#!/usr/bin/env python3
"""The mechanical half of /para-pipeline, as a script instead of instructions.

    py -3 pipeline_scan.py --vault <path> [--lifecycle <name>] [--today YYYY-MM-DD] [--indent N]
    python3 pipeline_scan.py --vault <path>

Prints one JSON document on stdout: every lifecycle the vault's CLAUDE.md declares, the
entities collected from the union of each stage's home, each entity's stage, days in stage,
next step and flag inputs, the counts by stage, and the quarter's metrics. It never writes
to the vault and never ranks or words anything an operator reads - that stays with the
skill, per references/scan.md and references/render.md.

Why a script. Those two files describe a mechanical read: which folder or row belongs to
which stage, where a next step lives, which dates fall in a quarter. Two correct runs have
to agree, and instructions re-derived per run do not, so this pins the rules the same way
brief_scan.py pins /para-daily-brief's.

Reading the vault's primitives - Stage lines, header fields, register rows, lifecycle
tables, open tasks - is not this script's own work: para-shared/scripts/paraos_vault.py
holds it. What lives here is what this skill alone decides: how a lifecycle's declared
homes turn into entities, how a next step is chosen among the sources scan.md orders, which
flags fire, and how the quarter's metrics are counted.

What it deliberately does NOT do, so the skill keeps owning it: rank or cap entities, word a
flag into a sentence, render the board, or choose the single closing next action.
"""

import argparse
import calendar
import json
import re
import statistics
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        DATE_RE, H1_RE, field_ci, first_link, header_fields, is_live, iso,
        lifecycles, live_lines, open_tasks, parse_date, read_lines,
        register_rows, stage_of, stage_parts,
    )
except ImportError as missing:  # the skill falls back to scanning by hand
    print(f"pipeline_scan: {missing}. The shared vault library belongs at "
          f"{SHARED_DIR}/paraos_vault.py: install para-shared beside this skill, or scan "
          f"by hand with references/scan.md", file=sys.stderr)
    sys.exit(2)

STALE_DAYS = 14      # no movement in this many days, by last touch or by stage
EXPIRING_DAYS = 14   # a dated fact due within this many days, and still ahead

# The header fields that make a document with no Stage line, or one naming no declared
# stage, worth reporting (no_stage, unknown_stage), matched case-insensitively by field_ci - scan.md's narrowing rule.
NO_STAGE_FIELDS = ("opened", "source", "champion", "signer", "value", "last touch", "won")


# --------------------------------------------------------------------------------- reading

def extract_date(text):
    """The date a field carries: the whole value where it is exactly one, else the first
    YYYY-MM-DD found in it (a `Last touch` or `Next step` cell reads `<date>, <what
    happened>`)."""
    if not text:
        return None
    exact = parse_date(text.strip())
    if exact:
        return exact
    m = DATE_RE.search(text)
    return parse_date(m.group(0)) if m else None


def pick_doc(folder):
    """README.md over brief.md when a folder holds both - scan.md's duplicate-document
    rule."""
    readme, brief = folder / "README.md", folder / "brief.md"
    if readme.is_file():
        return readme
    if brief.is_file():
        return brief
    return None


def doc_h1(path):
    """A document's own title, for scoping which of a contact file's tasks are candidates
    (scan.md Step 4 rule 3): open_tasks() gives a task this same H1 as its section when it
    sits under Next actions or under no H2 at all, and its H2 text otherwise."""
    for _, text in live_lines(read_lines(path)):
        m = H1_RE.match(text)
        if m:
            return m.group(1).strip()
    return None


# The homes base gives an ordinary project, area or idea (CLAUDE.md.template), as globs.
ORDINARY_HOMES = {"projects/*", "areas/*", "resources/ideas/*", "archive/projects/*",
                  "archive/ideas/*"}


def home_is_lifecycle_only(home):
    """Whether no ordinary project, area or idea can occupy a home - scan.md's narrowing
    rule (b): a document there with no Stage line, or one naming no declared stage, is a
    filing gap even with nothing else marking it as staged (issue #67)."""
    return re.sub(r"<[^>]+>", "*", home.rstrip("/")) not in ORDINARY_HOMES


