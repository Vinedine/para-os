#!/usr/bin/env python3
"""The mechanics of /para-audit: every vault the registry lists, measured against a para-os
clone at a committed ref, as one JSON document on stdout.

    py -3 audit_scan.py [--clone <path>] [--ref origin/stable] [--paraos-home DIR] [--indent N]

Read-only: never writes a file, never fetches, never asks, and reads no user-level skill or
settings file. Every master is read at a committed ref (`origin/stable` unless `--ref` names
another), never from the clone's working tree; a newer template revision there is reported
once as `master.in_development` and is never the bar.

Nothing here reads a vault or a clone by its own rules. The registry, declarations and
markers come from para-shared/scripts/paraos_vault.py; the master, the changelog delta, the
add-on roots, the rule files a master ships and the skill and integration verdicts come from
para-upgrade/scripts/upgrade_scan.py. Both are found beside this skill, or under
base/.claude/skills/ in a para-os checkout. What this script decides is the audit's own:

Which entries are audited. The registry is the only list, in its own order. An entry with
`retired: true` is `RETIRED (excluded)`; one without a `name` and a `path` is `INVALID`; one
whose path is not a folder, or holds no `CLAUDE.md`, is `UNREACHABLE`. Each lands in
`excluded`, never dropped. `active: false` changes nothing here. When every vault on one
drive is unreachable, and the drive holds two or more of them or its root is not there,
`drives` names the drive.

The seven checks, one cell each in `cells`, every defect a `finding` with its `fix` and a
`route` (`upgrade` where /para-upgrade applies it, `operator` where a person decides):

1. revision      The vault's template marker against the master's: `aligned`, `behind N`
                 (`revision.entries`: the changelog revisions it lacks, oldest first, the
                 order /para-upgrade applies them), `ahead <rev>`,
                 or `UNSTAMPED`, which counts as behind by every revision. A vault ahead is
                 judged on nothing a master older than it would answer: no add-on names,
                 rules, integrations or skills (`not judged`).
2. type          The `**Type:**` line against the entry's `kind`, compared as one name
                 (`paraos_vault.norm`). A mismatch names both and decides neither.
3. declarations  The marker, `**Type:**`, `**Flavor:**` and `**Modules:**` lines: a marker
                 comment that does not parse, a line away from the title (read by nothing),
                 a line off the literal `**Name:** value` shape, a template placeholder,
                 two flavors, an add-on no `addons/<name>/` holds at the ref, and any other
                 bold line under the title, `**Delivery:**` included.
4. rules         Each `.claude/rules/` file base or a declared add-on ships, present. A rule
                 file no master ships that no other audited vault of the same `kind` carries
                 is an `observation`, never a finding, and only where such a sibling exists.
                 A `voice-*.md` profile is one person's (para-shared/voice-profile.md), never
                 a topic file.
5. integrations  Each `para-os-integration:` script against its master, upgrade_scan's
                 verdict. `none` where the vault carries none.
6. skills        Each bundled `.claude/skills/` copy with a master, or named `para-*`,
                 against its master, line endings normalised. A vault's own skill is not
                 a copy.
7. size          `CLAUDE.md` lines (`wc -l`) against the 200-line adherence target set in
                 base/CLAUDE.md.template; the fix is the template's lever.

`upgrade_first` is the vault with an `upgrade` finding that is furthest behind, then has the
most findings, registry order breaking a tie; null where no vault has one.

Exit codes: 0 answered; 2 the libraries are missing (scan by hand); 3 no registry, or one
listing no entry; 4 the clone or the ref cannot be read, or its template carries no marker;
5 no `--ref` and the clone has no `origin/stable`; 6 no clone found.
"""

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

HERE = Path(__file__).resolve().parent
CANDIDATE_ROOTS = (HERE.parents[1], HERE.parents[2] / "base" / ".claude" / "skills")


def _skills_root():
    for root in CANDIDATE_ROOTS:
        if (root / "para-shared" / "scripts" / "paraos_vault.py").is_file() and \
                (root / "para-upgrade" / "scripts" / "upgrade_scan.py").is_file():
            return root
    return None


SKILLS_ROOT = _skills_root()
if SKILLS_ROOT is None:
    print("audit_scan: para-shared/ and para-upgrade/ belong beside this skill. Install them, "
          "or audit by hand with references/checks.md", file=sys.stderr)
    sys.exit(2)
sys.path[:0] = [str(SKILLS_ROOT / lib / "scripts") for lib in ("para-shared", "para-upgrade")]

