#!/usr/bin/env python3
"""The mechanical half of /para-daily-brief, as a script instead of instructions.

    py -3 tools/../scripts/brief_scan.py --vault <path> [--today YYYY-MM-DD] [--entity <name>]
                                         [--paraos-home <dir>]
    python3 scripts/brief_scan.py --vault <path>

Prints one JSON document on stdout: the vault's open tasks with their markers parsed and
bucketed against a date, the per-entity totals, the health-flag inputs, the ideas lane and
the triage count. It never writes to the vault and never reads a mailbox; outside the vault
it reads only the ledgers of the sources the vault declares, under PARAOS_HOME.

Why a script. references/task-scan.md says "Mechanical: no judgment lives here", and
everything it describes has exactly one right answer: which folder a name resolves to,
which marker a line carries, which side of today a date falls on, which files share an
mtime. Instructions for that are re-derived on every run, cost a round trip each, and
cannot be regression-tested. What stays with the model is what the model is for: ranking
by what the vault's Vision rewards, choosing the one next action, and writing the brief.

Reading the vault is not this script's own work: `para-shared/scripts/paraos_vault.py`
holds it, so the next skill that needs a scan does not write a second one that disagrees.
What lives here is what the brief alone decides: which lane a task falls in against today,
how entities aggregate, and which signals the brief reports.

What it deliberately does NOT do, so the skill keeps owning it: rank, cap, or choose the
next action; read the root README's Vision, any calendar, or any mailbox; render anything
an operator reads.
"""

import argparse
import email
import email.policy
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

# The shared library sits beside this skill, in the skills folder both were installed into.
SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        BRIEF_LINE_CAP, DORMANT_ENTITY_DAYS, FALSELY_OVERDUE_DAYS,
        HEADLINE_CAP, OPEN_ITEM_CAP, STALE_FILE_DAYS, WAITING_FLAG_DAYS, action_files,
        cadence_days, cap_count, waiting_on,
        entity_candidates, field_ci, headline, stray_checkboxes,
        file_dates, is_under, iso, lifecycles, link_spans, live_lines, misplaced_checkboxes,
        open_tasks, read_lines,
        over_grown_briefs, parse_date, register_rows, resolve_entity,
        resolve_link, scope_of, stage_line, stage_of, stage_parts, triage_items,
    )
    from paraos_vault import (  # noqa: E402
        ingest_ledger, paraos_home_dir, same_place, triage_sources,
    )
    from paraos_vault import HEADING_RE, closed_tasks, table_cells  # noqa: E402
except ImportError as missing:  # the skill falls back to scanning by hand
    print(f"brief_scan: {missing}. The shared vault library belongs at "
          f"{SHARED_DIR}/paraos_vault.py: install para-shared beside this skill, or scan "
          f"by hand with references/task-scan.md", file=sys.stderr)
    sys.exit(2)

LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
# signals.md's sentence end, which render_dashboard.py's task cut imports: `e.g. the call`,
# `art. 12` and `€500.000` hold none.
SENTENCE_END_RE = re.compile(r"[.!?](?=\s+[^a-z0-9\s]|\s*$)")
EMPHASIS_RE = re.compile(r"(?<![\w*])([*_])(?![\s*])(.+?)(?<![\s*])\1(?![\w*])")
REVISIT_RE = re.compile(r"\brevisit when\b", re.IGNORECASE)
SENDER_RE = re.compile(r"^(?:[-*]\s+)?\**from\**:\**\s+(.+)$", re.IGNORECASE)
NOTE_FIELD_RE = re.compile(r"^(?:[-*]\s+\**[A-Za-z][\w ]{0,30}\**:|\*\*[A-Za-z][\w ]{0,30}:\*\*)")
BOLD_LINE_RE = re.compile(r"^\*\*[^*]+\*\*:?$")  # a bold line on its own is a heading
# Authentication material, which the dashboard counts and never names (para-shared/
# connectors.md). A backstop for an item that reached triage/ by hand: English phrasings only,
# and a booking or order confirmation code is deliberately not one.
AUTH_RE = re.compile(
    r"\b(?:verification|security|one[- ]time|sign[- ]?in|log[- ]?in|authentication|2fa|mfa)"
    r"[- ](?:code|link|pin|passcode)s?\b|\bmagic[- ]link\b|\bone[- ]time pass(?:word|code)\b"
    r"|\b(?:reset|recover)\b[^.\n]{0,30}\bpassword\b|\bpassword\b[^.\n]{0,30}\b(?:reset|recovery)\b",
    re.IGNORECASE)
PREVIEW_BYTES = 64 * 1024  # a triage item's head: enough for headers and a first paragraph
PREVIEW_CHARS = 240
UNDATED_MAJORITY_MIN = 8  # below this, a new vault's bootstrap actions are not a backlog


