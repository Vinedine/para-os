#!/usr/bin/env python3
"""The mechanical half of /para-archive, as a script instead of instructions.

    py -3 archive_scan.py --vault <path> --entity <name> [--destination <vault-rel path>]
                           [--today YYYY-MM-DD] [--paraos-home <dir>] [--indent N]
    py -3 archive_scan.py --vault <path> --verify --moved-from <old> --moved-to <new>
                           [--routed <vault-rel file>]... [--indent N]

Two read-only modes, one JSON document on stdout each. It never writes to the vault, never
asks, never decides a disposition - every judgment (whether the entity is really done, what
each open action becomes, the version suffix, every write) stays with the skill, per
references/reconcile.md and references/move.md.

Plan mode answers Steps 1 to 6: where the entity is, what its default archive destination is,
whether it sits in a declared lifecycle and what that lifecycle's terminal-stage gate needs,
its open and settled actions, the done-gate's raw material, every inbound reference, and the
move plan.
Verify mode answers Step 8, after the skill has moved the entity by hand: whether anything in
the vault still names the old path, whether every repointed link actually resolves, and what
git shows untracked at the new path.

Reading the vault's primitives - resolving an entity, the registry, header fields, stage
lines, lifecycle tables, tasks, links, snapshots - is not this script's own work:
para-shared/scripts/paraos_vault.py holds it. What lives here is what this skill alone
decides: how a plan's default destination and version suffix are derived, how a `## Backlog`
item is parsed and judged settled, how a lifecycle's reason line is parsed from a vault's own
rule-file prose, how an inbound reference is classified into a real reference versus a
name-only substring, and what a verify pass has to re-check after a move.

What it deliberately does NOT do, so the skill keeps owning it: decide whether the entity is
actually done, choose a disposition for an open action, decide the version suffix, write the
Stage or reason line, or move a single file.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        DATE_RE, H1_RE, H2_RE, HEADING_RE, LINK_ROOTS, NOT_VAULT_CONTENT,
        abspath, blank_spans,
        closed_tasks, extract_links, field_ci, git_untracked, header_fields,
        inbound_references, is_under, lifecycles, link_files, link_spans, live_lines,
        move_plan, open_tasks, parse_date, read_lines, read_text,
        registered_vault, registry, registry_holding, rel_posix, resolve_entity, resolve_link,
        snapshot, stage_line, stage_of, strip_code, vault_root,
    )
except ImportError as missing:  # the skill falls back to scanning by hand
    print(f"archive_scan: {missing}. The shared vault library belongs at "
          f"{SHARED_DIR}/paraos_vault.py: install para-shared beside this skill, or scan "
          f"by hand with the skill's own reference procedure", file=sys.stderr)
    sys.exit(2)


KIND_BY_BUCKET = {"P": "project", "I": "idea", "A": "area"}
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
# The full stop ending a sentence: followed by whitespace or the end, and not closing a
# one-letter abbreviation ("e.g.", "i.e."), which would cut a reason list mid-way.
SENTENCE_END_RE = re.compile(r"(?<!\b\w)\.(?=\s|$)")


# ------------------------------------------------------------------------------ the vault

def vault_block(vault, paraos_home):
    info = vault_root(vault)
    hint = None
    if not info["root"]:
        entry = registered_vault(registry(paraos_home), vault)
        if entry:
            hint = {"name": entry.get("name"), "path": entry.get("path")}
    return {"path": str(vault), "root": info["root"], "missing": info["missing"], "hint": hint}


# ----------------------------------------------------------------------------- the entity

def entity_block(vault, name, paraos_home):
    """resolve_entity() mapped to a kind and, where it did not resolve, everything Step 1
    needs to ask "which one" - the ambiguous candidates, an already-archived hit, this
    vault's own folders, and every other registered vault holding the name."""
    result = resolve_entity(vault, name, buckets=("projects", "resources/ideas", "areas"))
    status = result["status"]
    block = {
        "query": name, "status": status, "kind": None, "source": None,
        "candidates": [], "already_archived": None, "elsewhere": [],
        "other_vaults": [], "this_vault": None,
    }
    if status == "resolved":
        m = result["match"]
        block["kind"] = KIND_BY_BUCKET.get(m["bucket"])
        block["source"] = m["path"]
        return block
    if status == "ambiguous":
        block["candidates"] = result.get("candidates") or []
        return block

    elsewhere = result.get("elsewhere") or []
    archived_hit = next((e for e in elsewhere if e["path"].startswith("archive/")), None)
    block["already_archived"] = archived_hit["path"] if archived_hit else None
    block["elsewhere"] = elsewhere
    block["other_vaults"] = registry_holding(registry(paraos_home), name, exclude=vault)
    ideas_dir, projects_dir = vault / "resources" / "ideas", vault / "projects"
    block["this_vault"] = {
        "projects": sorted(p.name for p in projects_dir.iterdir() if p.is_dir())
                    if projects_dir.is_dir() else [],
        "resources/ideas": sorted(p.name for p in ideas_dir.iterdir() if p.is_dir())
                    if ideas_dir.is_dir() else [],
    }
    return block