def other_actions_files(vault):
    """Every actions.md a next step (rule 2) may be filed in: any actions.md at any depth
    under projects/ or areas/ (scan.md Step 3), so a sub-area's own file counts, never a
    contact file and never archive/ or resources/. Sorted per bucket, projects/ first."""
    files = []
    for bucket in ("projects", "areas"):
        files += sorted(p for p in (vault / bucket).rglob("actions.md") if p.is_file())
    return files


def tag_tasks(vault, path):
    return [dict(t, file=path.relative_to(vault).as_posix()) for t in open_tasks(path)]


def resolve_link(base_dir, link):
    try:
        return (base_dir / unquote(link.split("#", 1)[0])).resolve()
    except (OSError, ValueError):
        return None


def dated_facts_out(raw_facts, today):
    out = []
    for clause, date_str in raw_facts:
        d = parse_date(date_str)
        out.append({"clause": clause, "date": iso(d),
                     "days_ahead": (d - today).days if d else None})
    return out


# --------------------------------------------------------------------------- the next step

def effective_date(task):
    return parse_date(task.get("due")) or parse_date(task.get("scheduled"))


def pick_next(tasks):
    """The earliest-dated open item, undated ones after every dated one - scan.md Step 4's
    selection rule, shared by every source it names."""
    dated = sorted((t for t in tasks if effective_date(t)), key=effective_date)
    undated = [t for t in tasks if not effective_date(t)]
    ordered = dated + undated
    return ordered[0] if ordered else None


def make_next_step(task, source, today):
    d = effective_date(task)
    return {"text": task["text"], "date": iso(d), "days": (d - today).days if d else None,
            "file": task["file"], "line": task["line"], "source": source}


def champion_step(vault, today, context_dir, fields):
    """Rule 3: the champion's contact file, followed exactly as linked. No link, or a link
    resolving to nothing, is the no-next-step case here, never a name to search for. Only
    tasks under the file's own title or its Next actions heading are candidates - the ones
    open_tasks() gives the document's own H1 as their section - so a task filed under any
    other heading (a History log, say) is never picked."""
    champion_raw = field_ci(fields, "Champion")
    if not champion_raw:
        return None
    link = first_link(champion_raw)
    if not link:
        return None
    resolved = resolve_link(context_dir, link)
    if not resolved or not resolved.is_file():
        return None
    h1 = doc_h1(resolved)
    candidates = [t for t in tag_tasks(vault, resolved) if t["section"] in (None, h1)]
    picked = pick_next(candidates)
    return make_next_step(picked, "champion", today) if picked else None


def next_step_for_folder(vault, today, doc, fields, other_files):
    own = doc.parent / "actions.md"
    if own.is_file() and is_live(own.relative_to(vault)):
        picked = pick_next(tag_tasks(vault, own))
        if picked:
            return make_next_step(picked, "own_actions", today)

    target = doc.resolve()
    candidates = []
    for f in other_files:
        for t in tag_tasks(vault, f):
            link = t.get("first_link")
            if link and resolve_link(f.parent, link) == target:
                candidates.append(t)
    picked = pick_next(candidates)
    if picked:
        return make_next_step(picked, "linked_checkbox", today)

    return champion_step(vault, today, doc.parent, fields)


# A date the wording attaches to a register row's step, ranked: a 📅 marker, `by` before it,
# `on` before it, the date closing the cell. The highest-ranked match wins wherever it sits.
# A date anywhere else in the prose is not the due date. `by` and `on` may carry a weekday.
WEEKDAY = r"(?:(?:mon|tues?|wed(?:s|nes)?|thu(?:rs?)?|fri|sat(?:ur)?|sun)(?:day)?\.?,?\s+)?"
STEP_DATE_RES = [re.compile(p, re.IGNORECASE) for p in (
    r"📅️?\s*(\d{4}-\d{2}-\d{2})", r"\bby\s+" + WEEKDAY + r"(\d{4}-\d{2}-\d{2})",
    r"\bon\s+" + WEEKDAY + r"(\d{4}-\d{2}-\d{2})", r"(\d{4}-\d{2}-\d{2})\W*$")]


