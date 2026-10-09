#!/usr/bin/env python3
"""The dashboard page of /para-daily-brief, rendered from the scan instead of written by hand.

    py -3 render_dashboard.py --scan <scan.json> --judgment <judgment.json> --out <page.html>
    py -3 render_dashboard.py --scan <scan.json> --mechanical --out <page.html>
    py -3 render_dashboard.py --remember <artifact url> --vault <path>

Render prints one JSON line: `out`, the page's `title` and `description`, and `url`, the artifact this vault's
dashboard was last published to (null when none is remembered). Remember stores that URL
under `$PARAOS_HOME/cache/daily-brief/dashboards.json`, keyed by vault path; it is a cache,
and deleting it only sends the next run back to the title match in references/dashboard.md.

Everything on the page with one right answer comes from the scan: tiles, per-entity bars,
the remainder strip, Later counts, lifecycle lines, ideas, triage. The judgment file holds
only what the model decides, so the model writes a few hundred bytes instead of the page:

    {"now": [{"file": "projects/x/actions.md", "line": 12, "text": "optional override"}],
     "flags": ["**x: 14 open** - groom via `/para-deep-clean`",
               {"text": "8 of 8 open items are undated", "kind": "undated_majority"}],
     "agenda": [{"label": "Today", "events": [{"when": "09:30", "title": "...", "sub": "..."}]}],
     "agenda_note": "optional muted line: upcoming expansion, failed sources",
     "next_action": {"text": "Open X and check Y", "file": "projects/x/actions.md", "line": 12}}

Strings in the judgment file take `**bold**`, `` `code` `` and `[label](target)` (rendered
as its label). A flag written as an object names the scan flag it reports in `kind`, plus the
`file` for a per-file one (`over_threshold`, `stale_files`) or the `source` for a
`silent_sources` one, and opens on the items behind it.
A `now` or `next_action` entry naming a task the scan does not hold, or a flag object naming
one it did not raise, is an error (exit 2), never a silent drop. What the judgment file
holds is references/dashboard.md.

`--mechanical` renders with no judgment file, so the page can be kept current by a hook
(scripts/refresh_dashboard.py) with no model run: Now is ranked by the brief's own sort
(overdue and due today first, then priority, then date) without the Vision tiebreak, every
flag the scan fired is worded here, and in place of the Next action and the agenda, which
stay model work, one line says they come from the next brief run.
"""

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        HEADLINE_CAP, OPEN_ITEM_CAP, PRIORITY_RANK, paraos_home_dir, scope_of,
    )
    from brief_scan import EMPHASIS_RE, SENTENCE_END_RE, first_end  # noqa: E402
except ImportError as missing:
    print(f"render_dashboard: {missing}. install para-shared beside this skill", file=sys.stderr)
    sys.exit(2)

TOP_ENTITIES = 10
TEXT_CAP = 100
TILE_PANELS = ("overdue", "week", "undated")
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
BOLD_LEAD_RE = re.compile(r"^\*\*(.+?)\*\*")
CLAUSE_END_RE = re.compile(r";| - |" + SENTENCE_END_RE.pattern)
DESCRIPTION = ("Daily vault-state dashboard: open actions per project and area, health flags, "
               "ideas, agenda.")


class JudgmentError(ValueError):
    pass


# ------------------------------------------------------------------------ text helpers

def inline(text):
    """Escape, then the three markdown forms a judgment string may carry."""
    text = LINK_RE.sub(r"\1", text or "")
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)


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


def short_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1][:3]}"


def long_date(iso):
    d = date.fromisoformat(iso)
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"


def relative(days):
    if days == 0:
        return "today"
    return f"{-days}d ago" if days < 0 else f"in {days}d"


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


# ------------------------------------------------------------------------- the panels

def find_task(scan, ref, what):
    for t in scan["tasks"]:
        if t["file"] == ref.get("file") and t["line"] == ref.get("line"):
            return t
    raise JudgmentError(f"{what} names {ref.get('file')}:{ref.get('line')}, "
                        f"which holds no open task in the scan")


def task_label(t):
    return f"{t['person'] or t['scope']}:{t['line']}"


def tasks_at(scan, refs):
    keys = {(r["file"], r["line"]) for r in refs}
    return [t for t in scan["tasks"] if (t["file"], t["line"]) in keys]


