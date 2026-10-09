#!/usr/bin/env python3
"""Reading the para-os clone a vault is measured against.

Imported by the skills that compare a vault to the kit: `/para-upgrade`, `/para-audit` and
`/para-deep-clean`'s revision check. Nothing here reads the vault; that is `paraos_vault.py`,
beside this file, which also holds `template_marker` and the git primitives this builds on.

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "para-shared" / "scripts"))
    from paraos_clone import clone_session, clone_read, master_template

What lives here: the changelog as a list of revision entries, and every read of a clone at a
ref: a file's bytes, a tree listing, where an addon lives, the master template, all through one
session per scan so git starts once rather than hundreds of times.
"""

import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from paraos_vault import H2_RE, git, git_bytes, live_lines, split_lines, template_marker

CHANGELOG_HEADING_RE = re.compile(r"^##\s+(\d{4}\.\d{2}\.\d{2})\s*$")
RULE_RE = re.compile(r"^-{3,}$")


def changelog_entries(text):
    """Each `## <revision>` entry of a changelog in the order written, as {revision, line,
    body}. The body is the entry itself, which is the procedure a migration runs; `line` is
    the 1-based line of its heading in `text`, so a report can point at the entry rather
    than quote it. A heading inside a fenced block is a sample, not an entry."""
    out, body = [], None
    for lineno, line in live_lines(split_lines(text)):
        m = CHANGELOG_HEADING_RE.match(line.strip())
        if m:
            body = []
            out.append({"revision": m.group(1), "line": lineno, "body": body})
        elif body is None:
            continue
        elif H2_RE.match(line):
            body = None
        else:
            body.append(line)
    for entry in out:
        lines = entry["body"]
        while lines and (not lines[-1].strip() or RULE_RE.match(lines[-1].strip())):
            lines.pop()
        entry["body"] = "\n".join(lines).strip()
    return out


def entries_between(entries, after, upto=None):
    """The entries a vault stamped `after` has not had yet, up to and including `upto`.
    Revisions compare as plain strings, which is what their padding is for."""
    return [e for e in entries
            if (after is None or e["revision"] > after)
            and (upto is None or e["revision"] <= upto)]


# --- a para-os clone, which a vault is measured against ------------------------------------
# Every reader here reads the commit a ref names, never the clone's checkout: a revision in
# flight lives in the working tree uncommitted, and a vault measured against it reads as
# behind a revision that never shipped. `worktree=True` is the one exception, asked for by
# name when a master about to be committed is the point: the files on disk in the clone,
# never its index. `ref` is then not read at all, since the caller has already settled that
# it names the checked-out branch.

BASE_TEMPLATE = "base/CLAUDE.md.template"
ADDONS_DIR = "addons"
OLDER_ADDON_DIRS = ("flavors",)                     # where a flavor lived before addons/


def _clone_rel(path):
    """A clone-relative path the way git names it: forward slashes, no `./`, no leading or
    trailing slash. `""` for the clone root."""
    text = str(path).replace("\\", "/").strip("/")
    text = str(PurePosixPath(text)) if text else ""
    return "" if text == "." else text


def _usable_ref(ref):
    """A ref git will read as a ref: a value opening on `-` would be read as an option."""
    return bool(ref) and not str(ref).startswith("-")


def _z_paths(out):
    """The paths of a `-z` listing, NUL-separated and never quoted, decoded as UTF-8."""
    return [p.decode("utf-8", errors="replace") for p in out.split(b"\0") if p]


_SESSION = None                 # the open clone session, if any; see clone_session()
_UNBATCHED = object()           # no session reader can answer: ask git directly
_OBJECT_TYPES = (b"blob", b"tree", b"commit", b"tag")


class _CloneSession:
    def __init__(self):
        self.readers = {}       # clone -> its `cat-file --batch` process, None once unusable
        self.objects = {}       # (clone, "<ref>:<path>") -> (type, bytes), None for no object
        self.listings = {}      # (clone, ref) -> `ls-tree -r` output, None where git refused
        self.refs = {}          # (clone, ref) -> clone_ref's answer

    def close(self):
        for proc in self.readers.values():
            if proc is not None:
                _close_batch(proc)