def step_date(text):
    for rx in STEP_DATE_RES:
        m = rx.search(text)
        if m:
            return parse_date(m.group(1))
    return None


def next_step_for_row(vault, today, reg_path, row, header_cols):
    fields = {k: row[k] for k in header_cols}
    step = champion_step(vault, today, reg_path.parent, fields)
    if step:
        return step

    next_key = next((k for k in header_cols if k.strip().lower() == "next step"), None)
    text = (row.get(next_key) or "").strip() if next_key else ""
    if text in ("", "-") or text.lower().startswith("none planned"):
        return None
    d = step_date(text)
    return {"text": text, "date": iso(d), "days": (d - today).days if d else None,
            "file": reg_path.relative_to(vault).as_posix(), "line": row.get("line"),
            "source": "register_row"}


# -------------------------------------------------------------------------------- the flags

def build_flags(entity, next_step, stage_idx, today):
    fields = entity["fields"]
    signer_raw = field_ci(fields, "Signer")
    signer_unknown = bool(signer_raw and signer_raw.strip().lower() == "unknown"
                          and stage_idx >= 1)
    expiring = [f for f in entity["dated_facts"]
                if f["days_ahead"] is not None and 0 <= f["days_ahead"] <= EXPIRING_DAYS]

    last_touch_date = parse_date(entity["last_touch"]["date"])
    since_date = parse_date(entity["since"])
    if last_touch_date:
        basis, days = "last_touch", (today - last_touch_date).days
    elif since_date:
        basis, days = "stage", (today - since_date).days
    else:
        basis, days = None, None

    stale = None
    if basis and days is not None and days >= STALE_DAYS:
        # An undated next step, or none at all, never suppresses the flag - only a dated
        # step that has not yet arrived does (finding 4 of the 20260921-2035 test run).
        still_ahead = False
        if next_step and next_step.get("date"):
            nd = parse_date(next_step["date"])
            still_ahead = bool(nd and nd >= today)
        if not still_ahead:
            stale = {"basis": basis, "days": days}

    return {"no_next_step": next_step is None, "stale": stale, "expiring": expiring,
            "signer_unknown": signer_unknown, "name_collision": False}


def apply_name_collision(entities):
    """Two live entities sharing a name across homes. A name recovered from the Contact
    column (finding 1) is excluded from the check on both sides: an `unknown` Company cell
    would otherwise collide every row against every other before the fallback runs."""
    groups = {}
    for e in entities:
        if e["live"] and e["name_from"] is None:
            groups.setdefault(e["name"].strip().lower(), []).append(e)
    for group in groups.values():
        if len(group) >= 2:
            for e in group:
                e["flags"]["name_collision"] = True


# --------------------------------------------------------------------- collecting entities