try:
    from paraos_vault import (  # noqa: E402
        HEADER_FIELD_RE, INTEGRATION_MARKER_RE, TEMPLATE_MARKER_RE, clone_read, clone_session,
        declarations,
        find_clone, header_fields, live_lines, master_template, norm, paraos_home_dir,
        read_lines, registry,
    )
    from upgrade_scan import (  # noqa: E402
        _changelog_entries_at, _skeleton_master_files, clone_block, delta_block,
        integrations_block, masters_block, skills_block,
    )
except ImportError as missing:
    print(f"audit_scan: {missing}. Audit by hand with references/checks.md", file=sys.stderr)
    sys.exit(2)

COLUMNS = ("revision", "type", "declarations", "rules", "integrations", "skills", "size")
TARGET_LINES = 200
DECLARED = ("type", "flavor", "modules")
SHAPE_RE = re.compile(r"^\*\*(Type|Flavor|Modules):\*\* \S")
PLACEHOLDER = "{{"
MARKER_LINE_RE = re.compile(r"^\s*<!--.*para-os-template")
UPGRADE = "run /para-upgrade in this vault"
NOT_JUDGED = "not judged"


def finding(check, detail, fix=UPGRADE):
    return {"check": check, "detail": detail, "fix": fix,
            "route": "upgrade" if fix == UPGRADE else "operator"}


def counted(found, word):
    return "ok" if not found else f"{len(found)} {word}{'' if len(found) == 1 else 's'}"


# ================================================================ which entries, which drive

def excluded_status(entry):
    """(status, reason) for an entry the audit does not read, else None."""
    if isinstance(entry, dict) and entry.get("retired") is True:
        return "RETIRED (excluded)", "`retired: true` in the registry"
    if not isinstance(entry, dict) or not all(
            isinstance(entry.get(k), str) and entry[k].strip() for k in ("name", "path")):
        return "INVALID", "a registry entry needs a `name` and a `path`"
    path = Path(entry["path"])
    if not path.is_dir():
        return "UNREACHABLE", "the path is not there: not mounted, or moved"
    if not (path / "CLAUDE.md").is_file():
        return "UNREACHABLE", "the path holds no CLAUDE.md"
    return None


MOUNT_DEPTH = {("Volumes",): 3, ("mnt",): 3, ("media",): 4, ("run", "media"): 5}


def drive_of(path):
    """The drive a registered path lives on: a Windows drive letter or share, else a POSIX
    removable mount (`/Volumes/<x>`, `/mnt/<x>`, `/media/<user>/<x>`,
    `/run/media/<user>/<x>`), else `/`."""
    drive = PureWindowsPath(str(path)).drive
    if drive:
        return drive.upper() if len(drive) == 2 else drive
    parts = PurePosixPath(str(path).replace("\\", "/")).parts
    for lead, depth in MOUNT_DEPTH.items():
        if tuple(parts[1:1 + len(lead)]) == lead and len(parts) >= depth:
            return "/" + "/".join(parts[1:depth])
    return "/"


def _drive_root(drive):
    return Path(drive + "\\") if PureWindowsPath(drive).drive else Path(drive)


def down_drives(placed):
    """Each drive whose every registered vault is unreachable: two or more of them, or one
    whose drive root is not there. `placed` is [(name, path, unreachable)] in registry
    order."""
    groups = {}
    for name, path, unreachable in placed:
        groups.setdefault(drive_of(path), []).append((name, unreachable))
    return [{"drive": d, "vaults": [n for n, _ in members]} for d, members in groups.items()
            if all(u for _, u in members)
            and (len(members) > 1 or not _drive_root(d).exists())]


# ========================================================================= the checks

def revision_check(vault, clone, ref, template, in_development):
    delta = delta_block(vault, clone, ref, False, template)
    verdict, mine, master = delta["verdict"], delta["vault_marker"], delta["master_marker"]
    entries = sorted(e["revision"] for e in delta["entries"])
    out = {"verdict": verdict, "vault": mine, "master": master, "entries": entries,
           "behind": len(entries)}
    if verdict == "equal":
        return out, "aligned", []
    if verdict == "behind":
        return out, f"behind {len(entries)}", [finding(
            "revision", f"stamped {mine}, the master {master}: missing {', '.join(entries)}")]
    if verdict == "no-marker":
        return out, "UNSTAMPED", [finding(
            "revision", f"no template marker, so every revision up to {master} is unapplied")]
    draft = ", the revision in development in the clone's working tree" \
        if mine == in_development else ""
    return out, f"ahead {mine}", [finding(
        "revision", f"stamped {mine}, newer than the master's {master}{draft}: rules, "
        f"integrations, skills and add-on names are not judged against an older master",
        "fetch the clone, or audit again with ref= naming the revision the vault is on")]