def tiles(scan):
    """Overdue, Due this week and Undated toggle a panel listing the tasks they count (a
    hidden checkbox, so no script). No tile is a link: the artifact viewer resolves an
    in-page `#anchor` against its own address, and the page goes blank."""
    lanes, totals = scan["lanes"], scan["totals"]
    week = lanes.get("today", []) + lanes.get("this_week", [])
    share = round(100 * totals["undated"] / totals["open"]) if totals["open"] else 0
    panels = {"overdue": [t for t in scan["tasks"] if t["lane"] == "overdue"],
              "week": tasks_at(scan, week),
              "undated": [t for t in scan["tasks"] if t["lane"] == "undated"]}
    rows = [(totals["open"], "open actions", False, None),
            (totals["overdue"], "overdue", totals["overdue"] > 0, "overdue"),
            (len(week), "due this week", False, "week"), (f"{share}%", "undated", False, "undated"),
            (len(scan["ideas"]), "ideas", False, None),
            (len(scan["triage"]), "in triage", False, None)]
    toggles, cells, boxes = [], [], []
    for n, label, alert, target in rows:
        cls = "tile alert" if alert else "tile"
        inner = f"<b>{n}</b><span>{label}</span>"
        if not panels.get(target):
            cells.append(f'<div class="{cls}">{inner}</div>')
        else:
            toggles.append(f'<input type="checkbox" class="toggle" id="tile-{target}">')
            cells.append(f'<label class="{cls}" for="tile-{target}">{inner}</label>')
            boxes.append(f'<div class="panel p-{target}"><div class="label">{label} · '
                         f'{len(panels[target])}</div>{drill_list(scan, panels[target])}</div>')
    return (f'<div class="tilebox">{"".join(toggles)}<div class="tiles">{"".join(cells)}</div>'
            f'<div class="panels">{"".join(boxes)}</div></div>')


def counts_text(row):
    parts = [f"{row[k]} {k}" for k in ("overdue", "upcoming", "undated") if row[k]]
    return f"<b>{row['open']}</b> open · " + " · ".join(parts)


def segment(t):
    """The bar segment a task counts in: overdue, undated, or upcoming for every other lane."""
    return {"overdue": "over", "undated": "und"}.get(t["lane"], "up")


def bar_order(tasks):
    """Tasks in the order a bar reads: overdue, then upcoming soonest first, then undated."""
    rank = {"over": 0, "up": 1, "und": 2}
    return sorted(tasks, key=lambda t: (rank[segment(t)], t["days"] or 0, t["file"], t["line"]))


def task_item(scan, t):
    prio = f"{t['priority']} " if t["priority"] else ""
    return (f'<li><i class="seg-{segment(t)}"></i><span>{prio}'
            f'{html.escape(cut(t["text"]))}</span>{task_meta(t)}</li>')


def drill_list(scan, tasks):
    return f'<ol class="drill">{"".join(task_item(scan, t) for t in bar_order(tasks))}</ol>'


def drilldown(scan, rows):
    """The open tasks behind some chart rows."""
    keys = {(r["bucket"], r["label"]) for r in rows}
    return drill_list(scan, [t for t in scan["tasks"] if (t["bucket"], t["scope"]) in keys])