# ----------------------------------------------------------- lanes, against today

def bucket_task(task, today):
    """Which lane a task sits in, and how far from today. Recurring beats waiting, waiting
    beats a date, and a start gate that has already opened hides nothing."""
    due = parse_date(task["due"])
    sched = parse_date(task["scheduled"])
    start = parse_date(task["start"])
    effective = due or sched
    task["effective_date"] = iso(effective)
    task["days"] = (effective - today).days if effective else None

    task["also_lane"] = None
    if task["recurring"]:
        task["lane"] = "recurring"
        if effective and effective <= today:
            task["also_lane"] = "overdue" if effective < today else "today"
        return task
    if start and start > today:
        task["lane"] = "waiting"
        return task
    wait = waiting_on(task["text"])
    if wait and not effective:
        since = parse_date(wait["since"])
        task["lane"] = "waiting_on"
        task["waiting_on"] = dict(wait, days=(today - since).days if since else None)
        return task
    if not effective:
        task["lane"] = "undated"
        return task
    delta = (effective - today).days
    if delta < 0:
        task["lane"] = "overdue"
    elif delta == 0:
        task["lane"] = "today"
    elif delta <= 7:
        task["lane"] = "this_week"
    elif delta <= 30:
        task["lane"] = "next_30"
    else:
        task["lane"] = "later"
    return task


def collect_tasks(vault, files):
    tasks = []
    for path in files:
        bucket, scope = scope_of(vault, path)
        rel = path.relative_to(vault).as_posix()
        for task in open_tasks(path):
            task.update({"file": rel, "bucket": bucket, "scope": scope,
                         "person": path.stem if scope == "network" else None})
            tasks.append(task)
    return tasks


def mentions_elsewhere(vault, tasks, match):
    """Open items that name this entity but live in someone else's file. They are
    mentions, never the entity's own work, so they never join its totals.

    Two ways to mention an entity. A link: a target on the task's line, first or any
    further one, that resolves under the entity's folder. Text: only where the entity's
    own name carries a hyphen, dot or space - a multi-token name - does its bare word (or
    its space/dot form) count; a single-token name like `network` or `quill` is too
    common a word to trust as a mention and matches by link alone.
    """
    label = match["label"]
    own = match["path"] + "/"
    entity_dir = Path(vault) / match["path"]
    forms = [label, label.replace("-", " "), label.replace("-", ".")] \
        if re.search(r"[-. ]", label) else []
    patterns = [re.compile(r"(?<![\w-])" + re.escape(f) + r"(?![\w-])", re.IGNORECASE)
                for f in forms]

    out = []
    for t in tasks:
        if t["file"].startswith(own):
            continue
        file_path = Path(vault) / t["file"]
        targets = [t["first_link"]] if t.get("first_link") else []
        targets += [t["text"][a:b].strip() for a, b, _ in link_spans(t["text"])]
        linked = any(is_under(resolve_link(file_path, href), entity_dir)
                     for href in targets if href)
        prose = LINK_TARGET_RE.sub("]", t["text"])  # a link target is judged as a link only
        if linked or any(p.search(prose) for p in patterns):
            out.append(t)
    return out


def aggregate(tasks):
    """One row per entity, with three counts that partition its open count."""
    rows = {}
    for t in tasks:
        row = rows.setdefault((t["bucket"], t["scope"]),
                              {"bucket": t["bucket"], "label": t["scope"], "open": 0,
                               "overdue": 0, "upcoming": 0, "undated": 0, "files": set()})
        row["open"] += 1
        row["files"].add(t["file"])
        if t["lane"] == "overdue":
            row["overdue"] += 1
        elif t["lane"] == "undated":
            row["undated"] += 1
        else:
            row["upcoming"] += 1
    out = []
    for row in rows.values():
        row["files"] = len(row["files"])
        out.append(row)
    out.sort(key=lambda r: (-r["open"], r["label"]))
    top = out[0]["open"] if out else 0
    for row in out:  # filled cells of a 10-wide bar, rounded half-up: 3 of 12 fills 3
        row["bar"] = (20 * row["open"] + top) // (2 * top)
    return out


# --------------------------------------------------------------- signals the brief reports

def short_stage(text):
    """An idea's stage cut to what fits one line: link syntax reduced to its label (a
    target is relative to the brief's folder and breaks when rendered from the vault root)
    and `_x_` / `*x*` emphasis to its text, then the first sentence. Kept here, not in the
    shared `stage_line`, which other skills read uncut."""
    if not text:
        return text
    for start, end, bracket in reversed(link_spans(text)):
        if bracket is not None:
            text = text[:bracket] + text[bracket + 1:start - 2] + text[end + 1:]
    text = EMPHASIS_RE.sub(r"\2", text)
    return text[:first_end(text, SENTENCE_END_RE)].strip()