def type_check(decl, entry):
    declared, kind = decl["type"], entry.get("kind")
    if not declared or PLACEHOLDER in declared:
        return "-", []
    if not isinstance(kind, str) or not kind.strip():
        return "no kind", [finding(
            "type", f"the registry entry has no `kind`; the vault declares `**Type:** {declared}`",
            "add `kind` to the registry entry")]
    if norm(declared) == norm(kind):
        return "ok", []
    return "mismatch", [finding(
        "type", f"`**Type:** {declared}` against the registry's `kind: {kind}`",
        "decide which is stale, then correct the registry's `kind` or the vault's `**Type:**` line")]


def _line_of(lines, key):
    """The first (number, text) outside a fence whose bold lead names `key`, any case."""
    for n, text in live_lines(lines):
        m = HEADER_FIELD_RE.match(text.strip())
        if m and m.group(1).strip().lower() == key:
            return n, text.strip()
    return None, None


def declaration_check(vault, decl):
    """Findings on the marker and the declaration lines, and the decl to resolve add-ons
    from: a placeholder or a two-name flavor is reported here, never resolved."""
    path = vault / "CLAUDE.md"
    lines = read_lines(path)
    found = []
    for n, text in live_lines(lines):
        if MARKER_LINE_RE.match(text) and not TEMPLATE_MARKER_RE.search(text):
            found.append(finding("declarations", f"line {n}, `{text.strip()}`, is not a "
                                 f"well-formed `<!-- para-os-template: YYYY.MM.NN -->` marker"))
    under = {k.strip().lower(): k for k in header_fields(path)}
    for key in DECLARED:
        n, text = _line_of(lines, key)
        label = f"**{key.capitalize()}:**"
        if key not in under:
            if n:
                found.append(finding("declarations", f"`{label}` at line {n} is not under the "
                                     f"title, so nothing reads it", "move it under the title"))
            elif key == "type":
                found.append(finding("declarations", "no `**Type:**` line under the title",
                                     "add `**Type:** <the registry's kind>` under the title"))
            continue
        if not SHAPE_RE.match(text):
            found.append(finding("declarations", f"line {n} is written `{text}`; the "
                                 f"machine-read shape is `{label} <value>`",
                                 f"rewrite it as `{label} <value>`"))
    for name, raw in under.items():
        if name not in DECLARED:
            found.append(finding(
                "declarations", f"`**{raw}:**` under the title is not a line para-os reads",
                UPGRADE if name == "delivery" else
                "move it out of the lines under the title, which hold declarations only"))

    flavor, modules = decl["flavor"], list(decl["modules"])
    for label, value in [("Type", decl["type"]), ("Flavor", flavor)] + \
            [("Modules", m) for m in modules]:
        if value and PLACEHOLDER in value:
            found.append(finding("declarations", f"`**{label}:**` still holds the template "
                                 f"placeholder `{value}`", "write the vault's own value"))
    if flavor and "," in flavor:
        found.append(finding("declarations", f"`**Flavor:** {flavor}` names more than one",
                             "a vault has one flavor: move the others to `**Modules:**`"))
    resolvable = {"type": decl["type"],
                  "flavor": None if not flavor or "," in flavor or PLACEHOLDER in flavor
                  else flavor,
                  "modules": [m for m in modules if PLACEHOLDER not in m]}
    return found, resolvable


def addon_check(addons_rows, ref):
    return [finding("declarations", f"`**{'Flavor' if r['kind'] == 'flavor' else 'Modules'}:**` "
                    f"names `{r['name']}`, and no `addons/{r['name']}/` exists at {ref}",
                    "correct the name, or remove it from the line")
            for r in addons_rows if not r["root"] and not r.get("carried_forward")]


def rules_check(vault, clone, ref, addons_rows):
    shipped = {vp: m for vp, m in _skeleton_master_files(clone, ref, False, addons_rows).items()
               if vp.startswith(".claude/rules/")}
    found = [finding("rules", f"`{vp}` is missing; the master ships it as `{m}`")
             for vp, m in sorted(shipped.items()) if not (vault / vp).is_file()]
    topics = sorted(name for name in rule_files(vault) if f".claude/rules/{name}" not in shipped
                    and not name.startswith("voice-"))
    return found, topics


def rule_files(vault):
    folder = vault / ".claude" / "rules"
    return {p.name for p in folder.glob("*.md")} if folder.is_dir() else set()