def collect_folder_entities(vault, home, stage_by_name, stage_index, other_files, today):
    pattern = re.sub(r"<[^>]+>", "*", home.rstrip("/"))
    dirs = sorted(p for p in vault.glob(pattern) if p.is_dir())
    entities, no_stage, unknown_stage = [], [], []
    if not dirs:
        return entities, no_stage, unknown_stage, True
    lifecycle_only = home_is_lifecycle_only(home)

    for d in dirs:
        doc = pick_doc(d)
        if not doc:
            continue
        info = stage_of(doc)
        matched = info and stage_by_name.get(info["name"].strip().lower())
        if not matched:
            path = doc.relative_to(vault).as_posix()
            fielded = any(field_ci(header_fields(doc), f) is not None for f in NO_STAGE_FIELDS)
            if info is None and (lifecycle_only or fielded):
                no_stage.append(path)
            elif info is not None and (lifecycle_only or fielded):
                unknown_stage.append({"path": path, "stage": info["name"]})
            continue

        idx = stage_index[matched["name"].lower()]
        fields = header_fields(doc)
        actual_dir = d.relative_to(vault).as_posix()
        declared_dir = re.sub(r"<[^>]+>", d.name, matched["home"].rstrip("/"))
        home_mismatch = (None if actual_dir == declared_dir else
                         {"declared": matched["home"], "actual": actual_dir})

        since_date = parse_date(info["since"])
        opened_date = extract_date(field_ci(fields, "Opened"))
        last_touch_date = extract_date(field_ci(fields, "Last touch"))
        closed = matched["terminal"]

        entity = {
            "name": d.name, "name_from": None,
            "path": doc.relative_to(vault).as_posix(), "line": None, "kind": "folder",
            "section": None,
            "stage": matched["name"], "terminal": matched["terminal"], "closed": closed,
            "live": not closed,
            "duplicate_document": (d / "brief.md").is_file() and (d / "README.md").is_file(),
            "days_in_stage": (today - since_date).days if since_date else None,
            "since": iso(since_date), "since_from": None, "qualifier": info["qualifier"],
            "dated_facts": dated_facts_out(info["dated_facts"], today), "fields": fields,
            "opened": iso(opened_date), "source": field_ci(fields, "Source"),
            "last_touch": {"date": iso(last_touch_date),
                           "days": (today - last_touch_date).days if last_touch_date else None},
            "home_mismatch": home_mismatch, "row_missing_columns": False,
        }
        if entity["live"]:
            step = next_step_for_folder(vault, today, doc, fields, other_files)
            entity["next_step"] = step
            entity["flags"] = build_flags(entity, step, idx, today)
        else:
            entity["next_step"] = None
            entity["flags"] = None
        entities.append(entity)
    return entities, no_stage, unknown_stage, False


def name_label(cell):
    """A name cell reduced to its label: a link to its text, then a trailing note dropped.
    "Acme NV ([acme.example](https://acme.example))" is Acme NV, "Jan Janssen (via a
    partner)" is Jan Janssen."""
    text = strip_links(cell or "").strip()
    return re.sub(r"\s+\(.*\)$", "", text) or text


def collect_row_entities(vault, home, stage_by_name, stage_index, today):
    reg_path = vault / home
    if not reg_path.is_file():
        return [], True
    rows = register_rows(reg_path)
    if not rows:
        return [], True

    entities = []
    for row in rows:
        header_cols = [k for k in row.keys() if k not in ("name", "section", "line", "cells")]
        stage_raw = re.sub(r"[*_]", "", field_ci(row, "Stage") or "").strip()
        if not stage_raw:
            continue
        info = stage_parts(stage_raw, stage_raw)
        matched = stage_by_name.get(info["name"].strip().lower())
        if not matched:
            continue
        idx = stage_index[matched["name"].lower()]
        home_mismatch = (None if matched["row"] else
                         {"stage_home": matched["home"],
                          "found_in": reg_path.relative_to(vault).as_posix()})

        name_val, name_from = name_label(row.get("name", "")), None
        if name_val.strip().lower() == "unknown":
            contact_key = next((k for k in header_cols if k.strip().lower() == "contact"), None)
            if contact_key is None and len(header_cols) > 1:
                contact_key = header_cols[1]
            name_val = name_label(row.get(contact_key, "")) if contact_key else name_val
            name_from = "contact"

        closed = matched["terminal"] or ((row.get("section") or "").strip().lower() == "closed")
        if closed:
            home_mismatch = None   # a closed row records where the lead went, not a filing gap
        opened_raw = field_ci(row, "Opened")
        opened_date = extract_date(opened_raw)
        since_str, since_from = info["since"], None
        if not since_str and idx == 0 and opened_raw:
            since_str, since_from = opened_raw, "opened"   # finding 3
        since_date = extract_date(since_str) if since_str else None
        last_touch_date = extract_date(field_ci(row, "Last touch"))

        entity = {
            "name": name_val, "name_from": name_from,
            "path": reg_path.relative_to(vault).as_posix(), "line": row.get("line"),
            "kind": "row", "section": row.get("section"),
            "stage": matched["name"], "terminal": matched["terminal"],
            "closed": closed, "live": not closed, "duplicate_document": False,
            "days_in_stage": (today - since_date).days if since_date else None,
            "since": iso(since_date), "since_from": since_from, "qualifier": info["qualifier"],
            "dated_facts": dated_facts_out(info["dated_facts"], today),
            "fields": {k: row[k] for k in header_cols},
            "opened": iso(opened_date), "source": field_ci(row, "Source"),
            "last_touch": {"date": iso(last_touch_date),
                           "days": (today - last_touch_date).days if last_touch_date else None},
            "home_mismatch": home_mismatch,
            "row_missing_columns": row["cells"] < len(header_cols),
        }
        if entity["live"]:
            step = next_step_for_row(vault, today, reg_path, row, header_cols)
            entity["next_step"] = step
            entity["flags"] = build_flags(entity, step, idx, today)
        else:
            entity["next_step"] = None
            entity["flags"] = None
        entities.append(entity)
    return entities, False