def pick_doc(entity_dir):
    """The entity's own record: brief.md first, README.md where the vault's shape gives the
    entity that instead - the opposite priority from a lifecycle's folder-home document,
    which favours README.md, because here it is the entity's *own* shape that decides."""
    brief = entity_dir / "brief.md"
    if brief.is_file():
        return brief
    readme = entity_dir / "README.md"
    return readme if readme.is_file() else None


# ------------------------------------------------------------------------- the destination

def vault_rel_arg(arg):
    """A vault-relative path argument in the one form every comparison here expects:
    surrounding whitespace and slashes dropped, backslashes read as forward slashes - so
    `projects/acme/` and `projects\\acme` name the same folder as `projects/acme`."""
    return arg.strip().replace("\\", "/").strip("/")


def destination_block(vault, kind, folder_name, destination_arg):
    if destination_arg:
        path = vault_rel_arg(destination_arg)
        default = False
    else:
        if kind == "project":
            path = f"archive/projects/{folder_name}"
        elif kind == "idea":
            path = f"archive/ideas/{folder_name}"
        else:
            path = None
        default = True

    block = {"path": path, "default": default,
             "exists": (vault / path).exists() if path else False}
    if kind == "area":
        block["needs_vault_rule"] = path is None
    if kind == "project":
        parent = (vault / path).parent if path else (vault / "archive" / "projects")
        pattern = re.compile(rf"^{re.escape(folder_name)}-v(\d+)$")
        siblings, nums = [], []
        if parent.is_dir():
            for p in sorted(parent.iterdir()):
                if p.is_dir():
                    m = pattern.match(p.name)
                    if m:
                        siblings.append(p.name)
                        nums.append(int(m.group(1)))
        next_n = 1
        while next_n in nums:
            next_n += 1
        block["suffix_siblings"] = siblings
        block["next_suffix"] = next_n
    return block


# --------------------------------------------------------------------------- the lifecycle

def concrete_home(home, folder_name):
    return re.sub(r"<[^>]+>", folder_name, home.rstrip("/"))


def reason_allowed(vault, stage_name):
    """The reason list a vault's own rule-file prose declares for `<stage_name> reason`: the
    **bold** values following "one of" in the paragraph that states the field, per the real
    wording in addons/sales/.claude/rules/deal-brief.md ("A lost deal carries one more
    line ... the reason being one of **no decision**, **timing**, ..."). None where no rule
    file under .claude/rules/ declares one, telling the skill to read the rule file itself.

    Read as raw text (fences skipped, inline code spans kept) rather than through
    strip_code(): the field name is itself quoted in backticks as an illustration
    (`` `**Lost reason:**` ``), and blanking that span would blank the very text this
    parser has to match.
    """
    rules_dir = vault / ".claude" / "rules"
    if not rules_dir.is_dir():
        return None
    field_re = re.compile(r"\*\*\s*" + re.escape(stage_name) + r"\s+reason\s*:?\s*\*\*",
                          re.IGNORECASE)
    for path in sorted(rules_dir.glob("*.md")):
        text = "\n".join(t for _, t in live_lines(read_lines(path)))
        for para in re.split(r"\n\s*\n", text):
            if not field_re.search(para):
                continue
            m = re.search(r"\bone of\b", para, re.IGNORECASE)
            if not m:
                continue
            rest = para[m.end():]
            # A full stop inside a bold value is part of the value, never the sentence's end.
            masked = BOLD_RE.sub(lambda b: "*" * len(b.group(0)), rest)
            end = SENTENCE_END_RE.search(masked)
            scope = rest[:end.start()] if end else rest
            values = [v.strip() for v in BOLD_RE.findall(scope)]
            if values:
                return values
    return None