def first_end(text, end_re):
    """Where `end_re` first matches outside parentheses, else None."""
    depth = 0
    for i, ch in enumerate(text):
        depth += (ch == "(") - (ch == ")")
        if depth <= 0 and end_re.match(text, i):
            return i
    return None


def ideas_lane(vault, today):
    base = Path(vault) / "resources" / "ideas"
    if not base.is_dir():
        return []
    briefs = {d: d / "brief.md" for d in sorted(base.iterdir())
              if d.is_dir() and (d / "brief.md").is_file()}
    dates = file_dates(vault, list(briefs.values()))
    rows = []
    for d, brief in briefs.items():
        touched = dates.get(brief)
        touched_date = parse_date(touched)
        age = (today - touched_date).days if touched_date else None
        stage = stage_of(brief)
        since = parse_date(stage["since"]) if stage else None
        rows.append({"name": d.name, "path": brief.relative_to(vault).as_posix(),
                     "touched": touched, "age_days": age,
                     "stage": short_stage(stage_line(brief)),
                     "since": iso(since) if since else None,
                     "days_in_stage": (today - since).days if since else None,
                     "revisit": revisit_sentence(brief),
                     "dormant": bool(age is not None and age >= DORMANT_ENTITY_DAYS)})
    rows.sort(key=lambda r: r["name"])
    rows.sort(key=lambda r: r["touched"] or "", reverse=True)
    return rows


def revisit_sentence(brief):
    """The brief's one prose "revisit when X" trigger, as the sentence holding it, cut like
    a stage line. None where the brief has none."""
    for _, text in live_lines(read_lines(brief)):
        stripped = text.strip()
        if stripped.startswith(("#", "|", ">")):
            continue
        m = REVISIT_RE.search(stripped)
        if m:
            starts = [e.end() for e in SENTENCE_END_RE.finditer(stripped) if e.end() <= m.start()]
            return short_stage(re.sub(r"^[-*]\s+", "", stripped[starts[-1] if starts else 0:]))
    return None


def triage_preview(vault, names):
    """Who sent each triage item and its first prose lines, read from the file's head: an
    .eml's headers and plain-text body, a note's `From:` field and first paragraph. A PDF
    reads through its extracted markdown twin; any other format has no preview. An item
    holding a sign-in or security code is `{"auth": True}` and nothing else."""
    out = {}
    for name in names:
        if AUTH_RE.search(name):
            out[name] = {"auth": True}
            continue
        path = Path(vault) / "triage" / name
        twin = path.with_suffix(".md")
        if path.suffix.lower() == ".pdf" and twin.is_file():
            path = twin
        try:
            if path.suffix.lower() == ".eml":
                with path.open("rb") as fh:
                    msg = email.message_from_bytes(fh.read(PREVIEW_BYTES),
                                                   policy=email.policy.default)
                body = msg.get_body(preferencelist=("plain",))
                sender, subject = msg["From"], msg["Subject"]
                text = body.get_content() if body else ""
            elif path.suffix.lower() in (".md", ".txt"):
                with path.open("rb") as fh:
                    head = fh.read(PREVIEW_BYTES).decode("utf-8", errors="replace")
                sender, subject, text = note_head(head)
            else:
                continue
        except (OSError, LookupError, ValueError):
            continue
        excerpt = " ".join((text or "").split())
        if AUTH_RE.search(f"{subject or ''} {excerpt}"):
            out[name] = {"auth": True}
            continue
        if len(excerpt) > PREVIEW_CHARS:
            excerpt = excerpt[:PREVIEW_CHARS].rsplit(" ", 1)[0] + "…"
        row = {k: str(v).strip() for k, v in
               (("from", sender), ("subject", subject), ("excerpt", excerpt)) if v}
        if row:
            out[name] = row
    return out


def note_head(head):
    """A staged note's sender (its `From:` field), its H1, and its first prose paragraph:
    the first run of lines that is no heading, field, table, quote, comment or front matter."""
    lines = head.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), 0)
        lines = lines[end + 1:]
    sender = subject = None
    para = []
    for line in lines:
        s = line.strip()
        from_line = SENDER_RE.match(s)
        if from_line and not sender:
            sender = from_line.group(1)
        if s.startswith("# ") and not subject:
            subject = s[2:].strip()
        if not s:
            if para:
                break
            continue
        heading = s.startswith(("#", "|", ">", "<!--", "---")) or BOLD_LINE_RE.match(s)
        if from_line or heading or NOTE_FIELD_RE.match(s):
            if para:
                break
            continue
        para.append(s)
    return sender, subject, LINK_TARGET_RE.sub("]", " ".join(para)).replace("[", "").replace("]", "")