def entity_chart(scan):
    rows = scan["entities"]
    if not rows:
        return ""
    top, rest = rows[:TOP_ENTITIES], rows[TOP_ENTITIES:]
    peak = top[0]["open"]
    out = ['<h2 id="entities">Open actions per entity</h2><div class="chart">']
    for r in top:
        name = html.escape(r["label"])
        if r["label"] == "network" and r["files"] > 1:
            name += f" ({r['files']} files)"
        segs = "".join(f'<i class="seg-{cls}" style="width:{100 * r[k] / r["open"]:.2f}%"></i>'
                       for k, cls in (("overdue", "over"), ("upcoming", "up"),
                                      ("undated", "und")) if r[k])
        out.append(f'<details><summary class="row"><span class="name"><span class="badge">'
                   f'{r["bucket"]}</span>{name}</span><div class="track"><div class="bar" '
                   f'style="width:{100 * r["open"] / peak:.1f}%">{segs}</div></div>'
                   f'<span class="n">{counts_text(r)}</span></summary>{drilldown(scan, [r])}'
                   f'</details>')
    out.append('<div class="legend"><span><i class="seg-over"></i>overdue</span>'
               '<span><i class="seg-up"></i>upcoming</span>'
               '<span><i class="seg-und"></i>undated</span></div>')
    if rest:
        agg = {k: sum(r[k] for r in rest) for k in ("open", "overdue", "upcoming", "undated")}
        more = "entity" if len(rest) == 1 else "entities"
        out.append(f'<details><summary class="rest">+{len(rest)} more {more} · '
                   f'{counts_text(agg)} <span class="sub">(composition only, not charted)'
                   f'</span></summary>{drilldown(scan, rest)}</details>')
    t = scan["totals"]
    share = round(100 * t["undated"] / t["open"]) if t["open"] else 0
    out.append(f'<div class="totals"><b>{t["open"]}</b> open · <b>{t["overdue"]}</b> overdue · '
               f'<b>{t["upcoming"]}</b> upcoming · <b>{t["undated"]}</b> undated ({share}%)</div>')
    out.append("</div>")
    for lc in scan.get("lifecycles") or []:
        stages = " · ".join(f"{c['stage']} {c['count']}" for c in lc["counts"])
        out.append(f'<p class="pipeline"><b>{html.escape(lc["heading"])}:</b> '
                   f'{html.escape(stages)} - <code>/para-pipeline</code> for the board</p>')
    return "".join(out)


def flag_drill(scan, flag):
    """What a flag object opens on, read from the scan flag its `kind` names."""
    kind, raised = flag.get("kind"), scan["flags"]
    if kind in ("over_threshold", "stale_files"):
        if not any(r["file"] == flag.get("file") for r in raised.get(kind) or []):
            raise JudgmentError(f"flag {kind} names {flag.get('file')}, which the scan "
                                f"did not flag")
        return drill_list(scan, [t for t in scan["tasks"] if t["file"] == flag["file"]])
    if kind in ("falsely_overdue", "stale_recurrence", "undated_majority", "long_headlines",
                "waiting_too_long"):
        if not raised.get(kind):
            raise JudgmentError(f"flag {kind} is one the scan did not raise")
        if kind == "undated_majority":
            return drill_list(scan, [t for t in scan["tasks"] if t["lane"] == "undated"])
        return drill_list(scan, tasks_at(scan, raised[kind]))
    if kind in ("misplaced", "over_grown_briefs", "stray_checkboxes"):
        rows = (sum((raised.get(kind) or {}).values(), []) if kind == "misplaced"
                else raised.get(kind) or [])
        if not rows:
            raise JudgmentError(f"flag {kind} is one the scan did not raise")
        unit = "lines" if kind == "over_grown_briefs" else "open"
        lis = "".join(f'<li><span>{html.escape(r["file"])}</span>'
                      f'<span class="meta">{r[unit]} {unit}</span></li>' for r in rows)
        return f'<ol class="drill">{lis}</ol>'
    if kind == "silent_sources":
        row = next((r for r in raised.get(kind) or [] if r["source"] == flag.get("source")), None)
        if not row:
            raise JudgmentError(f"flag {kind} names {flag.get('source')}, which the scan "
                                f"did not flag")
        return (f'<ol class="drill"><li><span>{html.escape(row["ledger"])}</span>'
                f'<span class="meta">newest {row["newest"] or "unread"} · expected '
                f'{html.escape(row["cadence"])}</span></li></ol>')
    if kind == "nothing_open":
        if not raised.get(kind):
            raise JudgmentError(f"flag {kind} is one the scan did not raise")
        lis = "".join(f'<li><span>{html.escape(r["path"])}</span><span class="meta">'
                      f'{"since " + r["touched"] if r["touched"] else "no actions.md"}</span></li>'
                      for r in raised[kind])
        return f'<ol class="drill">{lis}</ol>'
    raise JudgmentError(f"flag kind {kind!r} is not a scan flag")


def flags(scan, judgment):
    items = judgment.get("flags") or []
    if not items:
        return ""
    lis = "".join(f"<li>{inline(f)}</li>" if isinstance(f, str) else
                  f'<li><details><summary class="x">{inline(f.get("text"))}</summary>'
                  f'{flag_drill(scan, f)}</details></li>' for f in items)
    return f'<h2>Health flags</h2><ul class="flags">{lis}</ul>'