def lifecycle_block(vault, doc, dest, folder_name):
    """None unless the entity's own Stage line names a stage of a lifecycle the vault
    declares. Otherwise: the lifecycle, every terminal stage with its home made concrete
    for this entity, which terminal stage (if any) the destination matches, whether the
    Stage line already names it, and the reason-gate's raw material for that stage."""
    info = stage_of(doc) if doc else None
    if info is None:
        return None
    matched_lc, matched_stage = None, None
    for lc in lifecycles(vault):
        for s in lc["stages"]:
            if s["name"].strip().lower() == info["name"].strip().lower():
                matched_lc, matched_stage = lc, s
                break
        if matched_lc:
            break
    if not matched_lc:
        return None

    terminal_stages = [
        {"name": s["name"], "home": s["home"],
         "concrete_home": concrete_home(s["home"], folder_name)}
        for s in matched_lc["stages"] if s["terminal"]
    ]

    destination_matches = None
    dest_path = (dest.get("path") or "").rstrip("/")
    if dest_path:
        for t in terminal_stages:
            if t["concrete_home"].rstrip("/") == dest_path:
                destination_matches = t["name"]
                break

    stage_line_names_destination = bool(
        destination_matches
        and info["name"].strip().lower() == destination_matches.strip().lower())

    reason = None
    if destination_matches:
        field_name = f"{destination_matches} reason"
        raw = field_ci(header_fields(doc), field_name)
        key = raw.split(",", 1)[0].strip() if raw else None
        reason = {"field": field_name, "raw": raw, "key": key,
                   "allowed": reason_allowed(vault, destination_matches)}

    return {
        "heading": matched_lc["heading"], "noun": matched_lc["noun"],
        "current_stage": matched_stage["name"], "terminal_stages": terminal_stages,
        "destination_matches": destination_matches,
        "stage_line_names_destination": stage_line_names_destination,
        "reason": reason,
    }


# ----------------------------------------------------------------------------- the actions

def any_ahead(task, today):
    for key in ("due", "scheduled", "start"):
        d = parse_date(task.get(key))
        if d and d >= today:
            return True
    return False


SETTLE_PATTERNS = (("Done", re.compile(r"\bDone\b")), ("Decided", re.compile(r"\bDecided\b")),
                   ("Resolved", re.compile(r"\bResolved\b")))


def settle_check(text):
    """Whether a Backlog item is settled: a capitalised Done, Decided or Resolved as a whole
    word anywhere in it, case-sensitive, per reconcile.md Step 2. `by` names the leftmost
    match among the three."""
    best = None
    for label, pattern in SETTLE_PATTERNS:
        m = pattern.search(text)
        if m and (best is None or m.start() < best[1]):
            best = (label, m.start())
    return (True, best[0]) if best else (False, None)


TOP_BULLET_RE = re.compile(r"^- (?!\[[ xX]\])(.*)$")
TOP_CHECKBOX_RE = re.compile(r"^[-*+] \[[ xX]\] ")


