#!/usr/bin/env python3
"""The mechanics of /para-upgrade: a vault measured against a para-os clone at a committed
ref, as one JSON document on stdout.

    py -3 upgrade_scan.py --vault <path> [--clone <path>] [--ref origin/stable]
                          [--user-skills DIR] [--paraos-home DIR] [--indent N]
    py -3 upgrade_scan.py copy --vault <path> --clone <path> --commit <clone.commit> <master> <row path>

The scan is read-only: it never writes, fetches or asks, and reads every master at the ref's
commit. `copy` writes one master as the commit holds it over a row's path, keeping an
untouched row's `own` lines, whole or not at all and creating its folder; where the master
cannot be read it changes nothing and exits 4.

clone     `path`, `ref`, `commit` (the ref's commit, which a re-copy reads), `error` on exit 4-6.
revision  The vault's template marker (`vault`) against the master's (`master`): `verdict`
          equal, behind, ahead or no-marker. `entries`: each changelog revision after the
          vault's, up to the master's, with its `- ` lines as `reactions`, the lead dropped.
          `baseline`: the ref's commit where its template still carries the vault's marker, else
          the marker's release tag, else the commit that added it; null where none.
files     Every vault file the kit owns that is not `current`: `path` (vault-relative,
          absolute outside the vault), `kind`, `master` (its path in the clone), `state`.
          kind   skill: a base or declared add-on skill where the vault runs it (its bundled
                 copy, else the user-level one; a missing one beside its other kit skills;
                 para-shared wherever one runs), a multi-vault skill where installed. rule,
                 settings. integration: a file with a `para-os-integration:` marker, or one at
                 resources/scripts/[<name>/]<file> where the ref ships a marked master of that
                 name, under integrations/<name>/ or a declared add-on's pipeline/. Null on any
                 other retired file.
          state  current: nothing to take from the kit, the ref's bytes or those bytes with
                 lines of the vault's own added (a rule file the vault writes into), or for a
                 JSON file, keys and list entries of its own (settings with more deny rules).
                 untouched: bytes the master held at some commit along the ref, or those with
                 inserted lines (`own`) whose neighbours the ref still holds, so a re-copy
                 loses nothing local. edited: any other bytes, with `diff` from the master to
                 the copy, and `own` where only the ref's change to a neighbour stopped them.
                 missing. no-master: an integration the ref ships no master for. retired: a
                 file a changelog `Retired:` line names that the kit no longer ships, `master`
                 null.
          Bytes are compared as git blob ids, line endings and a byte-order mark normalised.
contract  The change to base/CLAUDE.md.template, and each declared add-on's CLAUDE.md.sections,
          from `baseline` to the ref: one row per `## ` section that changed (`file`,
          `heading`, "" above the first, and the section's unified `diff`), the marker line left
          out. With no baseline every section is new.
snapshot  {path: digest} of CLAUDE.md and every row, for `paraos_vault.py changed`.

`Retired:` opens a line of a changelog entry and lists backticked vault-relative paths or
globs; a folder retires every file under it, and a `.claude/skills/` path also matches under
--user-skills. Every entry up to the master's counts, whatever the vault's marker.

Exit codes: 0 answered; 2 the shared library is missing; 3 --vault is not a vault root; 4 the
clone or the ref cannot be read, or the ref holds no CHANGELOG.md or marked template; 5 no
--ref and no origin/stable; 6 no clone found.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        H2_RE, INTEGRATION_MARKER_RE, TEMPLATE_MARKER_RE, declarations, find_clone, git, git_bytes,
        integration_markers, normalised, paraos_home_dir, read_text,
        snapshot, template_marker, vault_root,
    )
    from paraos_clone import (  # noqa: E402
        BASE_TEMPLATE, addon_root, changelog_entries, clone_read, clone_ref, clone_session,
        entries_between,
    )
except ImportError as missing:  # para-shared/scripts.md: the skill stops
    print(f"upgrade_scan: {missing}. Install para-shared beside this skill: "
          f"{SHARED_DIR}/paraos_vault.py", file=sys.stderr)
    sys.exit(2)

STABLE = "origin/stable"
SECTIONS = "CLAUDE.md.sections"
DIFF_CAP = 200
REACTION_RE = re.compile(r"^- (.+?)[ \t]*$", re.M)
RETIRED_RE = re.compile(r"^Retired:(.*)$", re.M)
BACKTICK_RE = re.compile(r"`([^`]+)`")


class Kit:
    """The clone at one commit: its tree as {path: blob id}, and every blob id each path held
    along its history, which is what makes a copy untouched."""

    def __init__(self, clone, commit):
        self.clone, self.commit = clone, commit
        self.tree, self._shipped, self.master = {}, None, None
        for item in (git_bytes(clone, ["ls-tree", "-r", "-z", commit]) or b"").split(b"\0"):
            if b"\t" in item:
                meta, path = item.split(b"\t", 1)
                self.tree[path.decode("utf-8", "replace")] = meta.split()[2].decode()

    def shipped(self, path):
        if self._shipped is None:
            self._shipped, out = {}, (git_bytes(self.clone, [
                "log", "-m", "--raw", "-z", "--no-renames", "--no-abbrev", "--format=",
                self.commit]) or b"").split(b"\0")
            for meta, name in zip(out[::2], out[1::2]):
                self._shipped.setdefault(name.decode("utf-8", "replace"), set()).update(
                    meta.decode().split()[2:4])
        return self._shipped.get(path, set())

    def text(self, path, commit=None):
        data = clone_read(self.clone, commit or self.commit, path)
        return None if data is None else normalised(data).decode("utf-8", "replace")

    def under(self, folder):
        return [p for p in self.tree if p.startswith(folder + "/")]


def open_clone(clone, ref_arg):
    """(clone block, exit code, Kit or None)."""
    ref = ref_arg or STABLE
    block = {"path": str(clone), "ref": ref, "commit": None, "error": None}
    if git(clone, ["rev-parse", "--git-dir"]) is None:
        block["error"] = f"not a git repository: {clone}"
        return block, 4, None
    resolved = clone_ref(clone, ref)
    if resolved is None:
        block["error"] = f"ref does not resolve: {ref}"
        return block, 5 if ref_arg is None else 4, None
    kit = Kit(clone, resolved["commit"])
    block["commit"] = kit.commit
    template = kit.text(BASE_TEMPLATE)
    if template is None or kit.text("CHANGELOG.md") is None:
        block["error"] = f"not a para-os clone: {ref} holds no CHANGELOG.md and template"
        return block, 4, None
    kit.master = template_marker(template)
    if kit.master is None:
        block["error"] = f"{ref}:{BASE_TEMPLATE} carries no para-os-template marker"
        return block, 4, None
    return block, 0, kit


# ================================================================== revision and contract

def kit_entries(kit):
    return entries_between(changelog_entries(kit.text("CHANGELOG.md")), None, kit.master)


def revision_block(vault, kit):
    text = read_text(Path(vault) / "CLAUDE.md")
    mine, raw = template_marker(text), template_marker(text, raw=True)
    verdict = "no-marker" if mine is None else "equal" if mine == kit.master else \
        "ahead" if mine > kit.master else "behind"
    collected = [e for e in kit_entries(kit) if mine is None or e["revision"] > mine]
    return {"vault": mine, "master": kit.master, "verdict": verdict,
            "baseline": baseline(kit, raw, mine),
            "entries": [{"revision": e["revision"], "reactions": REACTION_RE.findall(e["body"])}
                        for e in collected]}


def baseline(kit, raw, mine):
    if mine == kit.master:
        return kit.commit
    if not raw:
        return None
    hits = (git(kit.clone, ["log", kit.commit, "--format=%H",
                            f"-S<!-- para-os-template: {raw} -->", "--", BASE_TEMPLATE]) or "").split()
    tag = git(kit.clone, ["rev-parse", "-q", "--verify", f"refs/tags/{raw}^{{commit}}"])
    return (tag or hits[-1]).strip() if hits else None


def sections(text):
    """{heading: [line, ...]} for each `## ` section, "" for the lines above the first, the
    marker line left out and trailing blank lines dropped."""
    out, heading = {"": []}, ""
    for line in text.splitlines(True):
        if TEMPLATE_MARKER_RE.search(line):
            continue
        m = H2_RE.match(line.rstrip("\n"))
        if m:
            heading = m.group(1).strip()
            out[heading] = []
        out[heading].append(line if line.endswith("\n") else line + "\n")
    for lines in out.values():
        while lines and not lines[-1].strip():
            lines.pop()
    return out


def contract_block(kit, base, decl):
    rows = []
    for name in [None] + addon_names(decl):
        new_path, old_path = (sections_path(kit, c, name) for c in (kit.commit, base))
        new = kit.text(new_path) if new_path else None
        if new is None:
            continue
        old, new = sections((kit.text(old_path, base) if old_path else None) or ""), sections(new)
        for heading in list(new) + [h for h in old if h not in new]:
            a, b = old.get(heading, []), new.get(heading, [])
            if a != b:
                rows.append({"file": new_path, "heading": heading,
                             "diff": "".join(list(difflib.unified_diff(a, b))[2:])})
    return rows


def sections_path(kit, commit, name):
    if commit is None:
        return None
    if name is None:
        return BASE_TEMPLATE
    root = addon_root(kit.clone, commit, name)
    return f"{root}/{SECTIONS}" if root else None


def addon_names(decl):
    return [n for n in [decl.get("flavor")] + list(decl.get("modules") or []) if n]


# ============================================================================== the files

def blob_id(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def plan_files(vault, kit, decl, user_dir):
    """{absolute vault-side path: (kind, master or None)} for every file the kit owns for
    this vault."""
    roots = [r for r in (addon_root(kit.clone, kit.commit, n) for n in addon_names(decl)) if r]
    planned = {}
    homes = [d for d in (vault / ".claude" / "skills", user_dir) if d and d.is_dir()]
    folders = {}
    for prefix, optional in [("base/.claude/skills/", False), ("multi-vault/", True)] + \
            [(f"{r}/.claude/skills/", False) for r in roots]:
        for path in kit.tree:
            name, _, rest = path[len(prefix):].partition("/")
            if path.startswith(prefix) and rest and \
                    not (optional and f"{prefix}{name}/SKILL.md" not in kit.tree):
                folders.setdefault(name, (prefix + name, optional))
    in_use = [d for d in homes if any((d / n).is_dir() for n in folders)]
    for name, (folder, optional) in folders.items():
        at = [d / name for d in homes if (d / name).is_dir()][:1] or \
            ([] if optional else [d / name for d in in_use[:1]])
        at = [d / name for d in in_use] if name == "para-shared" else at
        for master in kit.under(folder):
            planned.update((p / master[len(folder) + 1:], ("skill", master)) for p in at)

    for prefix in ["base/.claude/rules/"] + [f"{r}/.claude/rules/" for r in roots]:
        for master in kit.tree:
            if master.startswith(prefix):
                planned.setdefault(vault / ".claude" / "rules" / master[len(prefix):], ("rule", master))
    if "base/.claude/settings.json" in kit.tree:
        planned[vault / ".claude" / "settings.json"] = ("settings", "base/.claude/settings.json")

    for marker in integration_markers(vault):
        name, filename = marker["name"], Path(marker["file"]).name
        root = addon_root(kit.clone, kit.commit, name)
        master = next((m for m in (f"integrations/{name}/{filename}",
                                   f"{root}/pipeline/{filename}" if root else None)
                       if m in kit.tree), None)
        planned.setdefault(vault / marker["file"], ("integration", master))

    scripts = vault / "resources" / "scripts"
    shipped = [(m.split("/")[1], m) for m in kit.tree
               if m.startswith("integrations/") and m.count("/") == 2]
    shipped += [(r.rsplit("/", 1)[-1], m) for r in roots for m in kit.under(f"{r}/pipeline")]
    for name, master in shipped:
        filename = master.rsplit("/", 1)[-1]
        for path in (scripts / filename, scripts / name / filename):
            if path not in planned and path.is_file() and \
                    INTEGRATION_MARKER_RE.search(kit.text(master) or ""):
                planned[path] = ("integration", master)
    return planned


def state_of(path, kit, master):
    if master is None:
        return "no-master"
    if not path.is_file():
        return "missing"
    data = path.read_bytes()
    ids = {blob_id(data), blob_id(normalised(data))}
    if kit.tree[master] in ids:
        return "current"
    if ids & kit.shipped(master):
        return "untouched"
    kit_bytes = clone_read(kit.clone, kit.commit, master)
    if master.endswith(".json"):
        try:
            return "current" if holds(json.loads(data), json.loads(kit_bytes)) else "edited"
        except ValueError:
            return "edited"
    a, b = lines_of(kit_bytes), lines_of(data)
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    return "current" if all(op[0] in ("equal", "insert") for op in ops) else "edited"


def with_own_lines(data, kit, master):
    """Where `data` is a text the kit shipped at `master` plus inserted lines only: (the ref's
    text with those lines placed between the neighbours they had, or None where the ref
    changed a neighbour, [the inserted lines]). None otherwise."""
    if master.endswith(".json"):
        return None
    copy, best = lines_of(data), None
    for blob in kit.shipped(master) - {kit.tree[master]}:
        old = lines_of(git_bytes(kit.clone, ["cat-file", "blob", blob]) if blob.strip("0") else b"")
        ops = difflib.SequenceMatcher(None, old, copy, autojunk=False).get_opcodes()
        if not old or any(op[0] not in ("equal", "insert") for op in ops):
            continue
        inserts = [(i1, copy[j1:j2]) for tag, i1, _, j1, j2 in ops if tag == "insert"]
        if best is None or sum(len(c) for _, c in inserts) < sum(len(c) for _, c in best[1]):
            best = (old, inserts)
    if best is None:
        return None
    (old, inserts), ref = best, lines_of(clone_read(kit.clone, kit.commit, master))
    at = {-1: -1, len(old): len(ref)}
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, ref, autojunk=False).get_opcodes():
        if tag == "equal":
            at.update(zip(range(i1, i2), range(j1, j2)))
    own = [line for _, chunk in inserts for line in chunk]
    if any(at.get(k - 1) is None or at.get(k) != at[k - 1] + 1 for k, _ in inserts):
        return None, own
    for k, chunk in reversed(inserts):
        ref[at[k]:at[k]] = chunk
    return "".join(ref), own


def holds(have, want):
    """Whether parsed JSON `have` holds every key, value and list entry of `want`."""
    if isinstance(want, dict):
        return isinstance(have, dict) and all(k in have and holds(have[k], v) for k, v in want.items())
    if isinstance(want, list):
        return isinstance(have, list) and all(any(holds(h, w) for h in have) for w in want)
    return have == want


def retired_paths(vault, kit, user_dir):
    found = set()
    for entry in kit_entries(kit):
        for line in RETIRED_RE.findall(entry["body"]):
            for pattern in BACKTICK_RE.findall(line):
                pattern = pattern.strip().rstrip("/")
                if not pattern or pattern.startswith(("/", "\\")) or ":" in pattern \
                        or ".." in pattern.replace("\\", "/").split("/"):
                    continue
                places = [(vault, pattern)]
                if user_dir and pattern.startswith(".claude/skills/"):
                    places.append((user_dir, pattern[len(".claude/skills/"):]))
                for root, glob in places:
                    for hit in root.glob(glob):
                        found.update([hit] if hit.is_file() else
                                     (f for f in hit.rglob("*") if f.is_file()))
    return found


def files_block(vault, kit, decl, user_dir=None):
    """Every row, `current` ones included: /para-audit counts them."""
    vault = Path(vault).resolve()
    user_dir = Path(user_dir).resolve() if user_dir else None
    planned = plan_files(vault, kit, decl, user_dir)
    rows = {}
    for path, (kind, master) in planned.items():
        rows[path] = {"kind": kind, "master": master, "state": state_of(path, kit, master)}
        added = rows[path]["state"] == "edited" and with_own_lines(path.read_bytes(), kit, master)
        if added:
            rows[path]["own"] = [line.rstrip("\n") for line in added[1]]
            rows[path]["state"] = "untouched" if added[0] is not None else "edited"
        if rows[path]["state"] == "edited":
            rows[path]["diff"] = diff(clone_read(kit.clone, kit.commit, master), path.read_bytes(),
                                      master, shown(path, vault))
    for path in retired_paths(vault, kit, user_dir):
        if path not in planned or planned[path][1] is None:
            posix = path.as_posix()
            kind = "skill" if "/.claude/skills/" in posix or user_dir in path.parents else \
                "rule" if "/.claude/rules/" in posix else planned.get(path, (None,))[0]
            rows[path] = {"kind": kind, "master": None, "state": "retired"}
    return [dict({"path": shown(p, vault)}, **rows[p]) for p in sorted(rows, key=str)]


def shown(path, vault):
    try:
        return path.relative_to(vault).as_posix()
    except ValueError:
        return str(path)


def lines_of(data):
    return [ln if ln.endswith("\n") else ln + "\n"
            for ln in normalised(data or b"").decode("utf-8", "replace").splitlines(True)]


def diff(master_bytes, copy_bytes, master, path):
    a, b = lines_of(master_bytes), lines_of(copy_bytes)
    lines = list(difflib.unified_diff(a, b, master, path))
    if len(lines) > DIFF_CAP:
        lines = lines[:DIFF_CAP] + [f"... {len(lines) - DIFF_CAP} more lines\n"]
    return "".join(lines)


# ============================================================================== the report

@clone_session()
def build_report(vault, clone, ref, user_dir, default_clone=None):
    vault = Path(vault).resolve()
    report = {}
    if clone is None:
        report["clone"] = {"path": None, "ref": ref or STABLE, "commit": None, "error": (
            f"no para-os clone found: none at {default_clone}, and no --clone")}
        code, kit = 6, None
    else:
        report["clone"], code, kit = open_clone(Path(clone).resolve(), ref)
    if not vault_root(vault)["root"]:
        return report, 3
    if code:
        return report, code
    decl = declarations(vault)
    report["revision"] = revision_block(vault, kit)
    report["files"] = [r for r in files_block(vault, kit, decl, user_dir) if r["state"] != "current"]
    report["contract"] = contract_block(kit, report["revision"]["baseline"], decl)
    report["snapshot"] = snapshot([str(vault / "CLAUDE.md")] +
                                  [str(vault / r["path"]) for r in report["files"]])
    return report, 0


def copy(clone, commit, master, target):
    """None once `target` holds the master's bytes, with any lines of the vault's own the scan
    calls untouched, else what stopped it."""
    data = clone_read(clone, commit, master)
    if data is None:
        return f"{commit}:{master} cannot be read"
    target = Path(target)
    added = target.is_file() and with_own_lines(target.read_bytes(), Kit(clone, commit), master)
    if added and added[0] is not None:
        data = added[0].encode("utf-8")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    except OSError as error:
        return str(error)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
        os.replace(temp, target)
    except OSError as error:
        Path(temp).unlink(missing_ok=True)
        return str(error)
    return None


def copy_main(argv):
    ap = argparse.ArgumentParser(prog="upgrade_scan.py copy",
                                 description="Write one master over its vault copy, atomically.")
    ap.add_argument("--vault", required=True, help="vault root")
    ap.add_argument("--clone", required=True)
    ap.add_argument("--commit", required=True, help="the scan's clone.commit")
    ap.add_argument("master", help="the row's master")
    ap.add_argument("path", help="the row's path")
    args = ap.parse_args(argv)
    error = copy(Path(args.clone), args.commit, args.master, Path(args.vault) / args.path)
    if error:
        print(f"upgrade_scan copy: {error}", file=sys.stderr)
        return 4
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["copy"]:
        return copy_main(argv[1:])
    ap = argparse.ArgumentParser(description="Scan a vault and a para-os clone for /para-upgrade.")
    ap.add_argument("--vault", required=True, help="vault root")
    ap.add_argument("--clone", help="a local para-os clone (default: $PARAOS_HOME/para-os)")
    ap.add_argument("--ref", default=None, help="default: " + STABLE)
    ap.add_argument("--user-skills", default=str(Path.home() / ".claude" / "skills"))
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    ap.add_argument("--indent", type=int, default=None, help="pretty-print the JSON")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    clone, _ = find_clone(args.clone, args.paraos_home)
    report, code = build_report(args.vault, clone, args.ref, args.user_skills,
                                paraos_home_dir(args.paraos_home) / "para-os")
    json.dump(report, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    if code == 3:
        print(f"upgrade_scan: not a vault root: {args.vault} (projects/, areas/ or archive/, "
              f"and CLAUDE.md)", file=sys.stderr)
    elif code:
        print(f"upgrade_scan: {report['clone']['error']}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