def lifecycle_counts(vault):
    """One entry per declared lifecycle: its heading and the live entity count at each of
    its non-terminal stages. /para-pipeline owns the board and every other field on a
    staged entity; this is the one counts line the brief adds beside it."""
    vault = Path(vault)
    out = []
    for lc in lifecycles(vault):
        stages = [s for s in lc["stages"] if not s["terminal"]]
        by_name = {s["name"].lower(): s for s in stages}
        counts = {s["name"]: 0 for s in stages}
        seen_homes = set()
        for s in stages:
            if s["home"] in seen_homes:
                continue
            seen_homes.add(s["home"])
            if s["row"]:
                reg = vault / s["home"]
                rows = register_rows(reg) if reg.is_file() else []
                for row in rows:
                    if (row.get("section") or "").strip().lower() == "closed":
                        continue
                    raw = re.sub(r"[*_]", "", field_ci(row, "Stage") or "").strip()
                    matched = by_name.get(stage_parts(raw, raw)["name"].lower())
                    if matched:
                        counts[matched["name"]] += 1
            elif s["home"]:
                pattern = re.sub(r"<[^>]+>", "*", s["home"].rstrip("/"))
                for d in sorted(vault.glob(pattern)):
                    if not d.is_dir():
                        continue
                    doc = d / "README.md" if (d / "README.md").is_file() else d / "brief.md"
                    info = stage_of(doc) if doc.is_file() else None
                    matched = by_name.get(info["name"].strip().lower()) if info else None
                    if matched:
                        counts[matched["name"]] += 1
        out.append({"heading": lc["heading"],
                    "counts": [{"stage": s["name"], "count": counts[s["name"]]} for s in stages]})
    return out


def health_flags(vault, tasks, today, per_file_dates, scoped, entity_path=None):
    """Under an entity scope, every flag here is that entity's alone - an over-grown brief
    in an unrelated project is not this entity's problem, so it never shows in this brief."""
    briefs = over_grown_briefs(vault, cap=BRIEF_LINE_CAP, limit=None)
    if scoped and entity_path:
        own = entity_path + "/"
        briefs = [b for b in briefs if b["file"].startswith(own)]
    flags = {"over_threshold": [], "stale_files": [], "falsely_overdue": [],
             "stale_recurrence": [], "undated_majority": None, "misplaced": None,
             "nothing_open": None, "over_grown_briefs": briefs[:3], "long_headlines": [],
             "stray_checkboxes": None, "waiting_too_long": []}

    by_file = {}
    for t in tasks:
        by_file.setdefault(t["file"], []).append(t)

    for name, items in sorted(by_file.items()):
        if cap_count(items) > OPEN_ITEM_CAP:
            flags["over_threshold"].append({"file": name, "open": cap_count(items)})
        touched = parse_date(per_file_dates.get(Path(vault) / name))
        if touched and (today - touched).days >= STALE_FILE_DAYS:
            flags["stale_files"].append({"file": name, "touched": iso(touched),
                                         "days": (today - touched).days,
                                         "open": len(items)})

    for t in tasks:
        wait = t.get("waiting_on")
        if wait and wait["days"] is not None and wait["days"] >= WAITING_FLAG_DAYS:
            flags["waiting_too_long"].append({"file": t["file"], "line": t["line"],
                                              "person": wait["person"], "what": wait["what"],
                                              "days": wait["days"]})
        chars = len(headline(t["text"]))
        if chars > HEADLINE_CAP:
            flags["long_headlines"].append({"file": t["file"], "line": t["line"],
                                            "chars": chars})
        overdue = "overdue" in (t["lane"], t.get("also_lane"))
        if overdue:
            days = -(t["days"] or 0)
            if days > FALSELY_OVERDUE_DAYS:
                flags["falsely_overdue"].append({"file": t["file"], "line": t["line"],
                                                 "days": days, "text": t["text"][:120]})
        if t["recurring"] and overdue:
            period = cadence_days(t["recurring"])
            if period:
                late = -(t["days"] or 0)
                behind = late // period
                if late > period:
                    flags["stale_recurrence"].append(
                        {"file": t["file"], "line": t["line"], "cadence": t["recurring"],
                         "date": t["effective_date"], "periods_behind": behind})
    flags["long_headlines"].sort(key=lambda r: -r["chars"])
    flags["waiting_too_long"].sort(key=lambda r: -r["days"])
    flags["falsely_overdue"].sort(key=lambda r: -r["days"])
    flags["stale_recurrence"].sort(key=lambda r: -r["periods_behind"])

    if not scoped:
        undated = sum(1 for t in tasks if t["lane"] == "undated")
        if len(tasks) >= UNDATED_MAJORITY_MIN and undated * 2 > len(tasks):
            flags["undated_majority"] = {"undated": undated, "open": len(tasks)}
        flags["misplaced"] = misplaced_checkboxes(vault)
        flags["stray_checkboxes"] = stray_checkboxes(vault)
        flags["nothing_open"] = nothing_open(vault, tasks, per_file_dates)
    return flags