def backlog_items(path, vault):
    """Every item under a `## Backlog` heading in one file, subheadings inside it included: a
    top-level non-checkbox bullet with its continuation lines, and a paragraph where prose
    stands outside any bullet. A checkbox or a subheading ends the item above it and is never
    one. Fenced content is never an item (live_lines)."""
    if not path.is_file():
        return []
    rel = rel_posix(vault, path)
    lines = read_lines(path)
    section, in_section = [], False
    for lineno, text in live_lines(lines):
        m = H2_RE.match(text)
        if m:
            if in_section:
                break
            in_section = m.group(1).strip().lower() == "backlog"
            continue
        if in_section and H1_RE.match(text):
            break
        if in_section:
            section.append((lineno, text))
    if not section:
        return []

    items = []
    current, bullet, gap = None, False, False
    for lineno, text in section:
        flush = not text[:1].isspace()
        top = TOP_BULLET_RE.match(text) if flush else None
        ends = flush and (TOP_CHECKBOX_RE.match(text) or HEADING_RE.match(text))
        outdented = flush and bullet and gap  # prose after a blank line has left the bullet
        if top or ends or outdented or (not text.strip() and not bullet):
            if current:
                items.append(current)
            current, bullet = None, False
        gap = bullet and not text.strip()
        if top:
            current, bullet = {"line": lineno, "lines": [top.group(1)]}, True
        elif ends or not text.strip():
            continue
        elif current is None:
            current = {"line": lineno, "lines": [text.strip()]}
        else:
            current["lines"].append(text.strip())
    if current:
        items.append(current)

    out = []
    for it in items:
        text = " ".join(it["lines"]).strip()
        settled, by = settle_check(text)
        out.append({"file": rel, "line": it["line"], "text": text, "settled": settled,
                    "by": by})
    return out


def other_checkbox_files(vault, entity_dir, actions_path):
    out = []
    for path in sorted(entity_dir.rglob("*.md")):
        if actions_path and path.resolve() == actions_path.resolve():
            continue
        opens = open_tasks(path)
        if not opens:
            continue
        in_sources = "sources" in path.relative_to(entity_dir).parts[:-1]
        out.append({"file": rel_posix(vault, path), "count": len(opens),
                    "in_sources": in_sources})
    return out


def actions_block(vault, entity_dir, kind, doc, today):
    actions_path = entity_dir / "actions.md"
    has_file = actions_path.is_file()
    rel_actions = rel_posix(vault, actions_path) if has_file else None
    done, open_ = [], []
    if has_file:
        for t in closed_tasks(actions_path):
            done.append(dict(t, file=rel_actions))
        for t in open_tasks(actions_path):
            entry = dict(t, file=rel_actions)
            entry["ahead"] = any_ahead(t, today)
            open_.append(entry)

    backlog = backlog_items(actions_path, vault) if has_file else []
    if doc:
        backlog += backlog_items(doc, vault)

    return {
        "file": rel_actions, "done": done, "open": open_, "backlog": backlog,
        "other_checkbox_files": other_checkbox_files(vault, entity_dir,
                                                      actions_path if has_file else None),
        "idea_holds_actions": bool(kind == "idea" and has_file),
    }


# -------------------------------------------------------------------------------- the gate

def blank_for_date_scan(text):
    """`text` with inline code spans and link *targets* blanked, so a date sitting in a
    target - a filed meeting note's own dated filename, an archive path - is never read as
    a stated future event. A link's display text is prose the operator wrote and still
    counts, as does everything outside a link."""
    out = list(blank_spans(text))
    for start, end, _ in link_spans(text):
        for i in range(start, min(end, len(out))):
            out[i] = " "
    return "".join(out)


def gate_block(doc, open_tasks_list, today):
    raw_status = None
    future_lines = []
    if doc:
        raw_status = field_ci(header_fields(doc), "Status")
        if raw_status is None:
            raw_status = stage_line(doc)
        for lineno, text in live_lines(read_lines(doc)):
            scan_text = blank_for_date_scan(text)
            for m in DATE_RE.finditer(scan_text):
                d = parse_date(m.group(0))
                if d and d > today:
                    future_lines.append({"line": lineno, "text": text})
                    break

    open_dated = [t for t in open_tasks_list
                  if t.get("due") or t.get("scheduled") or t.get("start")]
    return {"status_line": raw_status, "open_dated": open_dated,
            "future_dated_lines": future_lines}


# ----------------------------------------------------------------------------- the inbound

def boundary(c):
    return c == "" or not (c.isalnum() or c in "-_")


