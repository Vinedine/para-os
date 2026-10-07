#!/usr/bin/env python3
"""mirror.py - copy a vault on a synced drive into a git repository outside it, and commit.
para-os-integration: vault-mirror 2026.10.01 - see CHANGELOG.md; /para-upgrade reports drift against this line.

A vault in a folder a cloud drive syncs keeps no `.git`: git does not run reliably on every
drive's filesystem, and a sync client uploading git's internal files one by one can corrupt
them. The mirror is a git repository on a local disk, written only by this script, that holds
the vault's history.
    py -3 mirror.py                  # copy, then commit with a generated message
    py -3 mirror.py -m "Archive X"   # copy, then commit with your own subject
    py -3 mirror.py --dry-run        # report what would be copied, write nothing
    py -3 mirror.py --force          # overwrite uncommitted edits in the mirror

One way, vault to mirror, never back: the mirror is always the older copy. Install this file
at <vault>/resources/scripts/vault-mirror/mirror.py; the vault is derived from that path, and
the mirror comes from $PARAOS_VAULT_MIRROR or --mirror. Every file the vault holds is copied,
and the mirror's own .git/info/exclude decides what the history keeps.
See integrations/vault-mirror/README.md. Standard library only, Python 3.9+.
"""
import argparse
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

# This copy lives in <vault>/resources/scripts/vault-mirror/, so the vault is three levels up.
VAULT = Path(__file__).resolve().parents[3]

# Never copied, and never deleted from the mirror: git's own storage. The mirror's is its
# history, and a vault being moved onto a mirror still holds one of its own.
GIT_DIR = ".git"

# Files no script can read, skipped on both sides so the mirror keeps whatever copy its history
# holds. Anything else unwanted is copied and kept out of the history by .git/info/exclude.
UNREADABLE = [
    # Google Drive's native-format pointers, which Drive for Desktop refuses to open
    # (OSError 22, WinError 1): the document itself lives on a server.
    re.compile(r"\.g(doc|sheet|slides|form|draw|map|site|jam)$", re.IGNORECASE),
    # The marker OneDrive keeps locked in every synced root, named for a GUID.
    re.compile(r"^\.[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}", re.IGNORECASE),
    # An Office lock file, held open as long as its document is.
    re.compile(r"^~\$"),
]

MAX_BODY_LINES = 40


def skipped(name):
    return name == GIT_DIR or any(p.search(name) for p in UNREADABLE)


def _stop(err):
    # A folder that cannot be listed must stop the run: skipped, its files would read as
    # deleted from the vault and be deleted from the mirror.
    raise err


def relative_files(root):
    """Every file under root as a path relative to it, minus the skipped ones."""
    found = set()
    for dirpath, dirnames, filenames in os.walk(root, onerror=_stop):
        dirnames[:] = [d for d in dirnames if d != GIT_DIR]
        here = Path(dirpath)
        found.update((here / name).relative_to(root) for name in filenames if not skipped(name))
    return found


def digest(path):
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.digest()


def differs(a, b):
    """Size first, then content when only the timestamp moved: a re-download or a sync client
    touching a file shifts its mtime without changing a byte, and is not a change."""
    sa, sb = a.stat(), b.stat()
    if sa.st_size != sb.st_size:
        return True
    if int(sa.st_mtime) == int(sb.st_mtime):
        return False
    return digest(a) != digest(b)


def sync(live, mirror, dry_run):
    """Make mirror's files match live's. Returns the (added, modified, deleted) paths."""
    live_files, mirror_files = relative_files(live), relative_files(mirror)
    added, modified = [], []
    for rel in sorted(live_files):
        src, dst = live / rel, mirror / rel
        if rel not in mirror_files:
            added.append(rel)
        elif differs(src, dst):
            modified.append(rel)
        else:
            continue
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            copy(src, dst)

    deleted = sorted(mirror_files - live_files)
    if not dry_run:
        for rel in deleted:
            remove(mirror / rel)
        prune_empty_dirs(mirror)
    return added, modified, deleted


def long_path(path):
    """The extended-length form of an absolute Windows path, which reaches past 260 characters
    without the machine-wide LongPathsEnabled setting. Unchanged on any other platform."""
    s = str(path)
    if os.name != "nt" or s.startswith("\\\\?\\"):
        return path
    if s.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + s[2:])
    return Path("\\\\?\\" + s)


def copy(src, dst):
    """copy2, clearing a read-only flag that refuses the overwrite. A sync client can mark a
    file read-only, copy2 carries the flag into the mirror, and the next overwrite or delete
    there then fails with access denied, even for the owner."""
    try:
        shutil.copy2(src, dst)
    except PermissionError:
        if not dst.exists():
            raise
        os.chmod(dst, stat.S_IWRITE)
        shutil.copy2(src, dst)


def remove(path):
    """Delete a file or an empty folder, clearing a read-only flag the same way."""
    try:
        path.rmdir() if path.is_dir() else path.unlink()
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)
        path.rmdir() if path.is_dir() else path.unlink()