def task_meta(t):
    bits = [html.escape(task_label(t))]
    if t["recurring"]:
        bits.append(f"🔁 {html.escape(t['recurring'])}")
    if t["effective_date"]:
        mark = "📅" if t["due"] else "⏳"
        badge = f"{mark} {short_date(t['effective_date'])} ({relative(t['days'])})"
        bits.append(f'<span class="due">{badge}</span>' if t["days"] <= 0 else badge)
    return f'<span class="meta">{" · ".join(bits)}</span>'


def later_line(scan, now_keys):
    lanes = scan["lanes"]

    def left(*names):
        keys = {(e["file"], e["line"]) for n in names for e in lanes.get(n, [])}
        return len(keys - now_keys)

    counts = [(left("overdue", "today", "this_week"), "this week"),
              (left("next_30"), "next 30 days"), (left("later"), "later"),
              (left("recurring"), "recurring"), (left("waiting"), "waiting"),
              (left("waiting_on"), "waiting on others"), (left("undated"), "undated")]
    return ('<p class="later"><b>Later:</b> '
            + " · ".join(f"{n} {label}" for n, label in counts) + "</p>")


def now_panel(scan, judgment):
    picks = judgment.get("now") or []
    if len(picks) > 5:
        raise JudgmentError(f"now holds {len(picks)} items; the cap is five")
    tasks = [(find_task(scan, p, "now"), p) for p in picks]
    now_keys = {(t["file"], t["line"]) for t, _ in tasks}
    out = []
    if tasks:
        out.append(f'<h2>Now · {len(tasks)} of {scan["totals"]["open"]}</h2><ol class="now">')
        for t, p in tasks:
            prio = f"{t['priority']} " if t["priority"] else ""
            text = html.escape(p.get("text") or cut(t["text"]))
            out.append(f"<li>{prio}{text} {task_meta(t)}</li>")
        out.append("</ol>")
    out.append(later_line(scan, now_keys))
    return "".join(out)


def agenda(judgment):
    sections = [s for s in judgment.get("agenda") or [] if s.get("events")]
    note = judgment.get("agenda_note")
    if not sections and not note:
        return ""
    out = ['<h2>Agenda</h2><div class="agenda">']
    for s in sections:
        out.append(f'<div class="day">{html.escape(s.get("label", ""))}</div>')
        for e in s["events"]:
            sub = f' <span class="sub">· {inline(e["sub"])}</span>' if e.get("sub") else ""
            out.append(f'<div class="ev"><time>{html.escape(e.get("when", ""))}</time>'
                       f'<span>{inline(e.get("title", ""))}{sub}</span></div>')
    out.append("</div>")
    if note:
        out.append(f'<p class="note">{inline(note)}</p>')
    return "".join(out)


def item(head, more):
    """A list card: a summary that opens on `more`, or a plain row when there is nothing
    behind it."""
    if more:
        return (f'<details class="item"><summary class="head x">{head}</summary>'
                f'<div class="more">{more}</div></details>')
    return f'<div class="item"><div class="head">{head}</div></div>'


def idea_more(scan, i):
    """Days in stage, the next step (the soonest dated open action naming the idea), the
    other actions naming it, and the brief's revisit trigger."""
    parts = []
    if i.get("days_in_stage") is not None:
        d = i["days_in_stage"]
        parts.append(f'<div class="facts"><b>{d} day{"" if d == 1 else "s"}</b> in stage, '
                     f'since {short_date(i["since"])}</div>')
    tasks = bar_order(tasks_at(scan, i.get("actions") or []))
    step = next((t for t in tasks if t["effective_date"]), None)
    if step:
        parts.append(f'<div class="label">Next step</div>{drill_list(scan, [step])}')
    rest = [t for t in tasks if t is not step]
    if rest:
        parts.append(f'<div class="label">{"Also open" if step else "Open actions"} naming it · '
                     f'{len(rest)}</div>{drill_list(scan, rest)}')
    if i.get("revisit"):
        parts.append(f'<div class="revisit">{inline(i["revisit"])}</div>')
    return "".join(parts)


def ideas(scan):
    if not scan["ideas"]:
        return ""
    rows = []
    for i in scan["ideas"]:
        stage = f"<span>{inline(i['stage'])}</span>" if i["stage"] else ""
        dormant = '<span class="dormant">dormant 6+ months</span>' if i["dormant"] else ""
        touched = f"touched {short_date(i['touched'])}" if i["touched"] else ""
        rows.append(item(f'<b>{html.escape(i["name"])}</b>{stage}{dormant}'
                         f'<span class="meta">{touched}</span>', idea_more(scan, i)))
    return f'<h2 id="ideas">Ideas · {len(rows)}</h2><div class="list">{"".join(rows)}</div>'