def whole_segment_match(text, name):
    """Whether `name` occurs in `text` with a path boundary on both sides - so
    "acme-website-v2" is never mistaken for a reference to "acme"."""
    start = 0
    while True:
        at = text.find(name, start)
        if at < 0:
            return False
        end = at + len(name)
        before = text[at - 1] if at > 0 else ""
        after = text[end] if end < len(text) else ""
        if boundary(before) and boundary(after):
            return True
        start = end


def routed_inbound(vault, entity_dir, route_files):
    """`{route: [hit, ...]}` for each `--route` file: every inbound reference to its bare
    filename, minus hits inside the entity folder itself. Step 4 decides what routes to
    `resources/` only after Step 0 has already run once, so this is a second, narrower call
    the skill makes once that decision exists - the mention may name only the file (a
    backtick citation, a bare filename in prose) and never the entity's own folder name at
    all, which `inbound_references(vault, folder_name)` alone would miss entirely."""
    entity_rel = rel_posix(vault, entity_dir)
    routed = {}
    for route in route_files:
        name = Path(route).name
        hits = []
        for hit in inbound_references(vault, name):
            if hit["file"] == entity_rel or hit["file"].startswith(entity_rel + "/"):
                continue
            hits.append(hit)
        routed[route] = hits
    return routed


def inbound_block(vault, entity_dir, folder_name, route_files=()):
    hits = inbound_references(vault, folder_name)
    entity_rel = rel_posix(vault, entity_dir)
    references, name_only = [], []
    for hit in hits:
        if hit["file"] == entity_rel or hit["file"].startswith(entity_rel + "/"):
            continue
        path = vault / hit["file"]
        decoded = unquote(hit["text"])
        link_under = False
        for _, href, _ in extract_links(decoded):
            target = resolve_link(path, href)
            if is_under(target, entity_dir):
                link_under = True
                break
        entry = dict(hit)
        if link_under or whole_segment_match(decoded, folder_name):
            references.append(entry)
        else:
            name_only.append(entry)

    living = {}
    for path in link_files(vault, LINK_ROOTS):
        if is_under(path, entity_dir):
            continue
        for line, href, raw in extract_links(strip_code(read_text(path))):
            target = resolve_link(path, href)
            if is_under(target, entity_dir) and target.is_file():
                key = rel_posix(vault, target)
                living.setdefault(key, []).append(
                    {"file": rel_posix(vault, path), "line": line})
    living_candidates = [{"file": k, "linked_from": v} for k, v in sorted(living.items())]

    return {"references": references, "name_only": name_only,
            "living_reference_candidates": living_candidates,
            "routed": routed_inbound(vault, entity_dir, route_files)}


# --------------------------------------------------------------------------------- the plan

def build_snapshot(vault, entity_dir, inbound_refs):
    paths = [p for p in entity_dir.rglob("*") if p.is_file()]
    paths += [vault / r["file"] for r in inbound_refs]
    return snapshot(sorted({abspath(p) for p in paths}, key=str))


def plan(vault, entity_name, destination_arg, today, paraos_home, route_files=()):
    vault = Path(vault).resolve()
    report = {
        "vault": vault_block(vault, paraos_home),
        "entity": entity_block(vault, entity_name, paraos_home),
        "destination": None, "lifecycle": None, "actions": None, "gate": None,
        "inbound": None, "move_plan": None, "snapshot": {},
    }
    if report["entity"]["status"] != "resolved":
        return report, 0

    kind = report["entity"]["kind"]
    source = report["entity"]["source"]
    entity_dir = vault / source
    folder_name = entity_dir.name

    dest = destination_block(vault, kind, folder_name, destination_arg)
    report["destination"] = dest

    doc = pick_doc(entity_dir)
    report["lifecycle"] = lifecycle_block(vault, doc, dest, folder_name)

    actions = actions_block(vault, entity_dir, kind, doc, today)
    report["actions"] = actions

    report["gate"] = gate_block(doc, actions["open"], today)

    inbound = inbound_block(vault, entity_dir, folder_name, route_files)
    report["inbound"] = inbound

    report["move_plan"] = move_plan(vault, source, dest["path"]) if dest["path"] else None
    report["snapshot"] = build_snapshot(vault, entity_dir, inbound["references"])
    return report, 0


