#!/usr/bin/env python3
"""How one vault stands against a para-os clone at a committed ref: the findings behind the
Command Center's Kit signal. Imported by global_scan.py and command_center.py, never run.

Read-only. Every master is read at a committed ref, never from the clone's working tree; a
newer template revision there is `in_development` and is never the bar.

Nothing here reads a vault or a clone by its own rules. Declarations, the roster and markers
come from para-shared/scripts/paraos_vault.py; the clone, the revision and the table of kit
files come from para-upgrade/scripts/upgrade_scan.py, whose docstring states each state.
Both are found beside this skill, or under base/.claude/skills/ in a para-os checkout
(`SKILLS_ROOT`); an import without them exits 2. What this script decides:

Which entries are read (`excluded_status`). An entry without a `name` and a `path` is
`INVALID`; one whose path is not a folder, or holds no `CLAUDE.md`, is `UNREACHABLE`, a
missing folder's reason naming the entry's `machine` where it has one. `active` and `machine`
change nothing else: a vault another machine pulls is read like any other.

The five checks of `audit_vault`, every defect a `finding` with its `fix` and a `route`
(`upgrade` where /para-upgrade applies it, `operator` where a person decides):

1. revision      The vault's revision stamp against the master's: `equal`, `behind`
                 (`revision.entries`: the changelog revisions it lacks, oldest first), `ahead`,
                 `no-marker`, which counts as behind by every revision, or `unverified` with
                 no clone. A vault ahead or unverified is judged on nothing a master would
                 answer: no add-on names, rules, integrations or skills, and none of a vault
                 ahead's findings routes to /para-upgrade, which never downgrades.
2. declarations  The marker, `**Type:**`, `**Flavor:**` and `**Modules:**` lines: a marker
                 comment that does not parse, a line away from the title (read by nothing),
                 a line off the literal `**Name:** value` shape, a template placeholder,
                 two flavors, an add-on no `addons/<name>/` holds at the ref, and any other
                 bold line under the title, `**Delivery:**` included. Then the roster: a
                 `## Who writes this vault` row with no role, or one finding where no row
                 has one.
3. rules         Each `.claude/rules/` file base or a declared add-on ships, from the table:
                 missing, behind (`untouched`) or retired. An edited copy is the vault's own.
                 Every rule file on disk, against para-shared/rule-files.md: one with no
                 `paths:` list in its frontmatter, which Claude Code loads in every session,
                 and a shape file (an `**Order:**` line or `## The shape`) with no
                 `## Placeholders`, each the operator's to fix.
4. integrations  Each `para-os-integration:` script's row in the table.
5. skills        Each bundled skill the table lists, one finding per skill folder, and a
                 bundled `para-*` folder no master ships. A vault's own skill is not a copy.
"""

import re
import sys
from pathlib import Path

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
    print("audit_scan: para-shared/ and para-upgrade/ belong beside this skill. Install them",
          file=sys.stderr)
    sys.exit(2)
sys.path[:0] = [str(SKILLS_ROOT / lib / "scripts") for lib in ("para-shared", "para-upgrade")]

try:
    from paraos_vault import (  # noqa: E402
        HEADER_FIELD_RE, TEMPLATE_MARKER_RE, declarations, header_fields, live_lines,
        read_lines, roster, vault_marker,
    )
    from paraos_clone import addon_root  # noqa: E402
    from upgrade_scan import files_block, revision_block  # noqa: E402
except ImportError as missing:
    print(f"audit_scan: {missing}. install para-shared and para-upgrade beside this skill",
          file=sys.stderr)
    sys.exit(2)

DECLARED = ("type", "flavor", "modules")
SHAPE_RE = re.compile(r"^\*\*(Type|Flavor|Modules):\*\* \S")
PLACEHOLDER = "{{"
MARKER_LINE_RE = re.compile(r"^\s*<!--.*para-os-template")
PATHS_RE = re.compile(r"^paths:[ \t]*(?:\n[ \t]*-[ \t]*\S|(?!\[[ \t]*\])\S)", re.M)
CONTRACT = "per para-shared/rule-files.md"
UPGRADE = "run /para-upgrade in this vault"
AHEAD = "fetch the clone: the vault is on a revision newer than its stable"


def finding(check, detail, fix=UPGRADE):
    return {"check": check, "detail": detail, "fix": fix,
            "route": "upgrade" if fix == UPGRADE else "operator"}


STATES = {"untouched": "behind", "edited": "edited", "missing": "missing", "retired": "retired",
          "no-master": "no master"}


def state_counts(rows):
    """Each state's count: `2 behind, 1 missing`."""
    counts = {}
    for r in rows:
        counts[STATES[r["state"]]] = counts.get(STATES[r["state"]], 0) + 1
    return ", ".join(f"{n} {word}" for word, n in sorted(counts.items()))


# ======================================================================= which entries

def excluded_status(entry):
    """(status, reason) for an entry that is not read, else None."""
    if not isinstance(entry, dict) or not all(
            isinstance(entry.get(k), str) and entry[k].strip() for k in ("name", "path")):
        return "INVALID", "a registry entry needs a `name` and a `path`"
    path = Path(entry["path"])
    if not path.is_dir():
        return "UNREACHABLE", f"the path is not there: pulled on {entry['machine']}" \
            if entry.get("machine") else "the path is not there: not mounted, or moved"
    if not (path / "CLAUDE.md").is_file():
        return "UNREACHABLE", "the path holds no CLAUDE.md"
    return None


# ========================================================================= the checks

