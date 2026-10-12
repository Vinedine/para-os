#!/usr/bin/env python3
"""The dashboard page of /para-daily-brief, rendered from the scan instead of written by hand.

    py -3 render_dashboard.py --scan <scan.json> --judgment <judgment.json> [--out <page.html>]
    py -3 render_dashboard.py --scan <scan.json> --mechanical [--out <page.html>]
    py -3 render_dashboard.py --remember <artifact url> --vault <path>
    py -3 render_dashboard.py --publish claude|local --vault <path>

The page is `dashboard.html` beside this script with the data embedded: it loads nothing
from the network, and its script works out lateness, days waited and days in stage from the
day it is opened, so a page read two days after its data still reads right.

Where it goes is the vault's choice, set with `--publish` and kept beside the remembered
artifact URL under `$PARAOS_HOME/cache/daily-brief/dashboards.json`, keyed by vault path:
`claude` (the default) publishes it as a claude.ai artifact, `local` keeps it a file on this
machine. A local page is written to `$PARAOS_HOME/cache/daily-brief/<vault folder>.html`,
the page scripts/refresh_dashboard.py keeps current, and carries "Work on this" links that
open a Claude Code session in the vault, which the artifact viewer would block; `--out` is
then not needed. Render prints one JSON line: `out`, `publish`, the page's `title` and
`description`, and `url`, the artifact this vault's dashboard was last published to (null
when none is remembered). Deleting the cache only sends the next run back to the title match
in references/dashboard.md, and to the default.

Everything on the page with one right answer comes from the scan: tiles, per-entity bars,
Today, Chase or drop, the next 14 days, people, the pipeline and its drill-down, ideas,
triage. The judgment file holds only what the model decides:

    {"flags": ["**x: 14 open** - groom via `/para-deep-clean`",
               {"text": "8 of 8 open items are undated", "kind": "undated_majority"}],
     "agenda": [{"label": "Today", "events": [{"when": "09:30", "title": "...", "sub": "..."}]}],
     "agenda_note": "optional muted line: upcoming expansion, failed sources",
     "next_action": {"text": "Open X and check Y", "file": "projects/x/actions.md", "line": 12}}

Strings in the judgment file take `**bold**`, `` `code` `` and `[label](target)` (rendered
as its label). A flag written as an object names the scan flag it reports in `kind`, plus the
`file` for a per-file one (`over_threshold`, `stale_files`) or the `source` for a
`silent_sources` one, and opens on the items behind it. A `next_action` naming a task the
scan does not hold, or a flag object naming one it did not raise, is an error (exit 2),
never a silent drop. What the judgment file holds is references/dashboard.md.

`--mechanical` renders with no judgment file, so the page can be kept current by a hook
(scripts/refresh_dashboard.py) with no model run: the Next action is the first item of the
brief's own sort (overdue and due today first, then priority, then date) without the Vision
tiebreak, every flag the scan fired is worded here, and the agenda is left out.
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        HEADLINE_CAP, OPEN_ITEM_CAP, PRIORITY_RANK, WAITING_FLAG_DAYS, paraos_home_dir,
        scope_of,
    )
    from brief_scan import EMPHASIS_RE, SENTENCE_END_RE, first_end  # noqa: E402
except ImportError as missing:
    print(f"render_dashboard: {missing}. install para-shared beside this skill", file=sys.stderr)
    sys.exit(2)

TEMPLATE = Path(__file__).with_name("dashboard.html")
TEXT_CAP = 100
PUBLISH = ("claude", "local")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
BOLD_LEAD_RE = re.compile(r"^\*\*(.+?)\*\*")
CLAUSE_END_RE = re.compile(r";| - |" + SENTENCE_END_RE.pattern)
TIME_RE = re.compile(r"(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])")
DESCRIPTION = ("Daily vault-state dashboard: today, the next 14 days, who owes what, the "
               "pipeline and open actions per project and area.")


class JudgmentError(ValueError):
    pass


# ------------------------------------------------------------------------ text helpers

def inline(text):
    """Escape, then the three markdown forms a judgment string may carry."""
    text = LINK_RE.sub(r"\1", text or "")
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)


def plain(text):
    return LINK_RE.sub(r"\1", text or "").replace("**", "").replace("`", "").strip()


def cut(text):
    """A task cut, never wrapped: its bold lead where it has one, else its first clause,
    then to TEXT_CAP characters at a word boundary (output.md's line rules)."""
    text = EMPHASIS_RE.sub(r"\2", LINK_RE.sub(r"\1", text)).strip()
    lead = BOLD_LEAD_RE.match(text)
    if lead:
        text = lead.group(1).rstrip(".:")
    else:
        text = text[:first_end(text, CLAUSE_END_RE) or None]
    text = text.replace("**", "").replace("`", "").strip()
    if len(text) > TEXT_CAP:
        text = text[:TEXT_CAP].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


def display_name(vault):
    """The vault's CLAUDE.md H1 without a trailing `Vault Conventions`, else its folder."""
    claude = Path(vault) / "CLAUDE.md"
    if claude.is_file():
        for line in claude.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("# "):
                name = re.sub(r"\s*vault conventions\s*$", "", line[2:].strip(), flags=re.I)
                if name:
                    return name
                break
    return Path(vault).name


# ---------------------------------------------------------------------------- the data

def find_task(scan, ref, what):
    for t in scan["tasks"]:
        if t["file"] == ref.get("file") and t["line"] == ref.get("line"):
            return t
    raise JudgmentError(f"{what} names {ref.get('file')}:{ref.get('line')}, "
                        f"which holds no open task in the scan")


def task_id(t):
    return f"{t['file']}:{t['line']}"


def task_label(t):
    return f"{t['person'] or t['scope']}:{t['line']}"


def tasks_at(scan, refs):
    keys = {(r["file"], r["line"]) for r in refs}
    return [t for t in scan["tasks"] if (t["file"], t["line"]) in keys]


def task_row(t, names):
    """One task as the page reads it. A wait on someone else carries its own fields and no
    date; a time is read off the line only where the line is dated."""
    clock = TIME_RE.search(t["text"]) if t["effective_date"] else None
    wait = t.get("waiting_on")
    return {"id": task_id(t), "file": t["file"], "line": t["line"],
            "entity_key": f"{t['bucket']}:{t['scope']}", "where": task_label(t),
            "headline": cut(t["text"]), "due": None if wait else t["effective_date"],
            "time": f"{int(clock.group(1)):02d}:{clock.group(2)}" if clock else None,
            "priority": t["priority"], "recurring": t["recurring"],
            "waiting": wait and {"person": wait["person"], "what": wait["what"],
                                 "since": wait["since"]},
            "person_name": names.get(t.get("owed_to"))}


def flag_drill(scan, flag):
    """(task ids, file rows) a flag object opens on, read from the scan flag its `kind`
    names."""
    kind, raised = flag.get("kind"), scan["flags"]
    if kind in ("over_threshold", "stale_files"):
        if not any(r["file"] == flag.get("file") for r in raised.get(kind) or []):
            raise JudgmentError(f"flag {kind} names {flag.get('file')}, which the scan "
                                f"did not flag")
        return [task_id(t) for t in scan["tasks"] if t["file"] == flag["file"]], []
    if kind in ("falsely_overdue", "stale_recurrence", "undated_majority", "long_headlines",
                "waiting_too_long"):
        if not raised.get(kind):
            raise JudgmentError(f"flag {kind} is one the scan did not raise")
        if kind == "undated_majority":
            return [task_id(t) for t in scan["tasks"] if t["lane"] == "undated"], []
        return [task_id(t) for t in tasks_at(scan, raised[kind])], []
    if kind in ("misplaced", "over_grown_briefs", "stray_checkboxes"):
        rows = (sum((raised.get(kind) or {}).values(), []) if kind == "misplaced"
                else raised.get(kind) or [])
        if not rows:
            raise JudgmentError(f"flag {kind} is one the scan did not raise")
        unit = "lines" if kind == "over_grown_briefs" else "open"
        return [], [{"label": r["file"], "meta": f"{r[unit]} {unit}"} for r in rows]
    if kind == "silent_sources":
        row = next((r for r in raised.get(kind) or [] if r["source"] == flag.get("source")), None)
        if not row:
            raise JudgmentError(f"flag {kind} names {flag.get('source')}, which the scan "
                                f"did not flag")
        return [], [{"label": row["ledger"], "meta": f"newest {row['newest'] or 'unread'} · "
                                                     f"expected {row['cadence']}"}]
    if kind == "nothing_open":
        if not raised.get(kind):
            raise JudgmentError(f"flag {kind} is one the scan did not raise")
        return [], [{"label": r["path"], "meta": "since " + r["touched"] if r["touched"]
                     else "no actions.md"} for r in raised[kind]]
    raise JudgmentError(f"flag kind {kind!r} is not a scan flag")


def flag_rows(scan, items):
    out = []
    for f in items or []:
        if isinstance(f, str):
            out.append({"html": inline(f), "tasks": [], "rows": []})
        else:
            tasks, rows = flag_drill(scan, f)
            out.append({"html": inline(f.get("text")), "tasks": tasks, "rows": rows})
    return out


def next_action(scan, judgment, mechanical):
    if mechanical:
        picks = mechanical_now(scan)
        if not picks:
            return {"html": "Nothing is overdue or due this week.", "text": "", "where": None,
                    "note": None}
        t = find_task(scan, picks[0], "now")
        return {"html": html.escape(cut(t["text"])), "text": cut(t["text"]),
                "where": task_label(t), "note": "Picked by the brief's own sort; the next "
                                                "/para-daily-brief run chooses with judgment."}
    na = judgment.get("next_action")
    if not na or not na.get("text"):
        raise JudgmentError("next_action.text is required")
    where = task_label(find_task(scan, na, "next_action")) if na.get("file") else None
    return {"html": inline(na["text"]), "text": plain(na["text"]), "where": where, "note": None}


def agenda(judgment):
    out = []
    for s in judgment.get("agenda") or []:
        events = [{"when": e.get("when", ""),
                   "html": inline(e.get("title", "")) + (f" · {inline(e['sub'])}"
                                                         if e.get("sub") else "")}
                  for e in s.get("events") or []]
        if events:
            out.append({"label": s.get("label", ""), "events": events})
    return out


def ideas(scan):
    return [{"name": i["name"], "stage": plain(i["stage"]) or None, "dormant": i["dormant"],
             "touched": i["touched"], "since": i.get("since"), "revisit": plain(i.get("revisit")),
             "actions": [f"{a['file']}:{a['line']}" for a in i.get("actions") or []]}
            for i in scan["ideas"]]


def triage(scan):
    """Each item with its sender and subject; sign-in material is counted, never named
    (para-shared/connectors.md)."""
    previews, rows, codes = scan.get("triage_preview") or {}, [], 0
    for name in scan["triage"]:
        p = previews.get(name) or {}
        if p.get("auth"):
            codes += 1
            continue
        rows.append({"name": re.sub(r"[.]md$", "", name), "from": p.get("from"),
                     "subject": p.get("subject")})
    return rows, codes


def page_data(scan, judgment, mechanical, local):
    names = {p["person"]: p["name"] for p in scan.get("people") or []}
    tri, codes = triage(scan)
    items = [dict(i, contact_name=names.get(i["contact"]) or i["contact_text"] or None)
             for i in scan.get("pipeline_items") or []]
    return {"vault": scan["vault"], "name": display_name(scan["vault"]), "today": scan["today"],
            "local": local, "chase_days": WAITING_FLAG_DAYS,
            "generated_by": "from the scan alone" if mechanical else "by /para-daily-brief",
            "next_action": next_action(scan, judgment, mechanical),
            "tasks": [task_row(t, names) for t in scan["tasks"]],
            "entities": [dict(r, key=f"{r['bucket']}:{r['label']}") for r in scan["entities"]],
            "flags": flag_rows(scan, judgment.get("flags")),
            "agenda": [] if mechanical else agenda(judgment),
            "agenda_note": None if mechanical or not judgment.get("agenda_note")
            else inline(judgment["agenda_note"]),
            "ideas": ideas(scan), "triage": tri, "triage_codes": codes,
            "people": scan.get("people") or [], "pipeline": scan.get("lifecycles") or [],
            "pipeline_items": items}


# ------------------------------------------------------------- without a judgment file

NOW_CAP = 5
NOW_LANES = ("overdue", "today", "this_week")


def mechanical_now(scan):
    """Step 5's ranking without the model: overdue and due-today items first, then priority
    descending, then a deadline before a plan date and a one-off before a recurring item,
    then date ascending, and no Vision tiebreak. A recurring item overdue or due today is in
    those lanes already."""
    keys = {(e["file"], e["line"]) for lane in NOW_LANES for e in scan["lanes"].get(lane, [])}
    picks = [t for t in scan["tasks"] if (t["file"], t["line"]) in keys]
    picks.sort(key=lambda t: (0 if t["days"] <= 0 else 1,
                              -PRIORITY_RANK.get(t["priority"] or "", 0),
                              0 if t["due"] else 1, 1 if t["recurring"] else 0,
                              t["days"], t["file"], t["line"]))
    return [{"file": t["file"], "line": t["line"]} for t in picks[:NOW_CAP]]


def file_label(scan, rel):
    """The `<scope>` a flag names a file by: the entity, or the person for a contact file."""
    bucket, scope = scope_of(scan["vault"], Path(scan["vault"]) / rel)
    return Path(rel).stem if scope == "network" else scope


def mechanical_flags(scan):
    """Every flag the scan fired, worded as references/signals.md words it, each as a flag
    object that opens on what it reports."""
    raised, out = scan["flags"], []
    for r in raised.get("over_threshold") or []:
        out.append({"text": f"**{file_label(scan, r['file'])}: {r['open']} open**, over the cap "
                            f"of {OPEN_ITEM_CAP} - close or demote before adding. "
                            f"`/para-deep-clean` grooms",
                    "kind": "over_threshold", "file": r["file"]})
    for r in raised.get("stale_files") or []:
        out.append({"text": f"**{file_label(scan, r['file'])}: {r['open']} open, untouched since "
                            f"{r['touched']}** ({r['days']}d)",
                    "kind": "stale_files", "file": r["file"]})
    late = raised.get("falsely_overdue") or []
    if late:
        worst = late[0]
        out.append({"text": f"**{len(late)} overdue by more than 30 days** - worst: "
                            f"{file_label(scan, worst['file'])}:{worst['line']}, {worst['days']}d. "
                            f"Was the deadline real? `/para-deep-clean` asks",
                    "kind": "falsely_overdue"})
    behind = raised.get("stale_recurrence") or []
    if behind:
        worst = behind[0]
        out.append({"text": f"**{len(behind)} recurring behind** - worst: "
                            f"{file_label(scan, worst['file'])}:{worst['line']} 🔁 {worst['cadence']}, "
                            f"📅 {worst['date']}, {worst['periods_behind']} periods behind",
                    "kind": "stale_recurrence"})
    um = raised.get("undated_majority")
    if um:
        out.append({"text": f"**{um['undated']} of {um['open']} open items are undated** - the "
                            f"backlog is bigger than the brief can date. `/para-deep-clean` grooms",
                    "kind": "undated_majority"})
    idle = raised.get("nothing_open") or []
    if idle:
        out.append({"text": f"**{idle[0]['label']}: nothing open**"
                            + (f", and {len(idle) - 1} more" if len(idle) > 1 else "")
                            + " - finished (archive) or stalled (next step)?",
                    "kind": "nothing_open"})
    mis = raised.get("misplaced") or {}
    fired = [(bucket, rows) for bucket, rows in mis.items() if rows]
    parts = [f"{sum(r['open'] for r in rows)} under {bucket}/ (worst: {rows[0]['file']}, "
             f"{rows[0]['open']})" for bucket, rows in fired]
    if parts:
        why = {"archive": "archive hygiene requires zero", "resources": "`resources/` never "
               "holds one", "areas/network": "this vault's contact cards hold none"}
        out.append({"text": f"**Open checkboxes {' and '.join(parts)}** - "
                            + ", and ".join(why[b] for b, _ in fired if b in why),
                    "kind": "misplaced"})
    late = raised.get("waiting_too_long") or []
    if late:
        w = late[0]
        out.append({"text": f"**{w['what'] or 'what was owed'} from {w['person']}: {w['days']} days**"
                            + (f", and {len(late) - 1} more" if len(late) > 1 else "")
                            + " - chase or drop?",
                    "kind": "waiting_too_long"})
    stray = raised.get("stray_checkboxes") or []
    if stray:
        out.append({"text": f"**{sum(r['open'] for r in stray)} open checkboxes outside the action "
                            f"files** (worst: {stray[0]['file']}, {stray[0]['open']}) - no brief "
                            f"counts them: move them to `actions.md`, or mark the file frozen",
                    "kind": "stray_checkboxes"})
    long_ = raised.get("long_headlines") or []
    if long_:
        worst = long_[0]
        out.append({"text": f"**{len(long_)} action{'s' if len(long_) > 1 else ''} of "
                            f"{HEADLINE_CAP}+ characters** - worst: "
                            f"{file_label(scan, worst['file'])}:{worst['line']}, {worst['chars']}. "
                            f"A bold headline, the detail in a sub-bullet or the brief",
                    "kind": "long_headlines"})
    briefs = raised.get("over_grown_briefs") or []
    if briefs:
        out.append({"text": f"**{briefs[0]['file']}: {briefs[0]['lines']} lines** - content "
                            f"grooming via `/para-deep-clean`"
                            + (f", and {len(briefs) - 1} more" if len(briefs) > 1 else ""),
                    "kind": "over_grown_briefs"})
    for r in raised.get("silent_sources") or []:
        out.append({"text": f"**{r['source']}: ledger unreadable** - its silence is unknown"
                    if r.get("error") else
                    f"**{r['source']}: nothing since {r['newest']}** ({r['days']} days, expected "
                    f"{r['cadence']}) - check its sign-in and routing",
                    "kind": "silent_sources", "source": r["source"]})
    return out




# --------------------------------------------------------------------------- the page

def render(scan, judgment=None, local=False):
    """The page: from the model's judgment file, or, with none, from the scan alone."""
    if scan.get("scope") != "vault":
        raise JudgmentError("the dashboard is a vault-wide page; an entity scope has none")
    mechanical = judgment is None
    if mechanical:
        judgment = {"flags": mechanical_flags(scan)}
    data = page_data(scan, judgment, mechanical, local)
    title = f"{data['name']} Dashboard"
    template = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")  # no tag closes the block
    page = template.replace("__PARAOS_TITLE__", html.escape(title)).replace("__PARAOS_DATA__", blob)
    return title, page


# ------------------------------------------------------- where the page goes, remembered

def cache_file(paraos_home=None):
    return paraos_home_dir(paraos_home) / "cache" / "daily-brief" / "dashboards.json"


def local_page(vault, paraos_home=None):
    """The page a local vault keeps, the one scripts/refresh_dashboard.py rewrites."""
    return paraos_home_dir(paraos_home) / "cache" / "daily-brief" / f"{Path(vault).name}.html"


def vault_key(vault):
    return Path(vault).resolve().as_posix().lower()


def load_cache(paraos_home=None):
    path = cache_file(paraos_home)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def cached(vault, paraos_home=None):
    entry = load_cache(paraos_home).get(vault_key(vault))
    return entry if isinstance(entry, dict) else {}


def remembered_url(vault, paraos_home=None):
    return cached(vault, paraos_home).get("url")


def publish_choice(vault, paraos_home=None):
    """`claude` unless the operator chose `local` for this vault."""
    return "local" if cached(vault, paraos_home).get("publish") == "local" else "claude"


def store(vault, paraos_home=None, **fields):
    path = cache_file(paraos_home)
    data = load_cache(paraos_home)
    entry = data.get(vault_key(vault)) if isinstance(data.get(vault_key(vault)), dict) else {}
    entry.update(fields)
    data[vault_key(vault)] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def remember(vault, url, paraos_home=None):
    return store(vault, paraos_home, url=url, title=f"{display_name(vault)} Dashboard")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render the daily-brief dashboard page.")
    ap.add_argument("--scan", help="brief_scan.py output")
    ap.add_argument("--judgment", help="the model's judgment file")
    ap.add_argument("--mechanical", action="store_true",
                    help="render from the scan alone, with no judgment file")
    ap.add_argument("--out", help="where to write a page for claude.ai (never inside the vault)")
    ap.add_argument("--remember", metavar="URL", help="store the published artifact URL")
    ap.add_argument("--publish", choices=PUBLISH, help="where this vault's dashboard goes")
    ap.add_argument("--vault", help="vault root, with --remember or --publish")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if args.remember or args.publish:
        if not args.vault:
            ap.error("--remember and --publish need --vault")
        if args.publish:
            path = store(args.vault, publish=args.publish)
            print(json.dumps({"publish": args.publish, "cache": path.as_posix()}))
        if args.remember:
            path = remember(args.vault, args.remember)
            print(json.dumps({"remembered": args.remember, "cache": path.as_posix()}))
        return 0
    if args.mechanical and args.judgment:
        ap.error("--mechanical renders without a judgment file; drop one or the other")
    if not (args.scan and (args.judgment or args.mechanical)):
        ap.error("render needs --scan and either --judgment or --mechanical")

    scan = json.loads(Path(args.scan).read_text(encoding="utf-8"))
    judgment = None if args.mechanical else \
        json.loads(Path(args.judgment).read_text(encoding="utf-8"))
    publish = publish_choice(scan["vault"])
    if publish == "local":
        out = local_page(scan["vault"])
    elif args.out:
        out = Path(args.out).resolve()
    else:
        ap.error("this vault publishes to claude.ai: name the page with --out")
    if out.is_relative_to(Path(scan["vault"]).resolve()):
        print("render_dashboard: --out is inside the vault; write it to a scratch folder",
              file=sys.stderr)
        return 2
    try:
        title, page = render(scan, judgment, local=publish == "local")
    except JudgmentError as wrong:
        print(f"render_dashboard: {wrong}", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(json.dumps({"out": out.as_posix(), "publish": publish, "title": title,
                      "description": DESCRIPTION, "url": remembered_url(scan["vault"])},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
