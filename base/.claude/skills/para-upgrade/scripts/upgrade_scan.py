#!/usr/bin/env python3
"""Phase 0 and Phase 3 of /para-upgrade, plus the mechanical parts of Phase 2 and the Phase 5
re-checks, as a script instead of instructions.

    py -3 upgrade_scan.py --vault <path> --clone <path> [--ref origin/stable] [--worktree]
                          [--today YYYY-MM-DD] [--user-skills DIR] [--user-settings FILE]
                          [--unchanged EARLIER_SCAN.json] [--indent N]

Read-only: never writes a file, never fetches, never asks. One JSON document on stdout.
Phases 1, 2's merges, 4 and every write stay with the skill - this answers what changed and
what the vault already has, never what to do about it.

Reading the vault and the clone is not this script's own work: para-shared/scripts/
paraos_vault.py holds the primitives (declarations, the git and clone readers, the template
and changelog readers, snapshots). What lives here is what /para-upgrade alone decides: the
baseline commit lookup, the skeleton and rules field tables, the shared skill/integration
verdict rules, the suite locator, and the collected-name encoding for a plain glob.

What it deliberately does NOT do, so the skill keeps owning it: merge a CLAUDE.md section,
create a skeleton file, overwrite an installed script (the one sanctioned overwrite is a
skill-level write, re-verified by hand against a fresh run of this script), reclassify or
delete anything, or judge whether an entry applies to this vault.
"""

import argparse
import ast
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        ADDONS_DIR, BASE_TEMPLATE, H2_RE, INTEGRATION_MARKER_RE, MARKED_SUFFIXES,
        OLDER_ADDON_DIRS, SKELETON_TEMPLATE, addon_root, changed,
        changelog_entries, clone_files, clone_read, clone_ref, declarations, entries_between,
        git, git_bytes, git_status_lines, git_untracked, integration_markers, master_template,
        normalised,
        read_lines, read_text, registered_vault, registry, rel_posix, snapshot,
        template_marker, vault_root,
    )
except ImportError as missing:  # the skill falls back to scanning by hand
    print(f"upgrade_scan: {missing}. The shared vault library belongs at "
          f"{SHARED_DIR}/paraos_vault.py: install para-shared beside this skill, or scan "
          f"by hand with references/scan.md's by-hand fallback", file=sys.stderr)
    sys.exit(2)


# ============================================================ small local git helpers
# git_bytes() in the library answers None on any non-zero exit, which is right for a read
# that only ever succeeds or fails - but `git check-ignore` (1 = nothing ignored) and
# `git merge-base --is-ancestor` (1 = not an ancestor) use exit 1 as a real, non-error
# answer. Local to this script because no other caller needs that distinction.