NOTE_DATE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})(?!\d)")


def delivered(vault, row, paraos_home):
    """(ledger, dates of what the source delivered to this vault, error) from the source's
    own ledger on this machine, or None where it keeps none here.

    A sync script keeps `{id: path of the note it wrote}` at
    `<PARAOS_HOME>/data/<script name>/synced.json`, an older copy's at `cache/<name>/`, each
    note named from its item's date; a note is this vault's when it was written under it. A
    mailbox's own ledger is `/para-ingest`'s, its threads this vault's when routed to the
    folder's name. `/para-triage`'s seen-ledger is the vault's, not a source's, so a mailbox
    read without ingest has none."""
    home = paraos_home_dir(paraos_home)
    if row["kind"] == "sync-script" and row["path"]:
        name = Path(row["path"].replace("\\", "/")).stem
        ledgers = [p for p in (home / "data" / name / "synced.json",
                               home / "cache" / name / "synced.json") if p.is_file()]
        if not ledgers:
            return None
        mine, places, dates = same_place(vault), {}, []
        for path in ledgers:
            try:
                notes = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(notes, dict):
                    raise ValueError("not an object")
            except (OSError, ValueError):
                return path, [], "unreadable"
            for note in filter(lambda n: isinstance(n, str), notes.values()):
                parent = str(Path(note).parent)
                place = places.setdefault(parent, same_place(parent))
                m = NOTE_DATE_RE.match(Path(note).name)
                if m and (place == mine or place.startswith(mine.rstrip(os.sep) + os.sep)):
                    dates.append(parse_date("-".join(m.groups())))
        return ledgers[0], dates, None
    if row["mailbox"]:
        ledger = ingest_ledger(paraos_home)
        path = home / "cache" / "ingest" / "ledger.json"
        if not ledger["exists"]:
            return None
        if ledger["load_error"]:
            return path, [], "unreadable"
        threads = next((t for box, t in ledger["mailboxes"].items()
                        if box.lower() == row["mailbox"].lower()), {})
        name = Path(vault).name
        return path, [parse_date(str(t.get("seen_date") or t.get("date"))[:10])
                      for t in threads.values()
                      if isinstance(t, dict) and name in (t.get("routed") or [])], None
    return None


def silent_sources(vault, today, paraos_home=None):
    """Every Triage sources row carrying a cadence hint whose newest delivery to this vault
    is older than one cadence, or whose ledger cannot be read: a source gone silent reads
    exactly like a quiet month. A date later than today is corrupt and never counts as the
    newest; a source with no ledger here, or nothing in it for this vault, is not judged."""
    out = []
    for row in triage_sources(vault)["rows"]:
        period = cadence_days(row["cadence"])
        seen = delivered(vault, row, paraos_home) if period else None
        if not seen:
            continue
        ledger, dates, error = seen
        newest = max((d for d in dates if d and d <= today), default=None)
        flag = {"source": re.sub(r"[`*]", "", row["source"]), "cadence": row["cadence"],
                "ledger": ledger.as_posix(), "newest": iso(newest), "days": None}
        if error:
            out.append(dict(flag, error=error))
        elif newest and (today - newest).days > period:
            out.append(dict(flag, days=(today - newest).days))
    out.sort(key=lambda r: -(r["days"] or 10 ** 6))
    return out


def nothing_open(vault, tasks, per_file_dates):
    """Every project and area with no open item anywhere under it, a recurring one counting
    as open: finished, or stalled with no next step. Never `network/`, where a contact who
    is owed nothing is the normal state. An entity with no `actions.md` leads, then the
    oldest one."""
    busy = {(t["bucket"], t["scope"].split("/")[0]) for t in tasks}
    out = []
    for e in entity_candidates(vault):
        if (e["bucket"], e["label"]) in busy or (e["bucket"], e["label"]) == ("A", "network"):
            continue
        own = Path(vault) / e["path"] / "actions.md"
        file = own.relative_to(vault).as_posix() if own.is_file() else None
        out.append({"bucket": e["bucket"], "label": e["label"], "path": e["path"],
                    "file": file, "touched": per_file_dates.get(own) if file else None})
    out.sort(key=lambda r: (r["touched"] or "", r["path"]))
    return out