# ------------------------------------------------------------------------------- the verify

def stale_links(vault, moved_from):
    old_dir = abspath(vault / moved_from)
    out = []
    for path in sorted(vault.rglob("*.md")):
        rel = rel_posix(vault, path)
        if any(rel == e or rel.startswith(e + "/") for e in NOT_VAULT_CONTENT):
            continue
        for line, href, raw in extract_links(strip_code(read_text(path))):
            target = resolve_link(path, href)
            if is_under(target, old_dir):
                out.append({"file": rel, "line": line, "href": href,
                            "resolved": rel_posix(vault, target)})
    return out


def relative_start(before):
    """Whether a vault-relative path can begin right after `before`: at a word boundary, or
    after a `../` or `./` climb. After a named folder (`archive/projects/x`) it is part of a
    different, longer path."""
    last = before[-1:]
    if not last:
        return True
    if last.isalnum() or last in "-_.":
        return False
    if last not in ("/", "\\"):
        return True
    return re.split(r"[/\\]", before[:-1])[-1].lstrip("(<`'\" ") in ("..", ".", "")


def stale_mentions(vault, moved_from, moved_to):
    """Every plain-text occurrence of the old path (link display text, a backtick path, bare
    prose) that carries a path boundary on both sides, excluding an occurrence that is part of
    the new path or of another path ending in it - so "archive/projects/x" is never read as a
    mention of "projects/x", and "archive/projects/x-v1" is not either, since both contain it
    as a substring."""
    out, exempt = [], []
    for path in sorted(vault.rglob("*.md")):
        rel = rel_posix(vault, path)
        if any(rel == e or rel.startswith(e + "/") for e in NOT_VAULT_CONTENT):
            continue
        in_sources = "sources" in Path(rel).parts[:-1]
        for lineno, text in live_lines(read_lines(path)):
            decoded = unquote(text)
            new_spans = [(m.start(), m.end())
                        for m in re.finditer(re.escape(moved_to), decoded)]
            start = 0
            while True:
                at = decoded.find(moved_from, start)
                if at < 0:
                    break
                end = at + len(moved_from)
                start = end
                if any(s <= at and end <= e for s, e in new_spans):
                    continue
                after = decoded[end] if end < len(decoded) else ""
                if after and (after.isalnum() or after in "-_"):
                    continue
                if not relative_start(decoded[:at]):
                    continue
                entry = {"file": rel, "line": lineno, "text": text}
                (exempt if in_sources else out).append(entry)
    return out, exempt


def inbound_resolved(vault, moved_to):
    new_dir = abspath(vault / moved_to)
    resolved, unresolved = 0, []
    for path in sorted(vault.rglob("*.md")):
        rel = rel_posix(vault, path)
        if any(rel == e or rel.startswith(e + "/") for e in NOT_VAULT_CONTENT):
            continue
        if is_under(path, new_dir):
            continue
        for line, href, raw in extract_links(strip_code(read_text(path))):
            target = resolve_link(path, href)
            if not is_under(target, new_dir):
                continue
            if target.exists():
                resolved += 1
            else:
                unresolved.append({"file": rel, "line": line, "href": href,
                                   "resolved": rel_posix(vault, target)})
    return {"resolved": resolved, "unresolved": unresolved}


def inside_links(vault, moved_to, routed):
    """Links inside the moved folder and each routed file. A routed path that names no file
    is listed under `missing` rather than skipped: it was never read, so it is not clean."""
    new_dir = abspath(vault / moved_to)
    files = sorted(new_dir.rglob("*.md")) if new_dir.is_dir() else []
    missing = [vault_rel_arg(r) for r in routed if not (vault / r).is_file()]
    files += [vault / r for r in routed if (vault / r).is_file()]
    resolved, dangling = 0, []
    for path in files:
        rel = rel_posix(vault, path)
        for line, href, raw in extract_links(strip_code(read_text(path))):
            target = resolve_link(path, href)
            if target.exists():
                resolved += 1
            else:
                dangling.append({"file": rel, "line": line, "href": href,
                                 "resolved": rel_posix(vault, target)})
    return {"resolved": resolved, "dangling": dangling, "missing": missing}