def triage(scan):
    items = scan["triage"]
    if not items:
        return ""
    previews = scan.get("triage_preview") or {}
    rows, codes = [], 0
    for n in items:
        p = previews.get(n) or {}
        if p.get("auth"):  # counted, never named: para-shared/connectors.md
            codes += 1
            continue
        more = "".join(f'<div class="facts">{label} {html.escape(p[k])}</div>'
                       for k, label in (("from", "From"), ("subject", "Subject:")) if p.get(k))
        if p.get("excerpt"):
            more += f'<div class="excerpt">{html.escape(p["excerpt"])}</div>'
        rows.append(item(f'<span>{html.escape(re.sub(r"[.]md$", "", n))}</span>', more))
    if codes:
        rows.append(item(f"<span>sign-in and security codes: {codes}</span>", ""))
    return (f'<h2 id="triage">Triage · {len(items)} to process</h2>'
            f'<div class="list">{"".join(rows)}</div>')


def next_action(scan, judgment):
    na = judgment.get("next_action")
    if not na or not na.get("text"):
        raise JudgmentError("next_action.text is required")
    text, meta = inline(na["text"]), ""
    if na.get("file"):
        t = find_task(scan, na, "next_action")
        meta = f' <span class="meta">{html.escape(task_label(t))}</span>'
    return f'<div class="next"><strong>Next action</strong>{text}{meta}</div>'


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


def mechanical_note():
    return ('<p class="note">Next action and agenda come from the next '
            '<code>/para-daily-brief</code> run.</p>')


# --------------------------------------------------------------------------- the page