def collect_entities(vault, lc, today):
    stages = lc["stages"]
    stage_by_name = {s["name"].lower(): s for s in stages}
    stage_index = {s["name"].lower(): i for i, s in enumerate(stages)}

    homes, seen = [], set()
    for s in stages:
        if s["home"] and s["home"] not in seen:
            seen.add(s["home"])
            homes.append(s)

    other_files = other_actions_files(vault)
    entities, no_stage, unknown_stage, empty_homes = [], [], [], []
    for h in homes:
        if h["row"]:
            found, empty = collect_row_entities(vault, h["home"], stage_by_name, stage_index,
                                                today)
        else:
            found, missing, unknown, empty = collect_folder_entities(
                vault, h["home"], stage_by_name, stage_index, other_files, today)
            no_stage += missing
            unknown_stage += [u for u in unknown if u not in unknown_stage]
        entities += found
        if empty:
            empty_homes.append(h["home"])

    apply_name_collision(entities)
    return (entities, sorted(set(no_stage)), sorted(unknown_stage, key=lambda u: u["path"]),
            sorted(set(empty_homes)))


# -------------------------------------------------------------------------------- metrics

def quarter_bounds(d):
    q = (d.month - 1) // 3
    start_month = q * 3 + 1
    end_month = start_month + 2
    start = date(d.year, start_month, 1)
    end = date(d.year, end_month, calendar.monthrange(d.year, end_month)[1])
    return start, end


def quarter_name(d):
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def won_outside_homes(vault, promoting_home):
    """An entity carrying a Won date wherever it now sits: the archived mirror of the
    promoting stage's own home, which is outside every declared home once a project ships
    and archives (render.md's Won-date rule). Each record is shaped enough to join the
    opened count and the referrers table (issue #66), and has no stage of its own."""
    pattern = "archive/" + re.sub(r"<[^>]+>", "*", promoting_home.rstrip("/"))
    out = []
    for d in sorted(vault.glob(pattern)):
        if not d.is_dir():
            continue
        doc = pick_doc(d)
        if not doc:
            continue
        fields = header_fields(doc)
        won_date = extract_date(field_ci(fields, "Won"))
        if won_date:
            opened_date = extract_date(field_ci(fields, "Opened"))
            out.append({"name": d.name, "kind": "folder", "stage": None, "closed": True,
                        "path": doc.relative_to(vault).as_posix(), "fields": fields,
                        "opened": iso(opened_date), "source": field_ci(fields, "Source"),
                        "won_date": won_date, "opened_date": opened_date})
    return out


LABELLED_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def strip_links(text):
    return LABELLED_LINK_RE.sub(r"\1", text) if text else text


def referrer_key(vault, e):
    """The Source text before its first comma (finding 2), each link replaced by the title
    of the file it resolves to (its name where it has none), else by its label: two labels
    linking one contact are one referrer (issue #174)."""
    base_dir = (vault / e["path"]).parent

    def name(m):
        target = resolve_link(base_dir, m.group(2))
        if target and target.is_file():
            return doc_h1(target) or target.stem
        return m.group(1)

    return LABELLED_LINK_RE.sub(name, e["source"]).split(",", 1)[0].strip()