# ------------------------------------------------------------------------- the review scope
# What closed, slipped, moved and was decided inside a window. Every function here only
# reads: the lanes and flags above are the brief's, and the review adds its own report key.

REVIEW_DAYS = {"week": 7, "month": 30}
# A development log's heading or file name, separators read as spaces and a trailing
# parenthetical dropped: `## Development log (newest first)`, `decision-log.md`, `## Log`.
LOG_NAME_RE = re.compile(r"^(?:(?:development|dev|decisions?) )?log$|^decisions$", re.IGNORECASE)
LOG_ENTRY_RE = re.compile(r"^(?:[-*+]\s+|#{2,6}\s+)?[*_]{0,2}(\d{4}-\d{2}-\d{2})[*_]{0,2}"
                          r"(?![\d-])[\s:,.)\u2013\u2014-]*(.*)$")
NAME_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def review_window(arg, today):
    """The window a `--review` argument names, both ends counted in: `week` is the seven
    days ending today, `month` the thirty, and a YYYY-MM-DD date every day since it. None for
    anything else, a date after today included."""
    key = (arg or "").strip().lower()
    if key in REVIEW_DAYS:
        start, name = today - timedelta(days=REVIEW_DAYS[key] - 1), key
    else:
        start, name = parse_date(key), "since"
        if not start or start > today:
            return None
    return {"name": name, "start": start.isoformat(), "end": today.isoformat(),
            "days": (today - start).days + 1}


def archived_scope(rel):
    """(bucket letter, entity label) for an action file under archive/: the entity it was."""
    parts = Path(rel).parts
    letter = {"projects": "P", "areas": "A", "ideas": "I"}.get(parts[1] if len(parts) > 2 else "")
    return letter or "?", "/".join(parts[2:-1]) or "/".join(parts[1:-1])


def done_in_window(vault, files, archived, start, end):
    """Every close whose `✅` date falls inside the window, one row per entity. A close with no
    date is counted as undated and never placed in any window. An archived file's closes
    count only when dated: its undated ones are the entity's whole history, not this window's."""
    rows, undated = {}, 0
    for path, gone in [(p, False) for p in files] + [(p, True) for p in archived]:
        rel = path.relative_to(vault).as_posix()
        bucket, label = archived_scope(rel) if gone else scope_of(vault, path)
        for task in closed_tasks(path):
            done = parse_date(task["done"])
            if not done:
                undated += not gone
                continue
            if not start <= done <= end:
                continue
            row = rows.setdefault((bucket, label, gone), {
                "bucket": bucket, "label": label, "archived": gone, "count": 0, "items": []})
            row["count"] += 1
            row["items"].append({"file": rel, "line": task["line"], "text": task["text"],
                                 "done": task["done"], "section": task["section"],
                                 "person": path.stem if label == "network" and not gone else None})
    out = sorted(rows.values(), key=lambda r: (-r["count"], r["archived"], r["label"]))
    for row in out:
        row["items"].sort(key=lambda i: (i["done"], i["file"], i["line"]))
    return {"count": sum(r["count"] for r in out), "undated": undated, "by_entity": out}


def slipped(tasks, start, end):
    """Open items whose `📅` fell inside the window, before today: a deadline the window let
    pass. One due today has not slipped yet, and a `⏳` is a plan, not a deadline."""
    out = [{"file": t["file"], "line": t["line"], "bucket": t["bucket"], "scope": t["scope"],
            "person": t["person"], "text": t["text"], "due": t["due"],
            "days_late": (end - parse_date(t["due"])).days, "recurring": t["recurring"]}
           for t in tasks if t["due"] and start <= parse_date(t["due"]) < end]
    out.sort(key=lambda s: (s["due"], s["file"], s["line"]))
    return out