def _master_revision(clone, ref, path):
    data = clone_read(clone, ref, path) if path else None
    m = INTEGRATION_MARKER_RE.search(data.decode("utf-8", errors="replace")[:4000]) \
        if data else None
    return m.group(2) if m else None


def integration_findings(rows, clone, ref):
    found = []
    for r in rows:
        verdict, label = r.get("verdict"), f"`{r['file']}` ({r['name']} {r['revision']})"
        if verdict == "identical":
            continue
        if verdict == "behind":
            master_rev = _master_revision(clone, ref, r.get("master"))
            found.append(finding("integrations", f"{label} is behind its master "
                                 f"`{r['master']}` at {master_rev or 'an unstamped revision'}"))
        elif verdict == "marker-matches-content-differs":
            found.append(finding("integrations", f"{label}: its content is not the "
                                 f"revision its marker names"))
        elif verdict == "both":
            found.append(finding("integrations", f"{label} carries local changes on an "
                                 f"older master"))
        elif verdict == "ahead":
            found.append(finding("integrations", f"{label} is newer than its master at {ref}",
                                 "audit again with ref= naming the ref it came from"))
        elif verdict == "unresolvable":
            found.append(finding("integrations", f"{label} names an integration {ref} does "
                                 f"not ship", "check the integration name in its marker"))
        else:
            found.append(finding("integrations", f"{label} could be any of "
                                 f"{', '.join(r.get('candidates') or [])}"))
    return found


def skill_rows(block):
    """The bundled copies the audit reads: para-shared's, and every skill with a master or
    named `para-*`. A vault's own skill is not a copy of anything."""
    rows = list(block["rows"][0]["copies"])
    return rows + [r for r in block["rows"][1:] if r["name"].startswith("para-")
                   or r.get("master") or r.get("undeclared_addon")]


def skill_findings(rows, ref):
    found = []
    for r in rows:
        label = f"`.claude/skills/{r['name']}`"
        if r.get("undeclared_addon"):
            found.append(finding("skills", f"{label} comes from add-on "
                                 f"`{r['undeclared_addon']}`, which the vault does not declare",
                                 "declare the add-on under the title, or remove the copy"))
        elif r["verdict"] == "identical":
            continue
        elif r["verdict"] == "behind":
            by = f" by {r['revisions_behind']} revisions" if r.get("revisions_behind") else ""
            missing = f", missing {', '.join(r['missing'])}" if r.get("missing") else ""
            found.append(finding("skills", f"{label} is behind its master{by}{missing}"))
        elif r["verdict"] == "unmatched":
            found.append(finding("skills", f"{label} is a para-os name no master ships at {ref}"))
        elif r["verdict"] == "ahead":
            found.append(finding("skills", f"{label} is newer than its master at {ref}",
                                 "audit again with ref= naming the ref it came from"))
        else:
            found.append(finding("skills", f"{label} carries local changes on an older master"))
    return found


def size_check(vault):
    try:
        lines = (vault / "CLAUDE.md").read_bytes().count(b"\n")
    except OSError:
        return "-", []
    if lines <= TARGET_LINES:
        return str(lines), []
    return f"{lines} (over {TARGET_LINES})", [finding(
        "size", f"`CLAUDE.md` is {lines} lines, over the {TARGET_LINES}-line adherence target "
        f"the template sets", "extract procedure to `.claude/rules/`, leaving a one-line "
        "pointer: the template's lever, never cutting the vault's own rules")]


def audit_vault(entry, clone, ref, template, in_development, all_entries):
    vault = Path(entry["path"]).resolve()
    decl = declarations(vault)
    revision, cell, found = revision_check(vault, clone, ref, template, in_development)
    cells = {"revision": cell}
    cells["type"], more = type_check(decl, entry)
    found += more
    declared, resolvable = declaration_check(vault, decl)
    judged = revision["verdict"] != "ahead"
    addons = masters_block(clone, ref, False, resolvable)["addons"] if judged else []
    declared += addon_check(addons, ref)
    cells["declarations"] = counted(declared, "finding")
    found += declared

    topics = []
    if judged:
        rules, topics = rules_check(vault, clone, ref, addons)
        cells["rules"] = "ok" if not rules else f"{len(rules)} missing"
        integrations = integrations_block(vault, clone, ref, False, addons, template["marker"])
        rows = integrations["rows"]
        more = integration_findings(rows, clone, ref)
        cells["integrations"] = "none" if not rows else \
            "ok" if not more else f"{len(more)} of {len(rows)} differ"
        found += rules + more
        copies = skill_rows(skills_block(vault, clone, ref, False, None, decl, addons,
                                         template["marker"], all_entries))
        more = skill_findings(copies, ref)
        cells["skills"] = "none" if not copies else \
            "ok" if not more else f"{len(more)} of {len(copies)} differ"
        found += more
    else:
        cells.update({c: NOT_JUDGED for c in ("rules", "integrations", "skills")})
    cells["size"], more = size_check(vault)
    found += more

    row = {"name": entry["name"], "path": entry["path"], "kind": entry.get("kind"),
           "active": entry.get("active"), "type": decl["type"], "revision": revision,
           "cells": {c: cells[c] for c in COLUMNS}, "findings": found, "observations": []}
    return row, topics


