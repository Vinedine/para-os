#!/usr/bin/env python3
"""The mechanical half of /para-daily-brief, as a script instead of instructions.

    py -3 tools/../scripts/brief_scan.py --vault <path> [--today YYYY-MM-DD] [--entity <name>]
    python3 scripts/brief_scan.py --vault <path>

Prints one JSON document on stdout: the vault's open tasks with their markers parsed and
bucketed against a date, the per-entity totals, the health-flag inputs, the ideas lane and
the triage count. It never writes to the vault and never reads a mailbox.

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
import re
import sys
from datetime import date
from pathlib import Path

# The shared library sits beside this skill, in the skills folder both were installed into.
SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        BRIEF_LINE_CAP, DORMANT_ENTITY_DAYS, FALSELY_OVERDUE_DAYS,
        STALE_FILE_DAYS, WIP_THRESHOLD, action_files, cadence_days, field_ci,
        file_dates, is_under, iso, lifecycles, link_spans, live_lines, misplaced_checkboxes,
        open_tasks, read_lines,
        over_grown_briefs, parse_date, register_rows, resolve_entity,
        resolve_link, scope_of, stage_line, stage_of, stage_parts, triage_items,
    )
except ImportError as missing:  # the skill falls back to scanning by hand
    print(f"brief_scan: {missing}. The shared vault library belongs at "
          f"{SHARED_DIR}/paraos_vault.py: install para-shared beside this skill, or scan "
          f"by hand with references/task-scan.md", file=sys.stderr)
    sys.exit(2)

LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
SENTENCE_END_RE = re.compile(r"[.!?](?=\s+[^a-z\s]|\s*$)")
SENTENCE_START_RE = re.compile(r"[.!?]\s+(?=[^a-z\s])")
REVISIT_RE = re.compile(r"\brevisit when\b", re.IGNORECASE)
SENDER_RE = re.compile(r"^(?:[-*]\s+)?\**from\**:\**\s+(.+)$", re.IGNORECASE)
NOTE_FIELD_RE = re.compile(r"^(?:[-*]\s+\**[A-Za-z][\w ]{0,30}\**:|\*\*[A-Za-z][\w ]{0,30}:\*\*)")
BOLD_LINE_RE = re.compile(r"^\*\*[^*]+\*\*:?$")  # a bold line on its own is a heading
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
    target is relative to the brief's folder and breaks when rendered from the vault root),
    then the first sentence, a full stop inside a parenthesis not counting as its end.
    Kept here, not in the shared `stage_line`, which other skills read uncut."""
    if not text:
        return text
    for start, end, bracket in reversed(link_spans(text)):
        if bracket is not None:
            text = text[:bracket] + text[bracket + 1:start - 2] + text[end + 1:]
    depth = 0
    for i, ch in enumerate(text):
        depth += (ch == "(") - (ch == ")")
        if depth <= 0 and SENTENCE_END_RE.match(text, i):
            return text[:i].strip()
    return text.strip()


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
            starts = [e.end() for e in SENTENCE_START_RE.finditer(stripped) if e.end() <= m.start()]
            return short_stage(re.sub(r"^[-*]\s+", "", stripped[starts[-1] if starts else 0:]))
    return None


def triage_preview(vault, names):
    """Who sent each triage item and its first prose lines, read from the file's head: an
    .eml's headers and plain-text body, a note's `From:` field and first paragraph. A PDF
    reads through its extracted markdown twin; any other format has no preview."""
    out = {}
    for name in names:
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
             "over_grown_briefs": briefs[:3]}

    by_file = {}
    for t in tasks:
        by_file.setdefault(t["file"], []).append(t)

    for name, items in sorted(by_file.items()):
        if len(items) >= WIP_THRESHOLD:
            flags["over_threshold"].append({"file": name, "open": len(items)})
        touched = parse_date(per_file_dates.get(Path(vault) / name))
        if touched and (today - touched).days >= STALE_FILE_DAYS:
            flags["stale_files"].append({"file": name, "touched": iso(touched),
                                         "days": (today - touched).days,
                                         "open": len(items)})

    for t in tasks:
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
    flags["falsely_overdue"].sort(key=lambda r: -r["days"])
    flags["stale_recurrence"].sort(key=lambda r: -r["periods_behind"])

    if not scoped:
        undated = sum(1 for t in tasks if t["lane"] == "undated")
        if len(tasks) >= UNDATED_MAJORITY_MIN and undated * 2 > len(tasks):
            flags["undated_majority"] = {"undated": undated, "open": len(tasks)}
        flags["misplaced"] = misplaced_checkboxes(vault)
    return flags


# ------------------------------------------------------------------------------- the report

def scan(vault, today, entity=None):
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
    if report["scope"] == "vault":
        report["ideas"] = ideas_lane(vault, today)
        for idea in report["ideas"]:  # an idea holds no actions.md: its work lives elsewhere
            match = {"label": idea["name"], "path": f"resources/ideas/{idea['name']}"}
            idea["actions"] = [{"file": t["file"], "line": t["line"]}
                               for t in mentions_elsewhere(vault, tasks, match)]
        report["triage"] = triage_items(vault)
        report["triage_preview"] = triage_preview(vault, report["triage"])
        report["lifecycles"] = lifecycle_counts(vault)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scan a PARA vault's open actions.")
    ap.add_argument("--vault", default=".", help="vault root (default: current directory)")
    ap.add_argument("--today", help="date to bucket against (default: the system date)")
    ap.add_argument("--entity", help="scope to one project or area")
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

    report = scan(root, today, args.entity)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