def old_path_block(vault, moved_from):
    old_dir = vault / moved_from
    exists = old_dir.exists()
    empty = exists and old_dir.is_dir() and not any(old_dir.iterdir())
    return {"exists": exists, "empty": empty}


def verify(vault, moved_from, moved_to, routed):
    vault = Path(vault).resolve()
    # Normalised as plan mode normalises --destination: `projects/acme/` or `projects\\acme`
    # otherwise matches no written mention and the pass reads a false clean.
    moved_from, moved_to = vault_rel_arg(moved_from), vault_rel_arg(moved_to)
    s_links = stale_links(vault, moved_from)
    s_mentions, s_exempt = stale_mentions(vault, moved_from, moved_to)
    inbound = inbound_resolved(vault, moved_to)
    inside = inside_links(vault, moved_to, routed)
    clean = (not s_links and not s_mentions and not inbound["unresolved"]
             and not inside["dangling"] and not inside["missing"])
    return {
        "vault": vault.as_posix(), "moved_from": moved_from, "moved_to": moved_to,
        "stale_links": s_links, "stale_mentions": s_mentions,
        "stale_mentions_exempt": s_exempt, "inbound_resolved": inbound, "inside": inside,
        "old_path": old_path_block(vault, moved_from),
        "untracked": git_untracked(vault, moved_to), "clean": clean,
    }, 0


# ------------------------------------------------------------------------------ entry point

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Scan a vault for /para-archive's mechanical checks, plan or verify.")
    ap.add_argument("--vault", default=".", help="vault root (default: current directory)")
    ap.add_argument("--entity", help="the project, idea or area to archive (plan mode)")
    ap.add_argument("--destination", help="a vault-relative destination overriding the default")
    ap.add_argument("--today", help="date to measure against (default: the system date)")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    ap.add_argument("--verify", action="store_true", help="verify mode, after the move")
    ap.add_argument("--moved-from", help="vault-relative old path (verify mode)")
    ap.add_argument("--moved-to", help="vault-relative new path (verify mode)")
    ap.add_argument("--routed", action="append", default=[],
                    help="a vault-relative file routed to resources/, repeatable (verify mode)")
    ap.add_argument("--route", action="append", default=[],
                    help="a vault-relative file Step 4 decided to route to resources/, "
                         "repeatable (plan mode, re-run once that decision is made)")
    ap.add_argument("--indent", type=int, default=None, help="pretty-print the JSON")
    args = ap.parse_args(argv)

    # A Windows console and a Windows pipe both default to a codepage that cannot encode a
    # task marker, and the traceback lands where the JSON was meant to be.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if args.verify:
        if not args.moved_from or not args.moved_to:
            ap.error("--verify needs --moved-from and --moved-to")
    elif not args.entity:
        ap.error("--entity is required outside --verify")

    # A path that does not exist at all is answered the same way as one that exists but is
    # not a vault root - vault_root() reads it as "everything is missing" - rather than
    # exiting 2 with bare usage text and no JSON, which is a different failure shape for a
    # typo'd or stale path than for every other non-root case.
    root = Path(args.vault).resolve()

    info = vault_block(root, args.paraos_home)
    if not info["root"]:
        json.dump({"vault": info}, sys.stdout, ensure_ascii=False, indent=args.indent)
        sys.stdout.write("\n")
        hint = f" (registry: {info['hint']['name']} at {info['hint']['path']})" \
            if info["hint"] else ""
        print(f"archive_scan: not a vault root: {root} (missing "
              f"{', '.join(info['missing'])}){hint}", file=sys.stderr)
        return 3

    if args.verify:
        report, code = verify(root, args.moved_from, args.moved_to, args.routed)
    else:
        today = parse_date(args.today) if args.today else date.today()
        if args.today and not today:
            ap.error("--today wants YYYY-MM-DD")
        report, code = plan(root, args.entity, args.destination, today, args.paraos_home,
                           args.route)

    json.dump(report, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