def prune_empty_dirs(mirror):
    folders = []
    for dirpath, dirnames, _ in os.walk(mirror):
        dirnames[:] = [d for d in dirnames if d != GIT_DIR]
        folders.append(Path(dirpath))
    for path in reversed(folders[1:]):  # deepest first, and never the mirror itself
        if not any(path.iterdir()):
            remove(path)


def git(mirror, *args, stdin=None):
    """Run git in the mirror, stopping the run with git's own message when it fails. UTF-8 both
    ways whatever the console's code page, or a filename outside it raises UnicodeEncodeError.
    core.longpaths lets Git for Windows reach the same long paths the copy does."""
    r = subprocess.run(["git", "-c", "core.longpaths=true", "-c", "core.quotepath=false",
                        "-C", str(mirror), *args],
                       input=stdin, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed in {mirror}:\n{r.stderr.strip()}")
    return r.stdout


def staged(mirror):
    """(added, modified, deleted) as `git add -A` staged them: what the commit will hold, which
    leaves out whatever the mirror's ignore rules keep as a copy only."""
    fields = git(mirror, "diff", "--cached", "--name-status", "--no-renames", "-z").split("\0")
    groups = {"A": [], "M": [], "D": []}
    for status, path in zip(fields[0::2], fields[1::2]):
        groups.get(status[:1], groups["M"]).append(path)
    return groups["A"], groups["M"], groups["D"]


def counts(added, modified, deleted):
    return f"{len(added)} added, {len(modified)} modified, {len(deleted)} deleted"


def build_message(added, modified, deleted, custom=None):
    summary = counts(added, modified, deleted)
    lines = [f"+ {p}" for p in added] + [f"~ {p}" for p in modified] + [f"- {p}" for p in deleted]
    if len(lines) > MAX_BODY_LINES:
        lines = lines[:MAX_BODY_LINES] + [f"... and {len(lines) - MAX_BODY_LINES} more"]
    subject = custom or f"Mirror live vault: {summary}"
    return f"{subject}\n\n{summary}.\n\n" + "\n".join(lines) + "\n"


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    ap = argparse.ArgumentParser(description="Copy this vault into its mirror repository and commit.")
    ap.add_argument("-m", "--message", help="commit subject; a summary is generated if omitted")
    ap.add_argument("--mirror", help="the mirror repository (default: $PARAOS_VAULT_MIRROR)")
    ap.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    ap.add_argument("--force", action="store_true", help="overwrite uncommitted edits in the mirror")
    args = ap.parse_args(argv)

    target = args.mirror or os.environ.get("PARAOS_VAULT_MIRROR")
    if not target:
        sys.exit("No mirror: set PARAOS_VAULT_MIRROR or pass --mirror <path to the mirror repository>.")
    mirror, vault = Path(target).expanduser().resolve(), VAULT
    if mirror == vault or vault in mirror.parents or mirror in vault.parents:
        sys.exit(f"The mirror {mirror} and the vault {vault} overlap. Refusing: the mirror "
                 f"lives outside the vault, and the vault outside the mirror.")
    if not (mirror / GIT_DIR).is_dir():
        sys.exit(f"Not a git repository: {mirror}. The integration's README covers the setup.")

    # A run leaves the mirror committed, so uncommitted changes mean someone edited the mirror,
    # and copying now would discard that work. A dry run writes nothing, so it reports them
    # and carries on: it is how to see what a --force would overwrite.
    dirty = git(mirror, "--no-optional-locks", "status", "--porcelain").rstrip()
    if dirty:
        print(f"The mirror has uncommitted changes:\n{dirty}", file=sys.stderr)
        if args.force:
            print("--force: they are about to be overwritten.\n", file=sys.stderr)
        elif args.dry_run:
            print("A run without --force would refuse rather than overwrite them.\n", file=sys.stderr)
        else:
            sys.exit("\nThe mirror is a copy, not a place to edit, and this run would overwrite "
                     "them. Commit or discard them there, or re-run with --force.")

    added, modified, deleted = sync(long_path(vault), long_path(mirror), args.dry_run)
    copied = counts(added, modified, deleted)
    if args.dry_run:
        for mark, group in (("+", added), ("~", modified), ("-", deleted)):
            for rel in group:
                print(f"  {mark} {rel.as_posix()}")
        print(f"\ndry run, nothing written: {copied}")
        return

    # After the copy the mirror's files match the vault's, so staging everything stages the
    # vault, and the mirror's ignore rules decide what the history keeps.
    git(mirror, "add", "-A")
    changes = staged(mirror)
    print(f"copied: {copied}")
    if not any(changes):
        print("Nothing to commit: the mirror's history is up to date.")
        return
    git(mirror, "commit", "-q", "-F", "-", stdin=build_message(*changes, custom=args.message))
    head = git(mirror, "rev-parse", "--short", "HEAD").strip()
    print(f"committed {head}: {counts(*changes)} in {mirror}")


if __name__ == "__main__":
    main()