def revision_check(vault, kit, in_development):
    if kit is None:
        return {"verdict": "unverified", "vault": vault_marker(vault),
                "master": None, "entries": []}, []
    rev = revision_block(vault, kit)
    verdict, mine, master = rev["verdict"], rev["vault"], rev["master"]
    entries = sorted(e["revision"] for e in rev["entries"])
    out = {"verdict": verdict, "vault": mine, "master": master, "entries": entries}
    if verdict == "equal":
        return out, []
    if verdict == "behind":
        return out, [finding(
            "revision", f"stamped {mine}, the master {master}: missing {', '.join(entries)}")]
    if verdict == "no-marker":
        return out, [finding(
            "revision", f"no template marker, so every revision up to {master} is unapplied")]
    draft = ", the revision in development in the clone's working tree" \
        if mine == in_development else ""
    return out, [finding(
        "revision", f"stamped {mine}, newer than the master's {master}{draft}: rules, "
        f"integrations, skills and add-on names are not judged against an older master",
        AHEAD)]


def roster_check(vault):
    """A roster with no role on any row is one finding; otherwise one per row without one."""
    rows = roster(vault) or []
    fix = "give each person on the roster a Role: keeper, member or steward"
    if rows and all(r["role"] is None for r in rows):
        return [finding("declarations", "the `## Who writes this vault` roster gives no one a "
                        "role", fix)]
    return [finding("declarations", f"line {r['line']}: {r['person']} has no role on the roster",
                    fix) for r in rows if r["role"] is None]


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
                                     "add `**Type:** <a label for this class of vault>` under "
                                     "the title"))
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


def addon_check(kit, decl, ref):
    named = [("Flavor", decl["flavor"])] + [("Modules", m) for m in decl["modules"]]
    return [finding("declarations", f"`**{label}:**` names `{name}`, and no `addons/{name}/` "
                    f"exists at {ref}", "correct the name, or remove it from the line")
            for label, name in named if name and not addon_root(kit.clone, kit.commit, name)]


def rule_files(vault):
    folder = vault / ".claude" / "rules"
    return {p.name for p in folder.glob("*.md")} if folder.is_dir() else set()


def contract_check(vault):
    """One finding per break of para-shared/rule-files.md in each rule file on disk: no
    `paths:` list in its frontmatter, or a shape file with no `## Placeholders`."""
    found = []
    for name in sorted(rule_files(vault)):
        lines = read_lines(vault / ".claude" / "rules" / name)
        rel = f"`.claude/rules/{name}`"
        end = lines.index("---", 1) if lines[:1] == ["---"] and "---" in lines[1:] else None
        if end is None or not PATHS_RE.search("\n".join(lines[1:end])):
            found.append(finding("rules", f"{rel} has " + (
                "no frontmatter" if end is None else "no `paths:` list in its frontmatter")
                + ", so Claude Code loads it in every session",
                f"give it a `paths:` frontmatter list of the globs it governs, {CONTRACT}"))
        body = [text.strip() for _, text in live_lines(lines[(end or -1) + 1:])]
        if any(t.startswith("**Order:**") or t == "## The shape" for t in body) and \
                "## Placeholders" not in body:
            found.append(finding("rules", f"{rel} is a shape file with no `## Placeholders`",
                                 f"close it on `## Placeholders` stating this vault's "
                                 f"convention, {CONTRACT}"))
    return found


def rules_check(vault, rows):
    found = [r for r in rows if r["kind"] == "rule" and r["state"] not in ("current", "edited")]
    return [finding("rules", f"`{r['path']}` is {STATES[r['state']]}"
                    + (f"; the master ships it as `{r['master']}`" if r["master"] else ""))
            for r in found] + contract_check(vault)


def integration_check(rows, ref):
    found = []
    for r in rows:
        if r["state"] == "no-master":
            found.append(finding("integrations", f"`{r['path']}` names an integration {ref} "
                                 f"does not ship", "check the integration name in its marker"))
        else:
            found.append(finding("integrations", f"`{r['path']}` is {STATES[r['state']]} "
                                 f"against `{r['master'] or ref}`"))
    return found


def skill_check(vault, rows, ref):
    """One finding per bundled skill folder the table flags, then per bundled `para-*`
    folder no master ships."""
    by_skill = {}
    for r in rows:
        by_skill.setdefault(r["path"].split("/")[2], []).append(r)
    unknown = [d.name for d in sorted((vault / ".claude" / "skills").glob("para-*"))
               if d.is_dir() and d.name not in by_skill]
    found = [finding("skills", f"`.claude/skills/{name}` holds {state_counts(flagged)}")
             for name, flagged in sorted((n, [r for r in g if r["state"] != "current"])
                                         for n, g in by_skill.items()) if flagged]
    return found + [finding("skills", f"`.claude/skills/{name}` is a para-os name no master "
                            f"ships at {ref}") for name in unknown]


def audit_vault(entry, kit, ref, in_development):
    """The vault's `revision` block and its `findings`, in the order of the checks."""
    vault = Path(entry["path"]).resolve()
    revision, found = revision_check(vault, kit, in_development)
    declared, resolvable = declaration_check(vault, declarations(vault))
    found += declared + roster_check(vault)
    if revision["verdict"] not in ("ahead", "unverified"):
        rows = files_block(vault, kit, resolvable)
        found += addon_check(kit, resolvable, ref) + rules_check(vault, rows)
        found += integration_check([r for r in rows if r["kind"] == "integration"
                                    and r["state"] != "current"], ref)
        found += skill_check(vault, [r for r in rows if r["kind"] == "skill"], ref)
    if revision["verdict"] == "ahead":
        for f in found:
            if f["route"] == "upgrade":
                f.update(fix=AHEAD, route="operator")
    return {"revision": revision, "findings": found}