@contextmanager
def clone_session():
    """Read every clone once per question for the length of a scan.

    Starting git costs tens of milliseconds on Windows, and a scan asks its clone hundreds
    of questions. Inside a session `clone_read` and the folder check go through one
    long-lived `git cat-file --batch` per clone, `clone_files` filters one `ls-tree` of the
    whole tree per ref, `clone_ref` resolves each ref once, and every answer is kept.
    Working-tree reads are never kept: they go to the disk each time.

    The session assumes no clone changes while it is open, so it is for a caller that only
    reads its clones. Leaving it stops every reader it started, which Windows needs before
    a clone's folder can be deleted. A session opened inside another one joins it. Works as
    a decorator too.
    """
    global _SESSION
    if _SESSION is not None:
        yield
        return
    _SESSION = _CloneSession()
    try:
        yield
    finally:
        session, _SESSION = _SESSION, None
        session.close()


def _open_batch(clone):
    try:
        return subprocess.Popen(["git", "-C", str(clone), "cat-file", "--batch"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    except OSError:
        return None


def _close_batch(proc):
    for pipe in (proc.stdin, proc.stdout):
        try:
            pipe.close()
        except OSError:
            pass
    proc.kill()
    proc.wait()


def _session_key(clone, value):
    return os.path.abspath(str(clone)), value


def _batch_object(clone, ref, rel):
    """(type, bytes) of `<ref>:<rel>` from the open session's reader, None where it names
    no object, or _UNBATCHED where no session or reader can answer."""
    spec = f"{ref}:{rel}"
    if _SESSION is None or "\n" in spec or "\r" in spec:
        return _UNBATCHED
    key = _session_key(clone, spec)
    if key in _SESSION.objects:
        return _SESSION.objects[key]
    if key[0] not in _SESSION.readers:
        _SESSION.readers[key[0]] = _open_batch(clone)
    proc = _SESSION.readers[key[0]]
    if proc is None:
        return _UNBATCHED
    try:
        proc.stdin.write(spec.encode("utf-8") + b"\n")
        proc.stdin.flush()
        header = proc.stdout.readline()
        found = header.rstrip(b"\n").rsplit(b" ", 2)
        if len(found) == 3 and found[1] in _OBJECT_TYPES and found[2].isdigit():
            size = int(found[2])
            data = proc.stdout.read(size + 1)[:size]   # the content, then git's newline
            result = (found[1].decode("ascii"), data) if len(data) == size else _UNBATCHED
        else:
            # `<spec> missing` or `ambiguous`; nothing at all once git has exited, as it
            # does at once in a folder that is no repository
            result = None if header.endswith((b" missing\n", b" ambiguous\n")) else _UNBATCHED
    except OSError:
        result = _UNBATCHED
    if result is _UNBATCHED:
        _close_batch(proc)
        _SESSION.readers[key[0]] = None
        return result
    _SESSION.objects[key] = result
    return result


def _session_listing(clone, ref):
    """The whole tree's `ls-tree -r` output at a ref, once per session; _UNBATCHED outside
    one."""
    if _SESSION is None:
        return _UNBATCHED
    key = _session_key(clone, ref)
    if key not in _SESSION.listings:
        _SESSION.listings[key] = git_bytes(clone, ["--literal-pathspecs", "ls-tree", "-r",
                                                   "--name-only", "-z", ref])
    return _SESSION.listings[key]


def clone_ref(clone, ref):
    """The commit a ref names in a clone, as {ref, commit}: `ref` as given, `commit` its
    full hash. None where it names no commit (a typo, a branch never fetched) or `clone` is
    not a git repository. Peeled with `^{commit}`, so an annotated tag answers with the
    commit it tags, never the tag object's own hash.
    """
    if not _usable_ref(ref):
        return None
    key = _session_key(clone, ref)
    if _SESSION is not None and key in _SESSION.refs:
        return _SESSION.refs[key] and dict(_SESSION.refs[key])
    out = git(clone, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
    commit = out.strip() if out else ""
    answer = {"ref": ref, "commit": commit} if commit else None
    if _SESSION is not None:
        _SESSION.refs[key] = answer and dict(answer)
    return answer


def clone_read(clone, ref, path, worktree=False):
    """One file's bytes as a clone holds it at a ref, or None where the ref holds no file
    at that path: absent, or a folder.

    Read with `git cat-file blob <ref>:<path>`, the same bytes `git show` prints for a file,
    but an error for a folder where `git show` prints a listing that would read back as the
    file's content. With `worktree`, the file on disk in the clone, unstaged edits included
    and never the index.
    """
    rel = _clone_rel(path)
    if not rel:
        return None
    if worktree:
        target = Path(clone) / rel
        try:
            return target.read_bytes() if target.is_file() else None
        except OSError:
            return None
    if not _usable_ref(ref):
        return None
    found = _batch_object(clone, ref, rel)
    if found is not _UNBATCHED:
        return found[1] if found and found[0] == "blob" else None
    return git_bytes(clone, ["cat-file", "blob", f"{ref}:{rel}"])


def clone_files(clone, ref, prefix, worktree=False):
    """Every file a clone holds under `prefix` at a ref, as sorted clone-relative posix
    paths (`git ls-tree -r --name-only <ref> -- <prefix>`). A prefix naming one file answers
    with that file, and `""` with the whole tree. A prefix is a path, never a pattern, and
    matches whole segments: `addons/sales` never lists `addons/sales-extra/`.

    `[]` where nothing is there, None where git cannot answer at all (not a repository, a
    ref that names no commit), so a caller can tell an empty folder from a question never
    answered.

    With `worktree`, what the working tree holds: every tracked file still on disk, plus
    every untracked file the clone's own ignore rules do not exclude (`git ls-files
    --cached --others --exclude-standard`). An ignored file (a `__pycache__`, a live
    config) is part of no master, and a tracked file deleted on disk is not in the working
    tree whatever the index says.
    """
    rel = _clone_rel(prefix)
    spec = ["--", rel] if rel else []
    if worktree:
        out = git_bytes(clone, ["--literal-pathspecs", "ls-files", "-z", "--cached",
                                "--others", "--exclude-standard"] + spec)
    elif _usable_ref(ref):
        out = _session_listing(clone, ref)
        if out is _UNBATCHED:
            out = git_bytes(clone, ["--literal-pathspecs", "ls-tree", "-r", "--name-only",
                                    "-z", ref] + spec)
    else:
        out = None
    if out is None:
        return None
    found = set()
    for path in _z_paths(out):
        if rel and path != rel and not path.startswith(rel + "/"):
            continue
        if worktree and not os.path.lexists(Path(clone) / path):
            continue
        found.add(path)
    return sorted(found)


def _clone_holds_folder(clone, ref, path, worktree):
    """Whether a folder exists in a clone at a ref: it holds a file there, since git tracks
    no empty folder. With `worktree`, `clone_files` lists something under it, so a folder
    left on disk holding only ignored files does not count."""
    if worktree:
        return bool(clone_files(clone, ref, path, worktree=True))
    if not _usable_ref(ref):
        return False
    found = _batch_object(clone, ref, path)
    if found is not _UNBATCHED:
        return bool(found) and found[0] == "tree"
    out = git(clone, ["cat-file", "-t", f"{ref}:{path}"])
    return bool(out) and out.strip() == "tree"


def addon_root(clone, ref, name, worktree=False):
    """The clone-relative folder an addon (a flavor or a module) lives in at a ref, or None
    where that ref holds none by that name.

    Today every addon lives under `addons/<name>/`; before that a flavor lived under
    `flavors/<name>/`, and a vault pinned to an older ref is measured against the layout
    that ref carried. So a ref holding `addons/` answers from there alone, never from a
    folder that ref no longer carries, and a ref without it answers with `flavors/<name>`
    where that exists at it.
    """
    if not name or any(c in name for c in "/\\") or name in (".", ".."):
        return None
    if _clone_holds_folder(clone, ref, ADDONS_DIR, worktree):
        candidates = [f"{ADDONS_DIR}/{name}"]
    else:
        candidates = [f"{parent}/{name}" for parent in OLDER_ADDON_DIRS]
    return next((c for c in candidates if _clone_holds_folder(clone, ref, c, worktree)), None)


def master_template(clone, ref, worktree=False):
    """The `CLAUDE.md` template a vault is measured against at a ref,
    `base/CLAUDE.md.template`, as {path, marker, raw_marker, source}. `marker` is the
    revision as `template_marker` reads it and `raw_marker` the label the comment writes,
    so a legacy label is told apart from the revision it became. `source` is "base", or
    None where the ref holds no template.
    """
    data = clone_read(clone, ref, BASE_TEMPLATE, worktree)
    text = data.decode("utf-8", errors="replace") if data is not None else ""
    return {"path": BASE_TEMPLATE, "marker": template_marker(text),
            "raw_marker": template_marker(text, raw=True),
            "source": "base" if data is not None else None}