def _git_raw(directory, args):
    try:
        return subprocess.run(["git", "-C", str(directory)] + list(args),
                              capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None


def _git_repo(directory):
    out = git(directory, ["rev-parse", "--is-inside-work-tree"])
    return bool(out) and out.strip() == "true"


def _porcelain_paths(directory):
    """Every path `git status --porcelain` names under `directory`, relative to it, a
    rename's new name only - the library's own status reading, as the raw relative name
    rather than a resolved absolute Path, since this is reported, not compared."""
    lines = git_status_lines(directory)
    return None if lines is None else [name for _, name in lines]


def _ignored_in_scope(vault, scope_files):
    if not scope_files:
        return []
    done = _git_raw(vault, ["-c", "core.quotePath=false", "check-ignore", "--"] + scope_files)
    if done is None or done.returncode not in (0, 1):
        return []
    return [ln for ln in done.stdout.decode("utf-8", errors="replace").splitlines() if ln]


def _scope_files(vault):
    """Every file under CLAUDE.md and .claude/, vault-relative posix paths - Precondition 5's
    scope."""
    vault = Path(vault)
    found = []
    if (vault / "CLAUDE.md").is_file():
        found.append("CLAUDE.md")
    claude_dir = vault / ".claude"
    if claude_dir.is_dir():
        for p in sorted(claude_dir.rglob("*")):
            if p.is_file():
                found.append(rel_posix(vault, p))
    return found


# ==================================================================== the vault block

def vault_block(vault, entries):
    info = vault_root(vault)
    hint = None
    if not info["root"]:
        entry = registered_vault(entries, vault)
        if entry:
            hint = {"name": entry.get("name"), "path": entry.get("path")}
    decl = declarations(vault)

    claude_md = vault / "CLAUDE.md"
    claude_md_lines = None
    if claude_md.is_file():
        try:
            claude_md_lines = claude_md.read_bytes().count(b"\n")  # wc -l: newlines, not lines
        except OSError:
            claude_md_lines = None

    repo = _git_repo(vault)
    if repo:
        dirty = _porcelain_paths(vault) or []
        untracked = []
        for under in ("CLAUDE.md", ".claude"):
            if (vault / under).exists():
                got = git_untracked(vault, under)
                if got:
                    untracked.extend(got)
        untracked = sorted(set(untracked))
        ignored = sorted(set(_ignored_in_scope(vault, _scope_files(vault))))
    else:
        dirty, untracked, ignored = [], [], []

    return {
        "path": str(vault), "root": info["root"], "missing": info["missing"], "hint": hint,
        "declarations": decl, "collected": decl["collected"], "claude_md_lines": claude_md_lines,
        "git": {"repo": repo, "dirty": dirty, "untracked_in_scope": untracked,
                "ignored_in_scope": ignored},
    }


# ==================================================================== the clone block

MASTER_DIRS = ("base", "integrations", "multi-vault")  # plus CHANGELOG.md and declared addons


def _dirty_masters(dirty, decl):
    """The dirty paths a run reads a master from - Precondition 3's question, so a dirty
    clone README is not read as an uncommitted master. The declared addons are matched under
    every layout this repo has shipped, and a collapsed untracked folder (`addons/`) counts
    when a master root lies inside it."""
    decl = decl or {}
    names = [n for n in [decl.get("delivery"), decl.get("flavor")] +
             list(decl.get("modules") or []) if n]
    roots = ([f"{d}/" for d in MASTER_DIRS] +
             [f"{layout}/{n}/" for layout in ADDON_ROOTS for n in names])
    return [p for p in dirty if p == "CHANGELOG.md" or
            any(p.startswith(r) or (p.endswith("/") and r.startswith(p)) for r in roots)]


STABLE = "origin/stable"  # what users get; main is where work merges


def clone_block(clone, ref_arg, worktree, decl=None):
    block = {"path": str(clone), "ref": ref_arg, "ref_commit": None, "worktree": worktree,
             "checked_out": None, "origin_stable": None, "same_commit": [], "dirty": None,
             "dirty_masters": None, "ref_merged": None, "stable_missing": False,
             "error": None}
    if not _git_repo(clone):
        block["error"] = f"not a git repository: {clone}"
        return block, False, None

    branch_out = git(clone, ["symbolic-ref", "--short", "-q", "HEAD"])
    branch = branch_out.strip() if branch_out else None
    head = clone_ref(clone, "HEAD")
    block["checked_out"] = {"branch": branch, "commit": head["commit"] if head else None}
    block["dirty"] = _porcelain_paths(clone) or []
    block["dirty_masters"] = _dirty_masters(block["dirty"], decl)

    if worktree:
        if ref_arg is not None and ref_arg != branch:
            block["error"] = (f"--worktree reads the checked-out branch as the ref; "
                              f"--ref {ref_arg} names something else "
                              f"({branch or 'a detached HEAD'})")
            return block, False, None
        if branch is None:
            block["error"] = ("--worktree needs a checked-out branch, and the clone is in "
                              "detached HEAD")
            return block, False, None
        ref = branch
    else:
        ref = ref_arg if ref_arg is not None else STABLE
    block["ref"] = ref

    resolved = clone_ref(clone, ref)
    if resolved is None:
        # A clone made before releases moved to stable: the skill offers the one-time switch.
        block["stable_missing"] = ref_arg is None and not worktree
        block["error"] = f"ref does not resolve: {ref}"
        return block, False, ref
    block["ref_commit"] = resolved["commit"]

    stable = clone_ref(clone, STABLE)
    block["origin_stable"] = {"commit": stable["commit"]} if stable else None

    names = {"ref": block["ref_commit"], "checked_out": block["checked_out"]["commit"],
             "origin_stable": block["origin_stable"]["commit"] if block["origin_stable"]
             else None}
    groups = {}
    for name, commit in names.items():
        if commit:
            groups.setdefault(commit, []).append(name)
    block["same_commit"] = sorted(sorted(g) for g in groups.values() if len(g) > 1)

    if block["origin_stable"]:
        done = _git_raw(clone, ["merge-base", "--is-ancestor", block["ref_commit"], STABLE])
        block["ref_merged"] = done.returncode == 0 if done is not None and \
            done.returncode in (0, 1) else None

    changelog = clone_read(clone, ref, "CHANGELOG.md", worktree=worktree)
    base_tpl = clone_read(clone, ref, BASE_TEMPLATE, worktree=worktree)
    if changelog is None or base_tpl is None:
        missing = [n for n, v in (("CHANGELOG.md", changelog), (BASE_TEMPLATE, base_tpl))
                   if v is None]
        block["error"] = f"not a para-os clone: {ref} carries no {' or '.join(missing)}"
        return block, False, ref

    return block, True, ref


# ================================================================== the masters block

ADDON_ROOTS = (ADDONS_DIR,) + OLDER_ADDON_DIRS  # every layout this repo has shipped


def _addon_row(clone, ref, name, kind, worktree, addons_present):
    root = addon_root(clone, ref, name, worktree)
    if root:
        return {"name": name, "kind": kind, "root": root}
    if kind == "module" and not addons_present:
        return {"name": name, "kind": kind, "root": None, "carried_forward": True}
    where = "in the clone's working tree" if worktree else f"at {ref}"
    return {"name": name, "kind": kind, "root": None, "reported": f"no folder {where}"}


def masters_block(clone, ref, worktree, decl):
    template = master_template(clone, ref, decl, worktree)
    delivery = decl.get("delivery")
    skeleton_overlay = None
    if delivery:
        root = addon_root(clone, ref, delivery, worktree)
        if root:
            skeleton_overlay = f"{root}/skeleton"

    addons_present = bool(clone_files(clone, ref, ADDONS_DIR, worktree))
    rows = []
    if delivery:
        rows.append(_addon_row(clone, ref, delivery, "delivery", worktree, addons_present))
    if decl.get("flavor"):
        rows.append(_addon_row(clone, ref, decl["flavor"], "flavor", worktree, addons_present))
    for m in decl.get("modules") or []:
        rows.append(_addon_row(clone, ref, m, "module", worktree, addons_present))

    return {"template": template, "skeleton_overlay": skeleton_overlay, "addons": rows}


# ==================================================================== the delta block

BOLD_LEAD_RE = re.compile(r"^(?:[-*]\s*)?\*\*([^*]+)\*\*")
# The LAST "Reaction:" in a paragraph: prose before it may name an earlier entry's own
# ("three points of the 2026.09.03 `.claude/rules/` Reaction: ..."), and the greedy lead
# skips past that mention.
REACTION_RE = re.compile(r".*(Reactions?:.*)", re.S)
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n|\n(?=[-*]\s)")


def _paragraphs(body):
    return [p.strip() for p in PARAGRAPH_SPLIT_RE.split(body) if p.strip()]


def _entry_shape(entry):
    items, reactions = [], []
    for p in _paragraphs(entry["body"]):
        m = BOLD_LEAD_RE.match(p)
        if m:
            items.append(m.group(1).strip())
        r = REACTION_RE.search(p)
        if r:
            reactions.append(r.group(1).strip())
    return {"revision": entry["revision"], "line": entry["line"], "items": items,
            "reactions": reactions}


def _changelog_entries_at(clone, ref, worktree):
    """Every `## <revision>` entry of CHANGELOG.md at the ref, parsed once - shared by
    delta_block (the collected-entries list) and skills_block (revisions_behind), so a vault
    with many skills does not re-read and re-parse the same small file once per skill."""
    changelog_bytes = clone_read(clone, ref, "CHANGELOG.md", worktree=worktree)
    changelog_text = changelog_bytes.decode("utf-8", errors="replace") if changelog_bytes else ""
    return changelog_entries(changelog_text)


def delta_block(vault, clone, ref, worktree, template):
    vault_text = read_text(vault / "CLAUDE.md")
    vault_marker = template_marker(vault_text)
    vault_marker_raw = template_marker(vault_text, raw=True)
    legacy = bool(vault_marker_raw) and vault_marker_raw != vault_marker
    master_marker = template.get("marker")

    all_entries = _changelog_entries_at(clone, ref, worktree)

    entries, current = [], None
    if master_marker is None:
        verdict = "unverified"
    elif vault_marker is None:
        verdict = "no-marker"
        entries = [_entry_shape(e) for e in entries_between(all_entries, None, master_marker)]
    elif vault_marker == master_marker:
        verdict = "equal"
        match = next((e for e in all_entries if e["revision"] == master_marker), None)
        current = _entry_shape(match) if match else None
    elif vault_marker > master_marker:
        verdict = "ahead"
    else:
        verdict = "behind"
        entries = [_entry_shape(e) for e in entries_between(all_entries, vault_marker, master_marker)]

    out = {"vault_marker": vault_marker, "vault_marker_raw": vault_marker_raw, "legacy": legacy,
           "master_marker": master_marker, "verdict": verdict, "entries": entries}
    if verdict == "equal":
        out["current"] = current
    return out


# ================================================================= the baseline block

def _template_path_variants(resolved_path, delivery):
    """The resolved template path plus every older-layout path it may have lived at along
    the same ref's history, since a -S search has to span the addons/ -> delivery+flavors ->
    flavors rename to find a commit from before it."""
    if not delivery:
        return [resolved_path]
    parts = resolved_path.split("/", 1)
    if len(parts) != 2 or parts[0] not in ADDON_ROOTS:
        return [resolved_path]
    rest = parts[1]
    seen, out = set(), []
    for root in ADDON_ROOTS:
        candidate = f"{root}/{rest}"
        if candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def baseline_block(clone, ref, delta, template, decl):
    vault_marker = delta["vault_marker"]
    vault_marker_raw = delta["vault_marker_raw"]
    if not vault_marker_raw:
        return {"commit": None, "source": None, "template": None,
                "reason": "the vault carries no template marker"}
    template_path = template.get("path")
    if not template_path:
        return {"commit": None, "source": None, "template": None,
                "reason": "no master template resolved at this ref"}

    # The ref's own committed tip, read from a commit even under --worktree: baselines are
    # always read from commits.
    tip_bytes = clone_read(clone, ref, template_path)
    if tip_bytes is not None and \
            template_marker(tip_bytes.decode("utf-8", errors="replace")) == vault_marker:
        tip = clone_ref(clone, ref)
        return {"commit": tip["commit"] if tip else None, "source": "ref-tip",
                "template": template_path,
                "reason": f"the ref's own committed template still carries {vault_marker}"}

    paths = _template_path_variants(template_path, decl.get("delivery"))
    marker_comment = f"<!-- para-os-template: {vault_marker_raw} -->"
    out = git(clone, ["log", ref, "--format=%H", f"-S{marker_comment}", "--"] + paths)
    hashes = [h for h in (out or "").splitlines() if h.strip()]
    if not hashes:
        return {"commit": None, "source": None, "template": None,
                "reason": f"no commit along {ref} carries {marker_comment}"}
    newest = hashes[0]
    parent_out = git(clone, ["rev-parse", f"{newest}^1"])
    parent = parent_out.strip() if parent_out else None
    return {"commit": parent, "source": "log-S", "template": template_path,
            "reason": f"parent of the newest commit changing {marker_comment} along {ref}"}


# ================================================================ the skeleton block

def _vault_path_for_skeleton(master_path, strip_prefix):
    vp = master_path[len(strip_prefix):] if master_path.startswith(strip_prefix) else master_path
    if Path(vp).name == "README.md.template":
        vp = str(Path(vp).with_name("README.md")).replace("\\", "/")
    return vp


def _skeleton_master_files(clone, ref, worktree, addons_rows):
    files = {}  # vault_path -> master clone-relative path

    for p in clone_files(clone, ref, "base", worktree) or []:
        if p in (BASE_TEMPLATE, "base/bootstrap-prompt.md") or p.startswith("base/.claude/skills/"):
            continue
        files[_vault_path_for_skeleton(p, "base/")] = p

    delivery_root = next((r["root"] for r in addons_rows if r["kind"] == "delivery" and r["root"]),
                         None)
    if delivery_root:
        prefix = f"{delivery_root}/skeleton/"
        for p in clone_files(clone, ref, f"{delivery_root}/skeleton", worktree) or []:
            if p == f"{delivery_root}/{SKELETON_TEMPLATE}":
                continue
            files[_vault_path_for_skeleton(p, prefix)] = p

    for r in addons_rows:
        if r["kind"] not in ("flavor", "module") or not r["root"]:
            continue
        root = r["root"]
        for p in clone_files(clone, ref, f"{root}/.claude/rules", worktree) or []:
            files[_vault_path_for_skeleton(p, f"{root}/")] = p
        for p in clone_files(clone, ref, f"{root}/skeleton", worktree) or []:
            files[_vault_path_for_skeleton(p, f"{root}/skeleton/")] = p

    return files


def _collected_plain_path(vault_path):
    return vault_path.replace("/", "__")


def skeleton_block(vault, clone, ref, worktree, decl, addons_rows):
    files = _skeleton_master_files(clone, ref, worktree, addons_rows)
    collected = decl.get("collected")
    rows = []
    for vp in sorted(files):
        master_path = files[vp]
        data = clone_read(clone, ref, master_path, worktree=worktree)
        vault_file = vault / vp
        present = vault_file.is_file()
        collected_as = None
        read_from = vault_file
        if not present and collected and vp.lower().endswith(".md"):
            enc = _collected_plain_path(vp)
            twin = vault / "resources" / "mds" / enc
            if twin.is_file():
                collected_as = f"resources/mds/{enc}"
                present = True
                read_from = twin
        identical = None
        if present and data is not None:
            try:
                identical = normalised(read_from.read_bytes()) == normalised(data)
            except OSError:
                identical = None
        folder_has_content = None
        if Path(vp).name in ("README.md", ".gitkeep"):
            folder = (vault / vp).parent
            if folder.is_dir():
                folder_has_content = any(
                    c.name not in ("README.md", ".gitkeep") for c in folder.iterdir())
        rows.append({"vault_path": vp, "master": master_path, "present": present,
                     "identical": identical, "collected_as": collected_as,
                     "folder_has_content": folder_has_content})
    return {"rows": rows, "triage_readme": (vault / "triage" / "README.md").is_file()}


# ==================================================================== the rules block

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
PATHS_LIST_RE = re.compile(r"^paths:[ \t]*\n((?:^[ \t]*-[ \t]*\S.*\n?)+)", re.M)
POINTER_SHAPE = "The full shape is in [.claude/rules/"
POINTER_CONVENTION = "The full convention is in [.claude/rules/"


def _frontmatter_paths(text):
    if not text:
        return []
    m = FRONTMATTER_RE.match(text.replace("\r\n", "\n"))
    if not m:
        return []
    pm = PATHS_LIST_RE.search(m.group(1))
    if not pm:
        return []
    out = []
    for line in pm.group(1).splitlines():
        item = line.strip()
        if item.startswith("-"):
            item = item[1:].strip()
        item = item.strip("'\"")
        if item:
            out.append(item)
    return out


def _collected_glob_twin(glob):
    """The resources/mds/ name a plain glob's collected twin carries: interior '/' -> '__', a
    leading '**/' -> '*__', an interior '/**/' -> '__*__', a trailing '/**' or '/*' -> '__*'."""
    g, prefix_add = glob, ""
    if g.startswith("**/"):
        prefix_add, g = "*__", g[3:]
    if g.endswith("/**"):
        g = g[:-3] + "__*"
    elif g.endswith("/*"):
        g = g[:-2] + "__*"
    g = g.replace("/**/", "/*/").replace("/", "__")
    return f"resources/mds/{prefix_add}{g}"


def _doubled_block(paths, decl):
    required = decl.get("delivery") == "readonly-ipad" or bool(decl.get("collected"))
    if not required:
        return {"required": False, "missing_twins": None}  # not applicable, never a failure
    plain = [p for p in paths if not p.startswith("resources/mds/")]
    missing = [p for p in plain if _collected_glob_twin(p) not in paths]
    return {"required": True, "missing_twins": missing}


def _rule_anchors(text):
    order = bool(re.search(r"^\*\*Order:\*\*", text, re.M))
    shape = bool(re.search(r"^##\s+The shape\s*$", text, re.M))
    headings = re.findall(r"^##\s+(.+?)\s*$", text, re.M)
    placeholders_last = bool(headings) and headings[-1].strip() == "Placeholders"
    return {"order": order, "shape": shape, "placeholders_last": placeholders_last}


def _rule_kind(anchors):
    vals = (anchors["order"], anchors["shape"], anchors["placeholders_last"])
    if all(vals):
        return "shape"
    if not any(vals):
        return "convention"
    return "mixed"


def _pointer_info(vault, filename):
    lines = read_lines(vault / "CLAUDE.md")
    section = None
    frag_open, frag_close = f".claude/rules/{filename}](", f".claude/rules/{filename})"
    for lineno, text in enumerate(lines, start=1):
        m = H2_RE.match(text.strip())
        if m:
            section = m.group(1).strip()
        if frag_open in text or frag_close in text:
            if POINTER_SHAPE in text:
                wording = "shape"
            elif POINTER_CONVENTION in text:
                wording = "convention"
            else:
                wording = "other"
            return {"present": True, "line": lineno, "section": section, "wording": wording}
    return {"present": False, "line": None, "section": None, "wording": None}


def _rule_master(clone, ref, worktree, name, addons_rows):
    candidates = ["base/.claude/rules/" + name]
    for r in addons_rows:
        if r["root"]:
            candidates.append(f"{r['root']}/.claude/rules/{name}")
    for path in candidates:
        data = clone_read(clone, ref, path, worktree=worktree)
        if data is not None:
            return path, data
    return None, None


def rules_block(vault, clone, ref, worktree, decl, addons_rows):
    out = []
    rules_dir = vault / ".claude" / "rules"
    if not rules_dir.is_dir():
        return out
    for path in sorted(rules_dir.glob("*.md")):
        text = read_text(path)
        paths = _frontmatter_paths(text)
        master_path, master_data = _rule_master(clone, ref, worktree, path.name, addons_rows)
        master_text = master_data.decode("utf-8", errors="replace") if master_data is not None \
            else None
        master_paths = _frontmatter_paths(master_text)
        anchors = _rule_anchors(text)
        out.append({
            "file": rel_posix(vault, path), "master": master_path,
            "paths": paths, "master_paths": master_paths,
            # null with no master: nothing to hold the paths against, not a failed check
            "paths_missing": sorted(set(master_paths) - set(paths)) if master_path else None,
            "paths_extra": sorted(set(paths) - set(master_paths)) if master_path else None,
            "kind": _rule_kind(anchors), "anchors": anchors,
            "doubled": _doubled_block(paths, decl), "pointer": _pointer_info(vault, path.name),
        })
    return out


# ================================================================= the settings block

def _load_json_dict(text):
    if not text:
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def settings_block(vault, clone, ref, worktree, user_settings_path):
    master_bytes = clone_read(clone, ref, "base/.claude/settings.json", worktree=worktree)
    master_keys = _load_json_dict(master_bytes.decode("utf-8", errors="replace")
                                  if master_bytes is not None else None)

    user_path = Path(user_settings_path)
    user_data = _load_json_dict(read_text(user_path)) if user_path.is_file() else {}
    matching = sorted(k for k in master_keys if k in user_data and user_data[k] == master_keys[k])

    vault_settings_path = vault / ".claude" / "settings.json"
    vault_present = vault_settings_path.is_file()
    vault_data = _load_json_dict(read_text(vault_settings_path)) if vault_present else {}

    missing_effective = sorted(
        k for k in master_keys
        if not (k in user_data and user_data[k] == master_keys[k])
        and not (k in vault_data and vault_data[k] == master_keys[k]))

    return {"master_keys": master_keys,
            "user_level": {"path": str(user_path), "matching": matching},
            "vault_level": {"present": vault_present, "keys": sorted(vault_data.keys())},
            "missing_effective": missing_effective}


# ============================================= shared machinery: skills and integrations

def _is_test_file(name):
    base = Path(name).name
    return base.startswith("test_") or ".test." in base


HISTORY_LIMIT = 200  # per-path cap, matching the old per-file git log's own limit


def _parse_batch_output(data, count):
    """`count` (bytes|None) results from one `git cat-file --batch` stdout, in request order.
    Order, not the printed identifier, is what lines a result up with its request: a
    `missing` line prints the ORIGINAL request text, a found one prints the resolved sha, and
    two different `<ref>:<path>` requests can legitimately resolve to the same sha."""
    results = []
    pos = 0
    for _ in range(count):
        nl = data.index(b"\n", pos)
        header = data[pos:nl].decode("utf-8", errors="replace")
        pos = nl + 1
        tokens = header.split(" ")
        if len(tokens) == 2 and tokens[1] == "missing":
            results.append(None)
            continue
        if len(tokens) < 3:
            results.append(None)
            continue
        obj_type, size_str = tokens[1], tokens[2]
        try:
            size = int(size_str)
        except ValueError:
            results.append(None)
            continue
        content = data[pos:pos + size]
        pos += size + 1  # the content's own trailing newline
        results.append(content if obj_type == "blob" else None)
    return results


RAW_DIFF_LINE_RE = re.compile(r"^:\d+ \d+ [0-9a-f]+ ([0-9a-f]{40}) ([A-Z])\d*\t(.+)$")


def _root_history_map(clone, ref, prefix):
    """{clone-relative path: [(commit, blob_sha), ...]} newest first, for every path under
    `prefix` at every commit along the ref's history that changed it - one `git log --raw`
    for the whole subtree, so a caller comparing many files under one root (every base skill,
    say) makes one git call instead of one per file."""
    out = git_bytes(clone, ["log", "--format=%H", "--raw", "--no-abbrev", "--no-renames", ref,
                                "--", prefix])
    if out is None:
        return {}
    history, commit = {}, None
    for line in out.decode("utf-8", errors="replace").splitlines():
        if not line:
            continue
        if line.startswith(":"):
            m = RAW_DIFF_LINE_RE.match(line)
            if not m or commit is None:
                continue
            blob, status, path = m.groups()
            if status.startswith("D"):
                continue
            entries = history.setdefault(path, [])
            if len(entries) < HISTORY_LIMIT:
                entries.append((commit, blob))
        else:
            commit = line.strip()
    return history


def _global_commit_order(clone, ref):
    """Every commit along the ref, newest first - one `git log`, used to answer 'which
    historical commit's template was still in effect at commit C' without an --is-ancestor
    call per commit. Assumes the ref's own history reads as a straight line, the same
    approximation `git log`'s own default (non---graph) order makes."""
    out = git(clone, ["log", "--format=%H", ref])
    return [c for c in (out or "").splitlines() if c.strip()]


def _effective_blob(commit, history_entries, commit_index):
    """The newest (commit, blob) in `history_entries` (newest first) at or before `commit`
    in `commit_index`'s order. None where `commit` itself is not in the index."""
    target = commit_index.get(commit)
    if target is None or not history_entries:
        return None
    for c, blob in history_entries:
        idx = commit_index.get(c)
        if idx is not None and idx >= target:
            return blob
    return None


def _branch_names(clone):
    out = git(clone, ["for-each-ref", "--format=%(refname:short)", "refs/heads/", "refs/remotes/"])
    return [n for n in (out or "").splitlines() if n.strip() and not n.endswith("/HEAD")]


class HistoryBatch:
    """Every historical blob, other-branch read and current-master read the skills and
    integrations blocks need for one scan, gathered in two strict phases: every `want_*` call
    happens while planning what to compare (no git process runs yet), then `resolve()` sends
    everything gathered since the last call in one `git cat-file --batch`, and every
    `blob()`/`ref_path()` read happens afterwards, from the cache `resolve()` filled.

    This is the fix for a cold run against the real clone taking 20+ seconds: the old code
    ran a `git log` plus a `git show` per commit per file. This runs a handful of
    `git log --raw` calls (one per master root, via `root_history()`) plus one batched read
    for every blob any of them needs - a `git cat-file --batch` call sent once per caller
    (skills_block and integrations_block each gather everything they need, then resolve once,
    so it is two calls for the whole scan rather than one per file).
    """

    def __init__(self, clone, ref, worktree):
        self.clone = clone
        self.ref = ref
        self.worktree = worktree
        self._roots = {}
        self._commit_index = None
        self._branches = None
        self._pending = []
        self._resolved = {}

    def root_history(self, prefix):
        if prefix not in self._roots:
            self._roots[prefix] = _root_history_map(self.clone, self.ref, prefix)
        return self._roots[prefix]

    def commit_index(self):
        if self._commit_index is None:
            order = _global_commit_order(self.clone, self.ref)
            self._commit_index = {c: i for i, c in enumerate(order)}
        return self._commit_index

    def branch_names(self):
        if self._branches is None:
            self._branches = _branch_names(self.clone)
        return self._branches

    def want_blob(self, sha):
        if sha and sha not in self._resolved and sha not in self._pending:
            self._pending.append(sha)

    def want_ref_path(self, ref_or_branch, path):
        key = f"{ref_or_branch}:{path}"
        if key not in self._resolved and key not in self._pending:
            self._pending.append(key)
        return key

    def resolve(self):
        if not self._pending:
            return
        wants, self._pending = self._pending, []
        stdin = ("\n".join(wants) + "\n").encode("utf-8")
        out = git_bytes(self.clone, ["cat-file", "--batch"], input=stdin)
        results = _parse_batch_output(out, len(wants)) if out is not None else [None] * len(wants)
        for key, content in zip(wants, results):
            self._resolved[key] = content

    def blob(self, sha):
        if not sha:
            return None
        self.resolve()
        return self._resolved.get(sha)

    def ref_path(self, ref_or_branch, path):
        self.resolve()
        return self._resolved.get(f"{ref_or_branch}:{path}")

    def current_master_bytes(self, path):
        if self.worktree:
            return clone_read(self.clone, self.ref, path, worktree=True)
        return self.ref_path(self.ref, path)

    def other_sources(self, path):
        """O, read from what resolve() already cached: the working tree (a plain disk read,
        never batched - it is not a git object), plus every other branch tip."""
        sources = []
        wt_bytes = clone_read(self.clone, self.ref, path, worktree=True)
        if wt_bytes is not None:
            sources.append({"source": "worktree", "bytes": wt_bytes})
        for branch in self.branch_names():
            data = self.ref_path(branch, path)
            if data is not None:
                sources.append({"source": branch, "bytes": data})
        return sources


def _sweep_root(master_root):
    """The broad prefix to sweep a skill's history under, so every base skill (or every
    skill of one addon) shares one `git log --raw` rather than one per skill folder."""
    if ".claude/skills" in master_root:
        idx = master_root.index(".claude/skills") + len(".claude/skills")
        return master_root[:idx]
    return master_root


def _gather_history_wants(batch, master_path, sweep_root, is_integration):
    history = batch.root_history(sweep_root).get(master_path, [])
    for _, blob in history:
        batch.want_blob(blob)
    if not is_integration and history:
        template_history = batch.root_history(BASE_TEMPLATE).get(BASE_TEMPLATE, [])
        index = batch.commit_index()
        for commit, _ in history:
            tpl_blob = _effective_blob(commit, template_history, index)
            if tpl_blob:
                batch.want_blob(tpl_blob)


def _gather_other_wants(batch, master_path):
    for branch in batch.branch_names():
        batch.want_ref_path(branch, master_path)


def _history_from_batch(batch, master_path, sweep_root, is_integration):
    """H, built from blobs `resolve()` already cached: every (commit, blob) the root's
    history map carries for this path, each with its revision - an integration's own marker
    in that blob, or (a skill file) the base template's effective blob at that commit."""
    entries = batch.root_history(sweep_root).get(master_path, [])
    template_history = None if is_integration else \
        batch.root_history(BASE_TEMPLATE).get(BASE_TEMPLATE, [])
    index = None if is_integration else batch.commit_index()
    history = []
    for commit, blob_sha in entries:
        data = batch.blob(blob_sha)
        if data is None:
            continue
        if is_integration:
            m = INTEGRATION_MARKER_RE.search(data.decode("utf-8", errors="replace")[:4000])
            revision = m.group(2) if m else None
        else:
            tpl_blob = _effective_blob(commit, template_history, index)
            tpl_data = batch.blob(tpl_blob) if tpl_blob else None
            revision = template_marker(tpl_data.decode("utf-8", errors="replace")) \
                if tpl_data is not None else None
        history.append({"commit": commit, "revision": revision, "bytes": data})
    return history


def _strip_integration_revision(text):
    return INTEGRATION_MARKER_RE.sub(lambda m: f"para-os-integration: {m.group(1)} REV", text)


CHAR_COMPARE_LIMIT = 4000  # characters across both sides' changed lines; past it, the linear estimate


def _change_distance(a_lines, b_lines):
    """How far two versions of a file are apart, smallest first: the number of lines inserted
    or deleted between them (the change count rule 5 names), then, to split a tie, how unlike
    the changed lines themselves are. Lines first because a character-level SequenceMatcher is
    quadratic in the file's length: on two integration scripts of a few thousand lines each it
    ran for minutes per version, and rule 5 compares a copy against every version in H. The
    tie-break reads only the lines that differ, and falls back to `quick_ratio` (linear) when
    even those are large."""
    matcher = difflib.SequenceMatcher(None, a_lines, b_lines, autojunk=False)
    changed, a_parts, b_parts = 0, [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changed += (i2 - i1) + (j2 - j1)
        a_parts.extend(a_lines[i1:i2])
        b_parts.extend(b_lines[j1:j2])
    a_text, b_text = "\n".join(a_parts), "\n".join(b_parts)
    inner = difflib.SequenceMatcher(None, a_text, b_text, autojunk=False)
    near = inner.ratio() if len(a_text) + len(b_text) <= CHAR_COMPARE_LIMIT else inner.quick_ratio()
    return changed, 1 - near


def compute_verdict(copy_bytes, master_bytes, history, other_sources, copy_revision,
                    master_revision, is_integration):
    """Rules 1-5 of 'The verdict', for a file present as both copy and master.
    C = normalised(copy_bytes), M = normalised(master_bytes), H = history (newest first,
    H[0] the tip, which equals M except under --worktree, where M is the uncommitted file
    and H[0] an older version a copy can still be behind), O = other_sources."""
    c = normalised(copy_bytes)
    m = normalised(master_bytes)
    if c == m:
        return {"verdict": "identical"}

    for h in history:
        if h.get("bytes") is not None and c == normalised(h["bytes"]):
            return {"verdict": "behind", "commit": h["commit"], "revision": h["revision"],
                    "within_revision": h["revision"] == master_revision}

    for src in other_sources:
        if c == normalised(src["bytes"]):
            return {"verdict": "ahead", "source": src["source"]}

    if is_integration:
        c_stripped = _strip_integration_revision(c.decode("utf-8", errors="replace"))
        for h in history:
            if h.get("bytes") is None or h["revision"] == copy_revision:
                continue
            h_stripped = _strip_integration_revision(
                normalised(h["bytes"]).decode("utf-8", errors="replace"))
            if c_stripped == h_stripped:
                if copy_revision == master_revision:
                    return {"verdict": "marker-matches-content-differs", "case": "hand-bumped",
                            "content_of": h["commit"], "revision": h["revision"]}
                return {"verdict": "behind", "commit": h["commit"], "revision": h["revision"],
                        "marker_edited": True}

    candidates, seen = [{"label": "master", "bytes": m}], {m}
    for h in history:
        if h.get("bytes") is not None:
            b = normalised(h["bytes"])
            if b not in seen:  # history repeats a version across many commits: compare it once
                seen.add(b)
                candidates.append({"label": h["commit"], "bytes": b})
    c_lines = c.decode("utf-8", errors="replace").split("\n")
    closest = min(candidates, key=lambda cand: _change_distance(
        c_lines, cand["bytes"].decode("utf-8", errors="replace").split("\n")))
    if is_integration and copy_revision == master_revision:
        return {"verdict": "marker-matches-content-differs", "case": None,
                "closest": closest["label"]}
    if closest["label"] == "master":
        return {"verdict": "ahead", "source": None}
    return {"verdict": "both", "closest": closest["label"]}


def _strip_ast_docstrings(tree):
    """A parsed module with every module/class/function docstring removed, so a copy whose
    code is identical but whose docstring was reworded still proves equivalent - the spec's
    own wording for the ast proof. Two passes: `ast.walk` is snapshotted into a plain list
    before any `.body` is mutated, so trimming one node's body can never change what nodes
    the walk still has queued to visit."""
    targets = [n for n in ast.walk(tree)
              if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
    for node in targets:
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            node.body = body[1:]
    return tree


def _ast_dump_no_docstrings(text):
    try:
        return ast.dump(_strip_ast_docstrings(ast.parse(text)))
    except SyntaxError:
        return None


def _mechanical_equivalence(copy_bytes, master_bytes, history, is_python):
    """Conditions 2 and 3 of the sanctioned overwrite: the copy is equivalent to some version
    in H."""
    for h in history:
        if h.get("bytes") is not None and normalised(copy_bytes) == normalised(h["bytes"]):
            return {"eligible": True, "proof": "history-match", "proof_commit": h["commit"]}
    if is_python:
        c_tree = _ast_dump_no_docstrings(copy_bytes.decode("utf-8", errors="replace"))
        if c_tree is not None:
            for h in history:
                if h.get("bytes") is None:
                    continue
                h_tree = _ast_dump_no_docstrings(h["bytes"].decode("utf-8", errors="replace"))
                if h_tree is not None and c_tree == h_tree:
                    return {"eligible": True, "proof": "ast", "proof_commit": h["commit"]}
    for h in history:
        if h.get("bytes") is None:
            continue
        if normalised(copy_bytes, trailing_ws=True) == normalised(h["bytes"], trailing_ws=True):
            return {"eligible": True, "proof": "whitespace", "proof_commit": h["commit"]}
    return {"eligible": False, "proof": None, "proof_commit": None}


# ================================================================== the skills block

def _skill_master_root(clone, ref, worktree, name, addons_rows):
    candidates = [f"base/.claude/skills/{name}", f"multi-vault/{name}"]
    for r in addons_rows:
        if r["kind"] in ("delivery", "flavor", "module") and r["root"]:
            candidates.append(f"{r['root']}/.claude/skills/{name}")
    for path in candidates:
        files = [f for f in (clone_files(clone, ref, path, worktree) or [])
                 if not _is_noise(f[len(path) + 1:])]
        if files:
            return path, files
    return None, None


def _addon_skill_index(clone, ref, worktree):
    """{addon_name: set(skill_names)} across whichever addon layout the ref carries - one
    clone_files() sweep per addon per layout, done once per scan rather than re-searched per
    unmatched skill copy (a real-run finding: 11 unmatched copies against origin/main cost 2
    of the run's 8 seconds before this, each re-walking the same addon list from scratch)."""
    seen = set()
    for parent in ADDON_ROOTS:
        for f in clone_files(clone, ref, parent, worktree) or []:
            parts = f.split("/")
            if len(parts) > 1:
                seen.add((parent, parts[1]))
    index = {}
    for parent, addon_name in seen:
        prefix = f"{parent}/{addon_name}/.claude/skills/"
        files = clone_files(clone, ref, prefix.rstrip("/"), worktree) or []
        names = index.setdefault(addon_name, set())
        for f in files:
            if f.startswith(prefix):
                names.add(f[len(prefix):].split("/", 1)[0])
    return index


def _find_undeclared_addon_skill(clone, ref, worktree, name, declared_names, index=None):
    """Every addon name the ref carries, whichever of the three layouts it ships (addons/,
    or the older delivery/ + flavors/ split origin/main is still on) - a real-run finding:
    origin/main has no addons/ folder at all, so a search scoped to it alone silently missed
    every undeclared addon's skill there. `index`, when given (skills_block's own, built once
    per scan via `_addon_skill_index`), answers from memory instead of a fresh git search;
    without it, this still answers on its own - the direct-call shape the tests exercise."""
    if index is not None:
        for addon_name, names in sorted(index.items()):
            if addon_name not in declared_names and name in names:
                return addon_name
        return None
    seen = set()
    for parent in ADDON_ROOTS:
        for f in clone_files(clone, ref, parent, worktree) or []:
            parts = f.split("/")
            if len(parts) > 1:
                seen.add(parts[1])
    for addon_name in sorted(seen):
        if addon_name in declared_names:
            continue
        for parent in ADDON_ROOTS:
            if clone_files(clone, ref, f"{parent}/{addon_name}/.claude/skills/{name}", worktree):
                return addon_name
    return None


def _skill_in_other(clone, ref, name):
    if clone_files(clone, ref, f"base/.claude/skills/{name}", worktree=True):
        return "worktree"
    for b in _branch_names(clone):
        if clone_files(clone, b, f"base/.claude/skills/{name}"):
            return b
    return None


SCRIPT_NAME_RE = re.compile(r"scripts/[A-Za-z0-9_.-]+\.(?:py|js|mjs|ps1|sh)")


def _names_missing_script(copy_dir, copy_files):
    skill_md = copy_dir / "SKILL.md"
    if not skill_md.is_file():
        return []
    named = set(SCRIPT_NAME_RE.findall(read_text(skill_md)))
    return sorted(named - set(copy_files))


# What running a skill's scripts or syncing its folder leaves beside it: tool caches (a
# suite run in place writes `.pytest_cache/`) and a sync client's or an OS's folder
# metadata. Never part of a skill, on either side of a tree diff: counted, they turn an
# identical copy into an `ahead` or `extra` one.
NOISE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules"}
NOISE_FILES = {"desktop.ini", ".DS_Store", "Thumbs.db"}


def _is_noise(rel):
    parts = rel.split("/")
    return (any(p in NOISE_DIRS for p in parts[:-1]) or parts[-1] in NOISE_FILES
            or parts[-1].endswith(".pyc"))


def _tree_files(copy_dir):
    return sorted(rel for rel in (p.relative_to(copy_dir).as_posix()
                                  for p in copy_dir.rglob("*") if p.is_file())
                  if not _is_noise(rel))


def _skill_revisions_behind(file_rows, all_entries, master_marker):
    """How many changelog revisions behind a skill is: entries after the OLDEST revision any
    of its differing files matched, up to and including the master's own marker
    (`entries_between`) - so a file that only just fell behind and one from three revisions
    ago both count against the skill's worst file, which is what 'call out by name a bundled
    skill more than one revision behind' (derived-copies.md) needs."""
    revisions = [r["revision"] for r in file_rows
                if r["verdict"] == "behind" and r.get("revision")]
    if not revisions or master_marker is None:
        return None
    return len(entries_between(all_entries, min(revisions), master_marker))


def _plan_skill_tree_row(clone, ref, worktree, name, location, copy_dir, addons_rows,
                         bundled_dir, user_dir, declared_names, batch, addon_index):
    """Phase A for one skill copy: find its master, list files, and register every git read
    the comparison will need on `batch`. No verdict is computed here - `_finish_skill_tree_row`
    does that, after `batch.resolve()` has filled the cache this plan asked for."""
    # With a copy in both places the vault's bundled one shadows the user-level install
    # (derived-copies.md), so both rows name it: `wins` answers for the pair, not the row.
    other_dir = user_dir if location == "bundled" else bundled_dir
    wins = "bundled" if (other_dir / name).is_dir() else None

    master_root, master_files = _skill_master_root(clone, ref, worktree, name, addons_rows)
    copy_files = _tree_files(copy_dir)

    if master_root is None:
        undeclared = _find_undeclared_addon_skill(clone, ref, worktree, name, declared_names,
                                                   index=addon_index)
        other = None if undeclared else _skill_in_other(clone, ref, name)
        return {"name": name, "location": location, "copy_dir": copy_dir, "wins": wins,
                "master_root": None, "undeclared_addon": undeclared, "other": other,
                "copy_files": copy_files}

    # clone_files() answers with the master-root-prefixed clone path; every comparison below
    # needs it relative to the skill root, the same way copy_files (from _tree_files) is.
    prefix = f"{master_root}/"
    master_rel = [f[len(prefix):] for f in master_files if f.startswith(prefix)]
    master_set, copy_set = set(master_rel), set(copy_files)
    missing = sorted(master_set - copy_set)
    matched = sorted(master_set & copy_set)
    extra_names = sorted(copy_set - master_set)

    sweep_root = _sweep_root(master_root)
    for rel in matched:
        master_path = f"{master_root}/{rel}"
        _gather_history_wants(batch, master_path, sweep_root, is_integration=False)
        _gather_other_wants(batch, master_path)
        if not worktree:
            batch.want_ref_path(ref, master_path)
    for rel in extra_names:
        _gather_other_wants(batch, f"{master_root}/{rel}")

    return {"name": name, "location": location, "copy_dir": copy_dir, "wins": wins,
            "master_root": master_root, "sweep_root": sweep_root, "missing": missing,
            "matched": matched, "extra_names": extra_names, "copy_files": copy_files}


def _finish_skill_tree_row(plan, batch, master_marker, all_entries):
    """Phase C: every blob `_plan_skill_tree_row` wanted is now in `batch`'s cache, so every
    read here is a dict lookup, not a git process."""
    name, location, copy_dir, wins = plan["name"], plan["location"], plan["copy_dir"], plan["wins"]

    if plan["master_root"] is None:
        if plan["undeclared_addon"]:
            return {"name": name, "location": location, "path": str(copy_dir), "wins": wins,
                    "undeclared_addon": plan["undeclared_addon"]}
        if plan["other"]:
            return {"name": name, "location": location, "path": str(copy_dir), "wins": wins,
                    "master": None, "verdict": "ahead", "source": plan["other"], "files": [],
                    "missing": [], "extra": [], "names_missing_script": [],
                    "revisions_behind": None, "suite": None}
        return {"name": name, "location": location, "path": str(copy_dir), "wins": wins,
                "master": None, "verdict": "unmatched", "files": [], "missing": [],
                "extra": [{"path": p, "verdict": "extra"} for p in plan["copy_files"]],
                "names_missing_script": [], "revisions_behind": None, "suite": None}

    master_root, sweep_root = plan["master_root"], plan["sweep_root"]
    file_rows = []
    for rel in plan["matched"]:
        master_path = f"{master_root}/{rel}"
        master_bytes = batch.current_master_bytes(master_path)
        if master_bytes is None:
            continue
        copy_bytes = (copy_dir / rel).read_bytes()
        history = _history_from_batch(batch, master_path, sweep_root, is_integration=False)
        other = batch.other_sources(master_path)
        info = compute_verdict(copy_bytes, master_bytes, history, other, None, master_marker,
                               is_integration=False)
        if info["verdict"] != "identical":
            file_rows.append(dict({"path": rel}, **info))

    extra = []
    for rel in plan["extra_names"]:
        master_path = f"{master_root}/{rel}"
        other = batch.other_sources(master_path)
        copy_norm = normalised((copy_dir / rel).read_bytes())
        match = next((s for s in other if normalised(s["bytes"]) == copy_norm), None)
        extra.append({"path": rel, "verdict": "ahead", "source": match["source"]} if match
                     else {"path": rel, "verdict": "extra"})

    ahead_present = any(r["verdict"] == "ahead" for r in file_rows) or \
        any(r["verdict"] == "ahead" for r in extra)
    if any(r["verdict"] == "both" for r in file_rows):
        overall = "both"
    elif any(r["verdict"] == "marker-matches-content-differs" for r in file_rows):
        overall = "marker-matches-content-differs"
    elif plan["missing"] or any(r["verdict"] == "behind" for r in file_rows):
        overall = "both" if ahead_present else "behind"
    elif ahead_present:
        overall = "ahead"
    else:
        overall = "identical"

    revisions_behind = _skill_revisions_behind(file_rows, all_entries, master_marker) \
        if overall == "behind" else None

    suite = None
    scripts_dir = copy_dir / "scripts"
    if scripts_dir.is_dir():
        suite = {"dir": str(scripts_dir),
                 "files": sorted(p.name for p in scripts_dir.glob("test_*.py")),
                 "command": f'"{sys.executable}" -m unittest discover -s "{scripts_dir}" '
                            f'-p "test_*.py"'}

    return {"name": name, "location": location, "path": str(copy_dir), "wins": wins,
            "master": master_root, "verdict": overall, "files": file_rows,
            "missing": plan["missing"], "extra": extra,
            "names_missing_script": _names_missing_script(copy_dir, plan["copy_files"]),
            "revisions_behind": revisions_behind, "suite": suite}


def skills_block(vault, clone, ref, worktree, user_skills_dir, decl, addons_rows, master_marker,
                 all_entries):
    vault = Path(vault)
    bundled_dir = vault / ".claude" / "skills"
    user_dir = Path(user_skills_dir)
    declared_names = {n for n in (decl.get("flavor"), *(decl.get("modules") or [])) if n}
    batch = HistoryBatch(clone, ref, worktree)

    library_targets = [("library", "para-shared", loc, d) for loc, d in
                       (("bundled", bundled_dir / "para-shared"),
                        ("user", user_dir / "para-shared")) if d.is_dir()]
    skill_targets, ignored = [], []
    for loc, d in (("bundled", bundled_dir), ("user", user_dir)):
        if not d.is_dir():
            continue
        for child in sorted(d.iterdir()):
            if not child.is_dir() or child.name == "para-shared":
                continue
            if (child / "SKILL.md").is_file():
                skill_targets.append(("skill", child.name, loc, child))
            else:
                ignored.append({"location": loc, "path": str(child)})

    targets = library_targets + skill_targets
    addon_index = _addon_skill_index(clone, ref, worktree)
    plans = [_plan_skill_tree_row(clone, ref, worktree, name, loc, copy_dir, addons_rows,
                                  bundled_dir, user_dir, declared_names, batch, addon_index)
             for _, name, loc, copy_dir in targets]

    batch.resolve()

    finished = [_finish_skill_tree_row(plan, batch, master_marker, all_entries) for plan in plans]

    library_copies = [row for (kind, *_), row in zip(targets, finished) if kind == "library"]
    rows = [{"name": "para-shared", "location": "library", "copies": library_copies}]
    rows += [row for (kind, *_), row in zip(targets, finished) if kind == "skill"]

    return {"rows": rows, "ignored": ignored}


# ============================================================== the integrations block

def _integration_master_path(clone, ref, worktree, name, filename, addons_rows):
    direct = f"integrations/{name}/{filename}"
    if clone_read(clone, ref, direct, worktree=worktree) is not None:
        return direct, None, None
    root = next((r["root"] for r in addons_rows if r["name"] == name and r["root"]), None) or \
        addon_root(clone, ref, name, worktree)
    if root:
        alt = f"{root}/pipeline/{filename}"
        if clone_read(clone, ref, alt, worktree=worktree) is not None:
            return alt, None, None

    scripts = []
    for prefix in (f"integrations/{name}", f"{root}/pipeline" if root else None):
        if not prefix:
            continue
        found = clone_files(clone, ref, prefix, worktree) or []
        scripts += [f for f in found if Path(f).suffix in MARKED_SUFFIXES
                   and not _is_test_file(f)]
    if len(scripts) == 1:
        return scripts[0], "renamed", None
    if len(scripts) > 1:
        return None, "ambiguous-rename", scripts
    return None, "unresolvable", None


def _integration_suite(clone, ref, worktree, master_dir):
    files_all = clone_files(clone, ref, master_dir, worktree) or []
    test_files = [f for f in files_all
                 if (Path(f).name.startswith("test_") and f.endswith(".py"))
                 or f.endswith(".test.js") or f.endswith(".test.mjs")]
    scripts = [f for f in files_all if Path(f).suffix in MARKED_SUFFIXES and not _is_test_file(f)]
    runner = None
    if any(f.endswith(".py") for f in test_files):
        runner = 'py -3 -m unittest discover -s . -p "test_*.py"'
    elif test_files:
        runner = "node --test " + " ".join(test_files)
    fixtures = [f for f in files_all if f not in test_files and f not in scripts
               and Path(f).name != "README.md"
               and not (f.endswith(".config.json") and not f.endswith(".template"))
               and not f.endswith(".env")]
    stems = {_suite_stem(f) for f in test_files}
    covers = [s for s in scripts if Path(s).stem in stems]
    uncovered = [s for s in scripts if s not in covers]
    return {"dir": master_dir, "files": test_files, "runner": runner, "fixtures": fixtures,
            "covers": covers, "uncovered": uncovered}


def _suite_stem(test_file):
    """The script stem a test file covers: `test_x.py` -> `x`, `x.test.js` / `x.test.mjs` -> `x`.
    Only the prefix or suffix is stripped - `test_latest_sync.py` covers `latest_sync`."""
    stem = Path(test_file).stem
    if stem.startswith("test_"):
        stem = stem[len("test_"):]
    if stem.endswith(".test"):
        stem = stem[:-len(".test")]
    return stem


def unmarked_scripts(vault, decl, marked_files):
    vault = Path(vault)
    candidates = []
    scripts_dir = vault / "resources" / "scripts"
    if scripts_dir.is_dir():
        candidates += [p for p in sorted(scripts_dir.iterdir())
                       if p.is_file() and p.suffix in MARKED_SUFFIXES and not _is_test_file(p.name)]
    if decl.get("delivery") == "readonly-ipad":
        for name in ("flip.ps1", "render.ps1", "render.mjs"):
            p = vault / name
            if p.is_file():
                candidates.append(p)
    marked_set = {vault / m["file"] for m in marked_files}
    return [p for p in candidates if p not in marked_set]


def _unmarked_matches(clone, ref, worktree, path):
    """Evidence only, never a verdict - and a simplified one: the ref's own tip under
    integrations/, not the full history every marked script's own _path_history reads.
    Noted as a departure in the build report."""
    norm = normalised(path.read_bytes())
    out = []
    for f in clone_files(clone, ref, "integrations", worktree) or []:
        if Path(f).suffix not in MARKED_SUFFIXES or _is_test_file(f):
            continue
        data = clone_read(clone, ref, f, worktree=worktree)
        if data is not None and normalised(data) == norm:
            out.append({"file": f, "commit": None})
    return out


def _plan_integration_row(vault, clone, ref, worktree, marker, addons_rows, batch):
    """Phase A for one marked script: resolve its master and register every git read the
    comparison will need. `copy_bytes` is read now (a plain vault-local disk read, not a git
    call) so `_finish_integration_row` never needs `vault` at all."""
    name, revision, file = marker["name"], marker["revision"], marker["file"]
    filename = Path(file).name
    master_path, special, candidates = _integration_master_path(
        clone, ref, worktree, name, filename, addons_rows)
    plan = {"file": file, "name": name, "revision": revision, "master_path": master_path,
           "special": special, "candidates": candidates,
           "copy_bytes": (vault / file).read_bytes()}
    if special in ("ambiguous-rename", "unresolvable") or master_path is None:
        return plan

    if not worktree:
        batch.want_ref_path(ref, master_path)
    sweep_root = str(Path(master_path).parent.as_posix())
    plan["sweep_root"] = sweep_root
    _gather_history_wants(batch, master_path, sweep_root, is_integration=True)
    _gather_other_wants(batch, master_path)
    return plan


def _finish_integration_row(plan, batch):
    """Phase C: every blob `_plan_integration_row` wanted is now in `batch`'s cache."""
    file, name, revision = plan["file"], plan["name"], plan["revision"]
    row = {"file": file, "name": name, "revision": revision}
    special, master_path = plan["special"], plan["master_path"]

    if special == "ambiguous-rename":
        row.update({"verdict": "ambiguous-rename", "candidates": plan["candidates"]})
        return row
    if special == "unresolvable" or master_path is None:
        row.update({"verdict": "unresolvable"})
        return row

    master_bytes = batch.current_master_bytes(master_path)
    if master_bytes is None:
        row.update({"verdict": "unresolvable", "master": master_path})
        return row

    copy_bytes = plan["copy_bytes"]
    history = _history_from_batch(batch, master_path, plan["sweep_root"], is_integration=True)
    other = batch.other_sources(master_path)
    mm = INTEGRATION_MARKER_RE.search(master_bytes.decode("utf-8", errors="replace")[:4000])
    master_rev = mm.group(2) if mm else None

    info = compute_verdict(copy_bytes, master_bytes, history, other, revision, master_rev,
                           is_integration=True)
    if special == "renamed":
        info["renamed"] = True

    c_norm, m_norm = normalised(copy_bytes), normalised(master_bytes)
    diff_lines = list(difflib.unified_diff(
        m_norm.decode("utf-8", errors="replace").splitlines(keepends=True),
        c_norm.decode("utf-8", errors="replace").splitlines(keepends=True),
        fromfile=master_path, tofile=file))
    added = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))

    overwrite = {"eligible": False, "proof": None, "proof_commit": None}
    if info["verdict"] not in ("ahead", "both", "marker-matches-content-differs"):
        overwrite = _mechanical_equivalence(copy_bytes, master_bytes, history,
                                            is_python=file.endswith(".py"))

    # The row's `revision` stays the copy's own marker; the history entry a behind or
    # hand-bumped verdict matched is reported beside it, never over it.
    if "revision" in info:
        info["matched_revision"] = info.pop("revision")
    row.update(info)
    row.update({
        "master": master_path, "diff": "".join(diff_lines[:200]),
        "diff_truncated": len(diff_lines) > 200,
        "diff_stat": {"added": added, "removed": removed}, "overwrite": overwrite,
        "suite": _integration_suite(batch.clone, batch.ref, batch.worktree, plan["sweep_root"]),
    })
    return row


def integrations_block(vault, clone, ref, worktree, decl, addons_rows, master_marker):
    vault = Path(vault)
    markers = integration_markers(vault)
    batch = HistoryBatch(clone, ref, worktree)

    plans = [_plan_integration_row(vault, clone, ref, worktree, marker, addons_rows, batch)
             for marker in markers]
    batch.resolve()
    rows = [_finish_integration_row(plan, batch) for plan in plans]

    unmarked = [{"file": rel_posix(vault, p), "matches": _unmarked_matches(clone, ref, worktree, p)}
               for p in unmarked_scripts(vault, decl, markers)]

    return {"rows": rows, "unmarked": unmarked}


# ==================================================================== the smoke block

def smoke_block(vault, today):
    bundled = vault / ".claude" / "skills" / "para-daily-brief" / "scripts" / "brief_scan.py"
    script = bundled if bundled.is_file() else \
        Path(__file__).resolve().parents[2] / "para-daily-brief" / "scripts" / "brief_scan.py"
    if not script.is_file():
        return {"available": False, "reason": f"no brief_scan.py at {script}", "script": str(script)}

    cmd = [sys.executable, str(script), "--vault", str(vault)]
    if today:
        cmd += ["--today", today]
    try:
        done = subprocess.run(cmd, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as err:
        return {"available": False, "reason": str(err), "script": str(script)}
    if done.returncode != 0:
        reason = done.stderr.decode("utf-8", errors="replace").strip() or \
            f"brief_scan.py exited {done.returncode}"
        return {"available": False, "reason": reason, "script": str(script)}
    try:
        data = json.loads(done.stdout.decode("utf-8", errors="replace"))
    except ValueError as err:
        return {"available": False, "reason": f"brief_scan.py output was not JSON: {err}",
                "script": str(script)}

    lanes = {k: len(v) for k, v in (data.get("lanes") or {}).items()}
    return {"available": True, "script": str(script), "today": data.get("today"),
            "totals": data.get("totals"), "entities": data.get("entities"), "lanes": lanes,
            "flags": data.get("flags"), "ideas": len(data.get("ideas") or []),
            "triage": len(data.get("triage") or [])}


# ================================================================== the snapshot block

BACKTICK_RE = re.compile(r"`([^`\s]+)`")
# A relative file path: slash-separated segments, the last carrying an extension or a
# leading dot. A folder (trailing slash), a skill (`/para-x`), a negation (`!.x`), a
# heading and a revision label (digits and dots) are not one.
FILE_PATH_RE = re.compile(r"(?:[\w.-]+/)*[\w-]*\.[\w.-]*[A-Za-z][\w.-]*")
CLONE_ROOTS = ("base/", "addons/", "delivery/", "flavors/", "integrations/", "multi-vault/",
               "examples/", "evals/", "docs/", "tools/")


def _reaction_paths(entries):
    """Every vault file path a backticked token in the entries' Reactions names, a path
    into the clone's own folders excluded. A token naming no vault file stays in, since
    its snapshot digest is only ever null."""
    paths = set()
    for entry in entries:
        for reaction in entry.get("reactions") or []:
            for token in BACKTICK_RE.findall(reaction):
                if (FILE_PATH_RE.fullmatch(token) and not token.startswith(CLONE_ROOTS)
                        and ".." not in token.split("/")):
                    paths.add(token)
    return sorted(paths)


def snapshot_block(vault, skeleton_rows, rules_rows, integration_files, reaction_paths=()):
    vault = Path(vault)
    paths = {vault / "CLAUDE.md", vault / "README.md", vault / ".claude" / "settings.json",
             vault / "resources" / "scripts" / "README.md"}
    paths.update(vault / p for p in reaction_paths)
    for row in rules_rows:
        paths.add(vault / row["file"])
    for row in skeleton_rows:
        paths.add(vault / row["vault_path"])
    for f in integration_files:
        paths.add(vault / f)
    return snapshot(sorted(str(p) for p in paths))


# ============================================================ the since block (--unchanged)

def _smoke_counts(smoke):
    if not smoke or not smoke.get("available"):
        return {}
    counts = {}
    for k, v in (smoke.get("totals") or {}).items():
        if isinstance(v, int):
            counts[f"totals.{k}"] = v
    for k, v in (smoke.get("lanes") or {}).items():
        counts[f"lanes.{k}"] = v
    counts["ideas"] = smoke.get("ideas")
    counts["triage"] = smoke.get("triage")
    for ent in smoke.get("entities") or []:
        counts[f"entities.{ent.get('label')}.open"] = ent.get("open")
    return counts


def since_block(earlier_doc, current_snapshot, current_smoke):
    earlier_snapshot = earlier_doc.get("snapshot") if isinstance(earlier_doc, dict) else None
    changed_paths = changed(earlier_snapshot) if isinstance(earlier_snapshot, dict) else \
        sorted(current_snapshot.keys())
    before_counts = _smoke_counts(earlier_doc.get("smoke")) if isinstance(earlier_doc, dict) else {}
    after_counts = _smoke_counts(current_smoke)
    moved = [{"count": name, "before": before_counts.get(name), "after": after_counts.get(name)}
             for name in sorted(set(before_counts) | set(after_counts))
             if before_counts.get(name) != after_counts.get(name)]
    return {"changed": changed_paths, "smoke": moved}


# =========================================================================== the plan

def build_report(vault, clone, ref_arg, worktree, today, user_skills, user_settings,
                 unchanged_path, entries):
    vault = Path(vault).resolve()
    clone = Path(clone).resolve()

    v_block = vault_block(vault, entries)
    c_block, clone_ok, ref = clone_block(clone, ref_arg, worktree, v_block["declarations"])
    report = {"vault": v_block, "clone": c_block}

    if not v_block["root"]:
        return report, 3
    if not clone_ok:
        return report, 5 if c_block["stable_missing"] else 4

    decl = v_block["declarations"]
    masters = masters_block(clone, ref, worktree, decl)
    template = masters["template"]

    delta = delta_block(vault, clone, ref, worktree, template)
    baseline = baseline_block(clone, ref, delta, template, decl)
    skeleton = skeleton_block(vault, clone, ref, worktree, decl, masters["addons"])
    rules = rules_block(vault, clone, ref, worktree, decl, masters["addons"])
    settings = settings_block(vault, clone, ref, worktree, user_settings)
    all_entries = _changelog_entries_at(clone, ref, worktree)
    skills = skills_block(vault, clone, ref, worktree, user_skills, decl, masters["addons"],
                          delta["master_marker"], all_entries)
    integrations = integrations_block(vault, clone, ref, worktree, decl, masters["addons"],
                                      delta["master_marker"])
    smoke = smoke_block(vault, today)

    integration_files = [m["file"] for m in integration_markers(vault)]
    snap = snapshot_block(vault, skeleton["rows"], rules, integration_files,
                          _reaction_paths(delta["entries"]))

    report.update({
        "masters": masters, "delta": delta, "baseline": baseline, "skeleton": skeleton,
        "rules": rules, "settings": settings, "skills": skills, "integrations": integrations,
        "smoke": smoke, "snapshot": snap,
    })

    if unchanged_path:
        try:
            earlier_doc = json.loads(Path(unchanged_path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            report["since"] = {"error": f"cannot read {unchanged_path}: {err}"}
        else:
            report["since"] = since_block(earlier_doc, snap, smoke)

    return report, 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Scan a vault and a para-os clone for /para-upgrade.")
    ap.add_argument("--vault", required=True, help="vault root")
    ap.add_argument("--clone", required=True, help="a local para-os clone")
    ap.add_argument("--ref", default=None, help="default: " + STABLE)
    ap.add_argument("--worktree", action="store_true",
                    help="read every master from the clone's working tree; the ref is then "
                         "the checked-out branch")
    ap.add_argument("--today", help="YYYY-MM-DD, passed to the smoke-test script")
    ap.add_argument("--user-skills", default=str(Path.home() / ".claude" / "skills"))
    ap.add_argument("--user-settings", default=str(Path.home() / ".claude" / "settings.json"))
    ap.add_argument("--unchanged", help="an earlier scan's JSON, for the since block")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    ap.add_argument("--indent", type=int, default=None, help="pretty-print the JSON")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    entries = registry(args.paraos_home)
    report, code = build_report(Path(args.vault), Path(args.clone), args.ref, args.worktree,
                                args.today, args.user_skills, args.user_settings,
                                args.unchanged, entries)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")

    if code == 3:
        hint = f" (registry: {report['vault']['hint']['name']} at {report['vault']['hint']['path']})" \
            if report["vault"].get("hint") else ""
        print(f"upgrade_scan: not a vault root: {args.vault} "
              f"(missing {', '.join(report['vault']['missing'])}){hint}", file=sys.stderr)
    elif code in (4, 5):
        print(f"upgrade_scan: {report['clone'].get('error')}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