def staged_entities(vault, lc):
    """Every entity in one lifecycle's homes, terminal ones included, read the way
    /para-pipeline reads them: a folder's Stage line, a register row's Stage cell, matched
    against the declared names. A row under a register's `## Closed` is closed."""
    by_name = {s["name"].lower(): s for s in lc["stages"]}
    out, seen = {}, set()
    for s in lc["stages"]:
        if not s["home"] or s["home"] in seen:
            continue
        seen.add(s["home"])
        if s["row"]:
            reg = vault / s["home"]
            for row in register_rows(reg) if reg.is_file() else []:
                raw = re.sub(r"[*_]", "", field_ci(row, "Stage") or "").strip()
                info = stage_parts(raw, raw)
                matched = by_name.get(info["name"].lower())
                if matched:
                    closed = (row.get("section") or "").strip().lower() == "closed"
                    out[(s["home"], row["line"])] = {
                        "name": NAME_LINK_RE.sub(r"\1", row["name"]).strip(), "path": s["home"],
                        "line": row["line"], "stage": matched["name"], "since": info["since"],
                        "terminal": matched["terminal"], "closed": closed or matched["terminal"]}
            continue
        for d in sorted(vault.glob(re.sub(r"<[^>]+>", "*", s["home"].rstrip("/")))):
            doc = d / "README.md" if (d / "README.md").is_file() else d / "brief.md"
            info = stage_of(doc) if doc.is_file() else None
            matched = by_name.get(info["name"].strip().lower()) if info else None
            if matched:
                rel = doc.relative_to(vault).as_posix()
                out[(rel, None)] = {
                    "name": d.name, "path": rel, "line": None, "stage": matched["name"],
                    "since": info["since"], "terminal": matched["terminal"],
                    "closed": matched["terminal"]}
    return list(out.values())


def moved_in_window(vault, start, end, own=None):
    """Per declared lifecycle, the entities whose `since` date falls inside the window: a
    stage entered, a terminal one included. A Stage line with no `since` never moves, its
    date being unknown. Every lifecycle gets its entry, a quiet one with a count of 0."""
    out = []
    for lc in lifecycles(vault):
        moved = [e for e in staged_entities(vault, lc)
                 if e["since"] and start <= parse_date(e["since"]) <= end
                 and (own is None or e["path"].startswith(own))]
        moved.sort(key=lambda e: (e["since"], e["name"].lower()))
        out.append({"heading": lc["heading"], "count": len(moved), "entities": moved})
    return out


def log_name(text):
    name = re.sub(r"\s*\([^)]*\)$", "", re.sub(r"[*_`]", "", text))
    return bool(LOG_NAME_RE.match(re.sub(r"[-_\s]+", " ", name).strip()))


def log_entries(path):
    """(line, date, text) for each dated entry in a development log: the section under a
    heading `LOG_NAME_RE` reads as one, down to the next heading of its level or above, or
    the whole of a file named as one. An entry is a line, list item or heading opening on
    its date, or a table row whose first cell is one; a date alone on its line takes the
    next line as its text."""
    whole = log_name(path.stem)
    level, pending, out = None, None, []
    for lineno, text in live_lines(read_lines(path)):
        line = text.strip()
        if not line:
            continue
        entry = LOG_ENTRY_RE.match(line)
        heading = HEADING_RE.match(line)
        if heading and not entry:
            pending = None
            if not whole:
                depth = len(heading.group(1))
                if level is not None and depth <= level:
                    level = None
                if level is None and depth > 1 and log_name(heading.group(2)):
                    level = depth
            continue
        if level is None and not whole:
            continue
        if line.startswith("|"):
            cells = table_cells(line)
            day = re.sub(r"[*_]", "", cells[0]) if cells else ""
            if parse_date(day):
                out.append((lineno, day, " - ".join(c for c in cells[1:] if c)))
        elif entry and parse_date(entry.group(1)):
            body = entry.group(2).strip()
            pending = None if body else (lineno, entry.group(1))
            if body:
                out.append((lineno, entry.group(1), body))
        elif pending:
            out.append((pending[0], pending[1], line))
            pending = None
    return out


def log_files(vault, own=None):
    """Every note a development log may sit in: the markdown under projects/ and areas/, or
    under one entity, leaving out each `sources/` folder, whose records are not the log."""
    roots = [vault / own] if own else [vault / "projects", vault / "areas"]
    return [p for root in roots if root.is_dir() for p in sorted(root.rglob("*.md"))
            if "sources" not in p.relative_to(vault).parts[:-1]]


def decisions_in_window(vault, start, end, own=None):
    out = []
    for path in log_files(vault, own):
        bucket, label = scope_of(vault, path)
        for lineno, day, text in log_entries(path):
            if start <= parse_date(day) <= end:
                out.append({"file": path.relative_to(vault).as_posix(), "line": lineno,
                            "date": day, "text": text, "bucket": bucket, "scope": label})
    out.sort(key=lambda d: (d["date"], d["file"], d["line"]))
    return out


def stuck(report, tasks, match):
    """What is not moving, from what the brief already computed: the overdue lane, and each
    entity with nothing open, which has no next step. The `waiting` lane is a start gate
    still ahead, not a wait on someone, so it is not stuck."""
    # A wait on someone else, once the vault writes one in a form of its own, is a third list.
    if match:
        none = [] if tasks else [match]
    else:
        none = report["flags"].get("nothing_open") or []
    return {"overdue": report["lanes"].get("overdue", []),
            "no_next_step": [{"bucket": e["bucket"], "label": e["label"], "path": e["path"]}
                             for e in none]}