def referrers_metrics(vault, entities, q_start, q_end, promoting_name):
    """Grouped by referrer_key, over entities opened this quarter."""
    scoped = [e for e in entities
              if e["opened"] and q_start <= parse_date(e["opened"]) <= q_end]
    groups, unrecorded = {}, {"source": "unrecorded", "entities": 0, "reached_promoting": 0}
    for e in scoped:
        reached = bool(promoting_name and (e["stage"] == promoting_name
                       or extract_date(field_ci(e["fields"], "Won"))))
        src = e["source"]
        if not src or not src.strip():
            unrecorded["entities"] += 1
            unrecorded["reached_promoting"] += 1 if reached else 0
            continue
        key = referrer_key(vault, e)
        g = groups.setdefault(key, {"source": key, "entities": 0, "reached_promoting": 0})
        g["entities"] += 1
        g["reached_promoting"] += 1 if reached else 0
    rows = sorted(groups.values(), key=lambda r: r["source"].lower())
    if unrecorded["entities"]:
        rows.append(unrecorded)
    return rows


def name_key(name):
    return re.sub(r"[^a-z0-9]+", "", strip_links(name or "").lower())


def counted_once(vault, entities):
    """Every entity but a closed register row that records a lead's move to a folder entity,
    so one deal opened and promoted within the quarter is counted once, from its folder. The
    row's Outcome link names the folder; a row with no link resolving to one matches by
    name."""
    folders = [e for e in entities if e["kind"] == "folder"]
    dirs = {(vault / e["path"]).parent.resolve() for e in folders}
    names = {name_key(e["name"]) for e in folders}

    def moved(e):
        if e["kind"] != "row" or not e["closed"]:
            return False
        link = first_link(field_ci(e["fields"], "Outcome") or "")
        target = resolve_link((vault / e["path"]).parent, link) if link else None
        if target and target.exists():
            return target in dirs or target.parent in dirs
        return name_key(e["name"]) in names

    return [e for e in entities if not moved(e)]


def reason_declared(vault, reason_field):
    """Whether a rule file under .claude/rules/ declares the `**<Stage> reason:**` line, so a
    terminal entity without one is a gap rather than a stage that records none (issue #181)."""
    needle = f"**{reason_field}:**".lower()
    return any(needle in p.read_text(encoding="utf-8", errors="replace").lower()
               for p in sorted((vault / ".claude" / "rules").glob("*.md")))


def compute_metrics(vault, today, lc, entities):
    q_start, q_end = quarter_bounds(today)
    stages = lc["stages"]
    promoting = next((s for s in stages if s["home"].startswith("projects/")), None)
    archived_won = won_outside_homes(vault, promoting["home"]) if promoting else []
    once = counted_once(vault, entities + archived_won)

    opened = sum(1 for e in once
                if e["opened"] and q_start <= parse_date(e["opened"]) <= q_end)

    reached_promoting, median_info = None, {"n": 0, "median": None, "values": None}
    if promoting:
        reach_deltas, count = [], 0
        for e in entities:
            if e["stage"] != promoting["name"]:
                continue
            won_date = extract_date(field_ci(e["fields"], "Won"))
            reach_date = won_date or parse_date(e["since"])
            if reach_date and q_start <= reach_date <= q_end:
                count += 1
                opened_date = parse_date(e["opened"])
                if opened_date:
                    reach_deltas.append((reach_date - opened_date).days)
        for w in archived_won:
            if w["won_date"] and q_start <= w["won_date"] <= q_end:
                count += 1
                if w["opened_date"]:
                    reach_deltas.append((w["won_date"] - w["opened_date"]).days)
        reached_promoting = count
        if reach_deltas:
            reach_deltas.sort()
            n = len(reach_deltas)
            median_info = ({"n": n, "median": None, "values": reach_deltas} if n < 3 else
                           {"n": n, "median": statistics.median(reach_deltas), "values": None})

    terminal = {}
    for s in stages:
        if not s["terminal"]:
            continue
        reason_field = f"{s['name']} reason"
        this_q, reasons_q, reasons_all, missing = 0, {}, {}, []
        for e in entities:
            if e["stage"] != s["name"] or not e["closed"]:
                continue
            since_date = parse_date(e["since"])
            in_quarter = bool(since_date and q_start <= since_date <= q_end)
            this_q += 1 if in_quarter else 0
            reason_raw = field_ci(e["fields"], reason_field)
            if not reason_raw or not reason_raw.strip():
                if reason_declared(vault, reason_field):
                    missing.append(e["name"])
                continue
            key = reason_raw.split(",", 1)[0].strip()
            reasons_all[key] = reasons_all.get(key, 0) + 1
            if in_quarter:
                reasons_q[key] = reasons_q.get(key, 0) + 1
        # finding 5: a quarter with no terminal entity still shows what the vault holds.
        terminal[s["name"]] = {"this_quarter": this_q, "reasons_this_quarter": reasons_q,
                               "all_time_reasons": reasons_all, "missing_reason": missing}

    terminal_this_quarter = sum(v["this_quarter"] for v in terminal.values())
    metrics = {
        "quarter": quarter_name(today), "opened": opened,
        "promoting_stage": promoting["name"] if promoting else None,
        "reached_promoting": reached_promoting,
        "median_days_opened_to_promoting": median_info,
        "terminal": terminal,
        "referrers": referrers_metrics(vault, once, q_start, q_end,
                                       promoting["name"] if promoting else None),
    }
    return metrics, terminal_this_quarter