def topic_observations(rows, topics, carried):
    """A topic file no other audited vault of the same kind carries, where one exists."""
    for i, row in enumerate(rows):
        kind = norm(row["kind"]) if isinstance(row["kind"], str) and row["kind"].strip() else None
        siblings = [carried[j] for j, other in enumerate(rows) if j != i and kind
                    and isinstance(other["kind"], str) and norm(other["kind"]) == kind]
        if not siblings:
            continue
        for name in topics[i]:
            if not any(name in files for files in siblings):
                row["observations"].append({"check": "rules", "detail": (
                    f"`.claude/rules/{name}` is a topic file no other `{row['kind']}` vault "
                    f"carries")})


def upgrade_first(rows):
    candidates = [r for r in rows if any(f["route"] == "upgrade" for f in r["findings"])]
    if not candidates:
        return None
    best = max(candidates, key=lambda r: (r["revision"]["behind"], len(r["findings"])))
    return {"name": best["name"], "revisions_behind": best["revision"]["behind"],
            "findings": len(best["findings"])}


# =========================================================================== the report

@clone_session()
def build_report(registry_path, entries, clone, ref_arg, clone_source, default_clone):
    report = {"registry": {"path": str(registry_path),
                           "entries": len(entries) if isinstance(entries, list) else None}}
    if not entries:
        report["error"] = f"no registry at {registry_path}" if entries is None else \
            f"{registry_path} lists no vault, or does not parse as a JSON list"
        return report, 3
    if clone is None:
        report["clone"] = {"path": None, "source": None, "error": (
            f"no para-os clone found: none at {default_clone}, and no --clone")}
        return report, 6

    clone = Path(clone).resolve()
    block, ok, ref = clone_block(clone, ref_arg, False)
    block["source"] = clone_source
    report["clone"] = block
    if not ok:
        return report, 5 if block["stable_missing"] else 4
    template = master_template(clone, ref)
    if template["marker"] is None:
        block["error"] = f"{ref}:{template['path']} carries no para-os-template marker"
        return report, 4
    developing = master_template(clone, ref, worktree=True)["marker"]
    in_development = developing if developing and developing > template["marker"] else None
    all_entries = _changelog_entries_at(clone, ref, False)
    report["master"] = {"ref": ref, "revision": template["marker"],
                        "in_development": in_development}
    report["columns"] = list(COLUMNS)

    rows, topics, carried, excluded, placed = [], [], [], [], []
    for number, entry in enumerate(entries, start=1):
        status = excluded_status(entry)
        name = entry.get("name") if isinstance(entry, dict) else None
        path = entry.get("path") if isinstance(entry, dict) else None
        if status:
            excluded.append({"entry": number, "name": name, "path": path,
                             "status": status[0], "reason": status[1]})
            if status[0] == "UNREACHABLE":
                placed.append((name, path, True))
            continue
        placed.append((name, path, False))
        row, topic = audit_vault(entry, clone, ref, template, in_development, all_entries)
        rows.append(row)
        topics.append(topic)
        carried.append(rule_files(Path(path)))
    topic_observations(rows, topics, carried)

    report.update({"vaults": rows, "excluded": excluded, "drives": down_drives(placed),
                   "upgrade_first": upgrade_first(rows)})
    return report, 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit every registered vault for /para-audit.")
    ap.add_argument("--clone", help="a local para-os clone (default: $PARAOS_HOME/para-os)")
    ap.add_argument("--ref", default=None, help="default: origin/stable")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    ap.add_argument("--indent", type=int, default=None, help="pretty-print the JSON")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    home = paraos_home_dir(args.paraos_home)
    registry_path = home / "vaults.json"
    entries = registry(args.paraos_home) if registry_path.is_file() else None
    clone, source = find_clone(args.clone, args.paraos_home)
    report, code = build_report(registry_path, entries, clone, args.ref, source,
                                home / "para-os")
    json.dump(report, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    error = report.get("error") or (report.get("clone") or {}).get("error")
    if code:
        print(f"audit_scan: {error}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