def review_block(vault, window, files, tasks, report, match):
    """The `review` key: the window, then done, slipped, moved, stuck and decisions inside
    it, for the vault or, given a resolved entity, for that entity alone."""
    start, end = parse_date(window["start"]), parse_date(window["end"])
    own = match["path"] + "/" if match else None
    if own:
        files = [p for p in files if p.relative_to(vault).as_posix().startswith(own)]
    archived = [] if own else sorted(p for p in vault.glob("archive/**/actions.md") if p.is_file())
    return {"window": window,
            "done": done_in_window(vault, files, archived, start, end),
            "slipped": slipped(tasks, start, end),
            "moved": moved_in_window(vault, start, end, own),
            "stuck": stuck(report, tasks, match),
            "decisions": decisions_in_window(vault, start, end, match["path"] if match else None)}


# ------------------------------------------------------------------------------- the report

def scan(vault, today, entity=None, paraos_home=None, review=None):
    vault = Path(vault).resolve()
    files = action_files(vault)
    report = {
        "vault": vault.as_posix(),
        "today": today.isoformat(),
        "scope": "vault",
    }

    resolution = None
    if entity:
        resolution = resolve_entity(vault, entity)
        report["scope"] = "entity"
        report["entity"] = resolution

    tasks = collect_tasks(vault, files)
    for t in tasks:
        bucket_task(t, today)

    scoped_tasks = tasks
    if resolution:
        if resolution["status"] == "resolved":
            own = resolution["match"]["path"] + "/"
            scoped_tasks = [t for t in tasks if t["file"].startswith(own)]
            report["mentioned_elsewhere"] = mentions_elsewhere(vault, tasks, resolution["match"])
        else:
            # A name that resolved to nothing never falls back to the whole vault: the
            # answer is where the thing actually is, or a question, not another brief.
            scoped_tasks = []

    dates = file_dates(vault, files)
    report["file_dates"] = {p.relative_to(vault).as_posix(): d for p, d in dates.items()}
    report["tasks"] = scoped_tasks
    report["entities"] = aggregate(scoped_tasks)
    report["totals"] = {
        "open": len(scoped_tasks),
        "overdue": sum(1 for t in scoped_tasks if t["lane"] == "overdue"),
        "upcoming": sum(1 for t in scoped_tasks if t["lane"] not in ("overdue", "undated")),
        "undated": sum(1 for t in scoped_tasks if t["lane"] == "undated"),
    }
    report["lanes"] = {}
    for t in scoped_tasks:  # a recurring item overdue or due today sits in both lanes
        for lane in filter(None, [t["lane"], t["also_lane"]]):
            report["lanes"].setdefault(lane, []).append({"file": t["file"], "line": t["line"]})
    entity_path = resolution["match"]["path"] \
        if resolution and resolution["status"] == "resolved" else None
    report["flags"] = health_flags(vault, scoped_tasks, today, dates,
                                   scoped=report["scope"] == "entity", entity_path=entity_path)
    report["flags"]["silent_sources"] = None if report["scope"] == "entity" \
        else silent_sources(vault, today, paraos_home)
    if report["scope"] == "vault":
        report["ideas"] = ideas_lane(vault, today)
        for idea in report["ideas"]:  # an idea holds no actions.md: its work lives elsewhere
            match = {"label": idea["name"], "path": f"resources/ideas/{idea['name']}"}
            idea["actions"] = [{"file": t["file"], "line": t["line"]}
                               for t in mentions_elsewhere(vault, tasks, match)]
        report["triage"] = triage_items(vault)
        report["triage_preview"] = triage_preview(vault, report["triage"])
        report["lifecycles"] = lifecycle_counts(vault)
    if review:
        window = review_window(review, today)
        if window is None:
            raise ValueError(f"no review window in {review!r}")
        match = resolution["match"] if resolution else None
        report["review"] = None if resolution and not match else \
            review_block(vault, window, files, scoped_tasks, report, match)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scan a PARA vault's open actions.")
    ap.add_argument("--vault", default=".", help="vault root (default: current directory)")
    ap.add_argument("--today", help="date to bucket against (default: the system date)")
    ap.add_argument("--entity", help="scope to one project or area")
    ap.add_argument("--review", metavar="WINDOW",
                    help="add the review block: week, month, or a YYYY-MM-DD date to review since")
    ap.add_argument("--indent", type=int, default=None, help="pretty-print the JSON")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
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
    if args.review is not None and not review_window(args.review, today):
        ap.error("--review wants week, month, or a YYYY-MM-DD date no later than today")

    report = scan(root, today, args.entity, args.paraos_home, args.review)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