CSS = """
:root{--bg:#F7F7F4;--surface:#FFFFFF;--ink:#20242B;--muted:#6B7280;--line:#E3E4DF;
--accent:#1F6E68;--accent-soft:#E4EFED;--alert:#B4423A;--upcoming:#3E6C93;--undated:#C9CCC3;--chip:#EEEFEA}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
--bg:#14171B;--surface:#1C2026;--ink:#E7E5DF;--muted:#8E959F;--line:#2C313A;--accent:#55A79D;
--accent-soft:#1E3330;--alert:#D06B60;--upcoming:#6E9CC4;--undated:#3B414B;--chip:#262B33}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#14171B;--surface:#1C2026;--ink:#E7E5DF;
--muted:#8E959F;--line:#2C313A;--accent:#55A79D;--accent-soft:#1E3330;--alert:#D06B60;
--upcoming:#6E9CC4;--undated:#3B414B;--chip:#262B33}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.5}
code,.meta,.date,.tile b,.badge,.row .n,.agenda time{font-family:Consolas,"SF Mono",Menlo,monospace}
code{font-size:.92em}
.wrap{max-width:880px;margin:0 auto;padding:2rem 1rem 3rem}
header{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;flex-wrap:wrap;margin-bottom:1.25rem}
h1{font-size:1.65rem;font-weight:700;margin:0;letter-spacing:-.015em}
h1 small{font-weight:600;color:var(--accent)}
.date{color:var(--muted);font-size:.85rem}
h2{font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);margin:1.75rem 0 .6rem}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:.6rem}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:.6rem .75rem}
.tile b{display:block;font-size:1.4rem;font-weight:600;font-variant-numeric:tabular-nums}
.tile span{font-size:.75rem;color:var(--muted)}
.tile.alert b{color:var(--alert)}
label.tile{cursor:pointer}
label.tile:hover{border-color:var(--accent)}
.toggle{position:absolute;opacity:0;width:1px;height:1px;pointer-events:none}
.panel{display:none;margin-top:.6rem;background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:.6rem .9rem .1rem}
#tile-overdue:checked~.panels .p-overdue,#tile-week:checked~.panels .p-week,#tile-undated:checked~.panels .p-undated{display:block}
#tile-overdue:checked~.tiles [for=tile-overdue],#tile-week:checked~.tiles [for=tile-week],#tile-undated:checked~.tiles [for=tile-undated]{border-color:var(--accent);background:var(--accent-soft)}
#tile-overdue:focus-visible~.tiles [for=tile-overdue],#tile-week:focus-visible~.tiles [for=tile-week],#tile-undated:focus-visible~.tiles [for=tile-undated]{outline:2px solid var(--accent);outline-offset:2px}
.label{font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:.15rem 0 .3rem}
.chart{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:.9rem 1rem .6rem}
.row{display:grid;grid-template-columns:minmax(0,13rem) minmax(4rem,1fr) auto;gap:.6rem;align-items:center;padding:.25rem 0}
.row .name{font-size:.85rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.badge{display:inline-block;font-size:.65rem;color:var(--muted);background:var(--chip);border-radius:3px;padding:0 .25rem;margin-right:.3rem}
.bar{display:flex;height:14px;border-radius:3px;overflow:hidden}
.bar i{display:block;height:100%}
.seg-over{background:var(--alert)}.seg-up{background:var(--upcoming)}.seg-und{background:var(--undated)}
.row .n{font-size:.75rem;color:var(--muted);text-align:right;white-space:nowrap}
.row .n b,.rest b,.totals b,.pipeline b{color:var(--ink);font-weight:600}
.legend{display:flex;flex-wrap:wrap;gap:1rem;font-size:.72rem;color:var(--muted);padding:.6rem .1rem .1rem;border-top:1px solid var(--line);margin-top:.5rem}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:.3rem}
.rest,.totals{font-size:.8rem;color:var(--muted);padding:.25rem .1rem 0}
summary{cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}
summary:hover .name,summary.rest:hover{color:var(--accent)}
summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
.row .name::before,summary.rest::before,summary.x::before{content:"▸";display:inline-block;width:.9rem;color:var(--muted);transition:transform .15s}
details[open]>summary .name::before,details[open]>summary.rest::before,details[open]>summary.x::before{transform:rotate(90deg)}
summary.x:hover{color:var(--accent)}
.drill{list-style:none;margin:.15rem 0 .55rem .45rem;padding:.2rem 0 .2rem .9rem;border-left:2px solid var(--line);display:grid;gap:.3rem;font-size:.82rem}
.drill li{display:flex;flex-wrap:wrap;align-items:baseline;gap:.2rem .5rem}
.drill i{display:inline-block;width:8px;height:8px;border-radius:2px;flex:none}
.drill span{min-width:0}
.sub{color:var(--muted)}
.pipeline{font-size:.82rem;color:var(--muted);margin:.6rem 0 0}
.pipeline+.pipeline{margin-top:.1rem}
.flags{list-style:none;margin:0;padding:0;display:grid;gap:.35rem}
.flags li{background:var(--chip);border-left:3px solid var(--alert);border-radius:0 5px 5px 0;padding:.5rem .75rem;font-size:.85rem}
.flags .drill{margin:.45rem 0 .1rem .45rem}.flags .drill li{background:none;border:0;padding:0}
ol.now{list-style:none;margin:0;padding:0;counter-reset:now;display:grid;gap:.4rem}
ol.now li{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:.55rem .75rem .55rem 2.5rem;position:relative;font-size:.9rem}
ol.now li::before{counter-increment:now;content:counter(now);position:absolute;left:.8rem;top:.55rem;font-family:Consolas,monospace;font-size:.82rem;color:var(--accent);font-weight:600}
.meta{font-size:.72rem;color:var(--muted)}
.meta .due,.dormant{color:var(--alert)}
.later{font-size:.82rem;color:var(--muted);margin-top:.5rem}
.agenda{display:grid;gap:.25rem}
.agenda .day{font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);padding:.5rem .1rem 0}
.agenda .ev{display:grid;grid-template-columns:7.5rem 1fr;gap:.6rem;padding:.4rem .1rem;border-bottom:1px solid var(--line);font-size:.9rem}
.agenda time{font-size:.78rem;color:var(--accent)}
.note{font-size:.75rem;color:var(--muted);margin-top:.5rem}
.list{display:grid;gap:.4rem}
.item{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:.5rem .75rem;font-size:.85rem}
.head{display:flex;gap:.6rem;align-items:baseline;flex-wrap:wrap}
.head b{font-weight:600}.head span{min-width:0}.dormant{font-size:.75rem}
.head .meta{flex:1 1 auto;text-align:right}
.more{padding:.5rem 0 .1rem .9rem;display:grid;gap:.25rem;font-size:.82rem}
.more .drill{margin:0 0 .3rem}
.facts{color:var(--muted)}.facts b{color:var(--ink);font-weight:600}
.revisit{border-left:2px solid var(--accent);padding-left:.6rem;color:var(--ink)}
.excerpt{color:var(--ink)}
.next{margin-top:1.9rem;background:var(--accent-soft);border-left:3px solid var(--accent);border-radius:0 6px 6px 0;padding:.75rem 1rem;font-size:.9rem}
.next strong{color:var(--accent);text-transform:uppercase;font-size:.7rem;letter-spacing:.08em;display:block;margin-bottom:.2rem}
footer{margin-top:1.1rem;font-size:.72rem;color:var(--muted)}
@media (max-width:620px){.row{grid-template-columns:1fr;gap:.2rem}.row .n{text-align:left;white-space:normal}
.agenda .ev{grid-template-columns:1fr;gap:.1rem}}
"""