def counts_by_stage(lc, entities):
    counts = {s["name"]: 0 for s in lc["stages"] if not s["terminal"]}
    for e in entities:
        if e["live"] and e["stage"] in counts:
            counts[e["stage"]] += 1
    return [{"stage": name, "count": n} for name, n in counts.items()]


# ------------------------------------------------------------------------------- the report

def scan_lifecycle(vault, lc, today):
    entities, no_stage, unknown_stage, empty_homes = collect_entities(vault, lc, today)
    metrics, terminal_this_quarter = compute_metrics(vault, today, lc, entities)
    return {
        "heading": lc["heading"], "noun": lc["noun"],
        "stages": [s["name"] for s in lc["stages"]],
        "entities": entities, "no_stage": no_stage, "unknown_stage": unknown_stage,
        "empty_homes": empty_homes,
        "counts_by_stage": counts_by_stage(lc, entities),
        "terminal_this_quarter": terminal_this_quarter,
        "metrics": metrics,
    }


def matches_lifecycle(lc, query):
    q = query.strip().lower()
    return q == (lc["noun"] or "").lower() or q == lc["heading"].lower()


def scan(vault, today, lifecycle=None):
    vault = Path(vault).resolve()
    declared = lifecycles(vault)

    report = {"vault": vault.as_posix(), "today": today.isoformat()}
    if lifecycle:
        matched = [lc for lc in declared if matches_lifecycle(lc, lifecycle)]
        if not matched:
            report["error"] = "no such lifecycle"
            report["declared"] = [lc["heading"] for lc in declared]
            return report, 3
        declared = matched

    report["lifecycles"] = [scan_lifecycle(vault, lc, today) for lc in declared]
    return report, 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scan a vault's declared lifecycles.")
    ap.add_argument("--vault", default=".", help="vault root (default: current directory)")
    ap.add_argument("--lifecycle", help="scope to one declared lifecycle, by noun or heading")
    ap.add_argument("--today", help="date to measure against (default: the system date)")
    ap.add_argument("--indent", type=int, default=None, help="pretty-print the JSON")
    args = ap.parse_args(argv)

    # A Windows console and a Windows pipe both default to a codepage that cannot encode a
    # task marker, and the traceback lands where the JSON was meant to be.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    today = parse_date(args.today) if args.today else date.today()
    if args.today and not today:
        ap.error("--today wants YYYY-MM-DD")
    root = Path(args.vault)
    if not root.is_dir():
        ap.error(f"no such vault: {root}")

    report, code = scan(root, today, args.lifecycle)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