def render(scan, judgment=None):
    """The page: from the model's judgment file, or, with none, from the scan alone."""
    if scan.get("scope") != "vault":
        raise JudgmentError("the dashboard is a vault-wide page; an entity scope has none")
    mechanical = judgment is None
    if mechanical:
        judgment = {"now": mechanical_now(scan), "flags": mechanical_flags(scan)}
    name = display_name(scan["vault"])
    title = f"{name} Dashboard"
    body = [f'<header><h1>{html.escape(name)} <small>· Daily Brief</small></h1>'
            f'<span class="date">{long_date(scan["today"])}</span></header>']
    body += [tiles(scan), entity_chart(scan), flags(scan, judgment), now_panel(scan, judgment),
             agenda(judgment), ideas(scan), triage(scan),
             mechanical_note() if mechanical else next_action(scan, judgment),
             f'<footer>Generated {scan["today"]} '
             f'{"from the scan alone" if mechanical else "by /para-daily-brief"} · read-only: '
             f'repairs via /para-deep-clean</footer>']
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{CSS}</style></head><body>'
            f'<div class="wrap">{"".join(b for b in body if b)}</div></body></html>\n')
    return title, page


# ------------------------------------------------------------------ remembered URL

def cache_file(paraos_home=None):
    return paraos_home_dir(paraos_home) / "cache" / "daily-brief" / "dashboards.json"


def vault_key(vault):
    return Path(vault).resolve().as_posix().lower()


def load_cache(paraos_home=None):
    path = cache_file(paraos_home)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def remembered_url(vault, paraos_home=None):
    entry = load_cache(paraos_home).get(vault_key(vault))
    return entry.get("url") if isinstance(entry, dict) else None


def remember(vault, url, paraos_home=None):
    path = cache_file(paraos_home)
    data = load_cache(paraos_home)
    data[vault_key(vault)] = {"url": url, "title": f"{display_name(vault)} Dashboard"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render the daily-brief dashboard page.")
    ap.add_argument("--scan", help="brief_scan.py output")
    ap.add_argument("--judgment", help="the model's judgment file")
    ap.add_argument("--mechanical", action="store_true",
                    help="render from the scan alone, with no judgment file")
    ap.add_argument("--out", help="where to write the page (never inside the vault)")
    ap.add_argument("--remember", metavar="URL", help="store the published artifact URL")
    ap.add_argument("--vault", help="vault root, with --remember")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if args.remember:
        if not args.vault:
            ap.error("--remember needs --vault")
        path = remember(args.vault, args.remember)
        print(json.dumps({"remembered": args.remember, "cache": path.as_posix()}))
        return 0
    if args.mechanical and args.judgment:
        ap.error("--mechanical renders without a judgment file; drop one or the other")
    if not (args.scan and args.out and (args.judgment or args.mechanical)):
        ap.error("render needs --scan, --out and either --judgment or --mechanical")

    scan = json.loads(Path(args.scan).read_text(encoding="utf-8"))
    judgment = None if args.mechanical else \
        json.loads(Path(args.judgment).read_text(encoding="utf-8"))
    out = Path(args.out).resolve()
    if out.is_relative_to(Path(scan["vault"]).resolve()):
        print("render_dashboard: --out is inside the vault; write it to a scratch folder",
              file=sys.stderr)
        return 2
    try:
        title, page = render(scan, judgment)
    except JudgmentError as wrong:
        print(f"render_dashboard: {wrong}", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(json.dumps({"out": out.as_posix(), "title": title, "description": DESCRIPTION,
                      "url": remembered_url(scan["vault"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
