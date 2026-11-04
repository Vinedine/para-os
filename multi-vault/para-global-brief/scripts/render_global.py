#!/usr/bin/env python3
"""The page of /para-global-brief, rendered from the scan and a small judgment file.

    py -3 render_global.py --scan <global_scan output> --judgment <judgment.json> [--out <page.html>]
    py -3 render_global.py --publish claude|local [--paraos-home DIR]

The page is `global.html` beside this script with the data embedded; it loads nothing from
the network. Where it goes, and the artifact it was last published to, is para-shared's
`paraos_pages.py` under the page name `global-brief`, keyed by the para-os home, which stands
in for a vault since the page belongs to none. Render prints one JSON line: `out`, `page`,
`publish`, the page's `title` and `description`, `key` (the para-os home, the `--vault` that
paraos_pages.py's `remember` takes) and `url`, the artifact last published to, or null.

Everything with one right answer comes from the scan: the bands of dated items, the areas
and people of the vaults the operator keeps, the summed vaults, every vault's health card
(worded by para-daily-brief's render_dashboard.py, so the two pages agree) and the meetings
in `meetings.md`. The judgment file holds only what the model decides or fetched:

    {"next_action": {"text": "Check that ...", "vault": "Family",
                     "file": "projects/x/actions.md", "line": 12},
     "events": [{"date": "YYYY-MM-DD", "start": "13:00", "end": "14:00", "title": "...",
                 "source": "workspace"}],
     "agenda_note": "optional muted line: a calendar that failed, and why"}

`file` and `line` are optional; given, they must name a task of the scan, or the render
exits 2. `events` are the calendars' meetings from today to the scan's `horizon`, each
`source` the calendar's Source name; an event matching a `meetings.md` line on date, start
and title, case and spacing ignored, shows once.

Every render also writes the data the page embeds, plus `generated_at` (the render's local
time with its offset), to `<para-os home>/cache/global-brief/brief.json` through a temporary
file, so a script can show today's next action and meetings without a model. Among its
fields: `today`, `next_action` (`text`, `vault`), `events` (`date`, `start`, `end`, `title`,
`source`, `recurring`), `tasks` and each of `summaries`' `top` (`vault`, `text`, `date`,
`priority`, `file`, `line`), `entities`, `health` and `people`. `read_brief()` reads it back
with `stale` set: older than 26 hours, the next action is stale, and the reader names instead
the oldest item dated before its own today among those with the highest priority marker, or
null.
"""

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "para-audit" / "scripts"))

try:
    from audit_scan import SKILLS_ROOT  # noqa: E402
    sys.path.insert(0, str(SKILLS_ROOT / "para-daily-brief" / "scripts"))
    from paraos_vault import PRIORITY_RANK, WAITING_FLAG_DAYS, paraos_home_dir, parse_date  # noqa: E402
    from paraos_pages import PUBLISH, local_page, publish_choice, remembered_url, store  # noqa: E402
    from render_dashboard import HEALTH_SIGNALS, cut, health_card, plain  # noqa: E402
except ImportError as missing:
    print(f"render_global: {missing}. install para-audit, para-daily-brief and para-shared "
          "beside this skill", file=sys.stderr)
    sys.exit(2)

TEMPLATE = HERE / "global.html"
PAGE = "global-brief"
STALE_AFTER = timedelta(hours=26)
TITLE = "All Vaults"
DESCRIPTION = ("Every vault at once: today, this week and the next two weeks with their "
               "meetings, your own vaults by area and person, and each vault's health.")


KIT_SIGNAL = ("kit", "Kit", "Kit files that differ from the para-os clone at stable, as /para-audit counts them.",
              "A current marker can sit on drifted files; the audit reads the files behind it.",
              "Run /para-upgrade for what it applies; the rest is yours to decide.")


class JudgmentError(ValueError):
    pass


def kit_value(k):
    """The Kit signal's figures in a few words, as the other signals are worded."""
    if k.get("verdict") == "ahead":
        return "not judged: ahead of the kit"
    if k.get("verdict") == "unverified":
        return "not judged: no marker"
    if k.get("findings") is None:
        return "not judged: no para-os clone"
    if not k["findings"]:
        return "current"
    text = f"{k['findings']} finding{'s' * (k['findings'] > 1)}"
    if k.get("upgrade"):
        text += f", {k['upgrade']} the upgrade applies"
    return text


def health_rows(v):
    """The vault's health card with the Kit row after Template and the deep-clean audit's
    count on the Deep clean row, where the scan carries them."""
    card = health_card(v)
    if not card:
        return None
    k = v.get("kit") or {"level": "unknown"}
    kit_row = {"key": "kit", "label": KIT_SIGNAL[1], "level": k["level"], "value": kit_value(k),
               "what": KIT_SIGNAL[2], "why": KIT_SIGNAL[3], "fix": plain(KIT_SIGNAL[4])}
    rows = []
    for r in card["rows"]:
        if r["key"] == "deep_clean" and v.get("deep_clean_audit"):
            a = v["deep_clean_audit"]
            days = (parse_date(v["today"]) - parse_date(a["date"])).days if v.get("today") else None
            when = "today" if days == 0 else f"{days}d ago" if days is not None else a["date"]
            r = dict(r, value=f"{r['value']} · audit {when}: {a['total']} finding{'s' * (a['total'] != 1)}")
        rows.append(r)
        if r["key"] == "template":
            rows.append(kit_row)
    return dict(card, rows=rows)


def task(t):
    return {"vault": t["vault"], "text": cut(t["text"]), "date": t["effective_date"],
            "priority": t["priority"], "recurring": t["recurring"], "file": t["file"],
            "line": t["line"]}


def event_key(e):
    return (e["date"], e.get("start") or "", re.sub(r"\s+", " ", e["title"]).strip().lower())


def events(scan, judgment):
    """The scan's meetings and the calendars' events, one per date, start and title."""
    out, seen = [], set()
    fetched = []
    for e in judgment.get("events") or []:
        if not parse_date(e.get("date")) or not e.get("title"):
            raise JudgmentError(f"an event needs a YYYY-MM-DD date and a title: {e}")
        fetched.append({"date": e["date"], "start": e.get("start"), "end": e.get("end"),
                        "title": plain(e["title"]), "source": e.get("source") or "calendar",
                        "recurring": bool(e.get("recurring"))})
    own = [dict(m, source=m["vault"]) for m in scan["meetings"]]
    for e in sorted(own + fetched, key=lambda e: (e["date"], e.get("start") or "")):
        if event_key(e) not in seen:
            seen.add(event_key(e))
            out.append({k: e.get(k) for k in ("date", "start", "end", "title", "source",
                                               "recurring")})
    return out


def next_action(scan, judgment):
    na = judgment.get("next_action") or {}
    if not na.get("text"):
        raise JudgmentError("the judgment names no next_action text")
    if na.get("file") or na.get("line"):
        pool = scan["tasks"] + [t for s in scan["summaries"] for t in s["top"]]
        if not any(t["file"] == na.get("file") and t["line"] == na.get("line")
                   and t["vault"] == na.get("vault") for t in pool):
            raise JudgmentError(f"next_action names {na.get('vault')}:{na.get('file')}:"
                                f"{na.get('line')}, which holds no task in the scan")
    return {"text": plain(na["text"]), "vault": na.get("vault")}


def page_data(scan, judgment, local):
    shown = {v["name"]: v for v in scan["vaults"]}
    return {"today": scan["today"], "local": local, "chase_days": WAITING_FLAG_DAYS,
            "next_action": next_action(scan, judgment),
            "tasks": [task(t) for t in scan["tasks"]],
            "own_vaults": [v["name"] for v in scan["vaults"] if v["treatment"] == "full"],
            "entities": [{k: e[k] for k in ("vault", "bucket", "label", "open", "overdue",
                                             "undated")} for e in scan["entities"]],
            "undated": scan["undated"], "people": scan["people"],
            "summaries": [dict(s, top=[task(t) for t in s["top"]]) for s in scan["summaries"]],
            "events": events(scan, judgment), "agenda_note": plain(judgment.get("agenda_note")),
            "health": [{"vault": name, "role": v["role"], "treatment": v["treatment"],
                        "type": v["type"], "card": health_rows(dict(v, today=scan["today"]))}
                       for name, v in shown.items()],
            "signals": [{"label": label, "what": what, "why": why, "fix": plain(fix)}
                        for _, label, what, why, fix in with_kit(HEALTH_SIGNALS)],
            "funnel_url": scan.get("funnel_url"),
            "excluded": scan["excluded"]}


def with_kit(signals):
    """HEALTH_SIGNALS with the Kit signal after Template, the order the rows take."""
    out = []
    for s in signals:
        out.append(s)
        if s[0] == "template":
            out.append(KIT_SIGNAL)
    return out


def render(scan, judgment, local=False):
    return page(page_data(scan, judgment, local))


def page(data):
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    template = TEMPLATE.read_text(encoding="utf-8")
    return template.replace("__PARAOS_TITLE__", html.escape(TITLE)).replace("__PARAOS_DATA__", blob)


def brief_file(paraos_home=None):
    return paraos_home_dir(paraos_home) / "cache" / PAGE / "brief.json"


def write_brief(data, paraos_home=None):
    path = brief_file(paraos_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    stamped = dict(data, generated_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    tmp.write_text(json.dumps(stamped, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def read_brief(paraos_home=None, now=None):
    """brief.json with `stale` set and, when stale, the fallback next action; None without one."""
    try:
        data = json.loads(brief_file(paraos_home).read_text(encoding="utf-8"))
        made = datetime.fromisoformat(data["generated_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    now = now or datetime.now().astimezone()
    data["stale"] = now - made > STALE_AFTER
    if data["stale"]:
        today = now.date().isoformat()
        late = [t for t in data["tasks"] + [t for s in data["summaries"] for t in s["top"]]
                if t["date"] < today]
        pick = min(late, default=None,
                   key=lambda t: (-PRIORITY_RANK.get(t["priority"] or "", 0), t["date"]))
        data["next_action"] = pick and {"text": pick["text"], "vault": pick["vault"]}
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render the global-brief page.")
    ap.add_argument("--scan", help="global_scan.py output")
    ap.add_argument("--judgment", help="the model's judgment file")
    ap.add_argument("--out", help="where to write a page for claude.ai")
    ap.add_argument("--publish", choices=PUBLISH, help="where the page goes")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    key = paraos_home_dir(args.paraos_home)
    if args.publish:
        path = store(key, PAGE, args.paraos_home, publish=args.publish)
        print(json.dumps({"publish": args.publish, "cache": path.as_posix()}))
        return 0
    if not (args.scan and args.judgment):
        ap.error("render needs --scan and --judgment")
    scan = json.loads(Path(args.scan).read_text(encoding="utf-8"))
    judgment = json.loads(Path(args.judgment).read_text(encoding="utf-8"))
    publish = publish_choice(key, PAGE, args.paraos_home)
    if publish == "local":
        out = local_page(key, PAGE, args.paraos_home)
    elif args.out:
        out = Path(args.out).resolve()
    else:
        ap.error("this page publishes to claude.ai: name it with --out")
    try:
        data = page_data(scan, judgment, local=publish == "local")
    except JudgmentError as wrong:
        print(f"render_global: {wrong}", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page(data), encoding="utf-8")
    write_brief(data, args.paraos_home)
    print(json.dumps({"out": out.as_posix(), "page": PAGE, "publish": publish, "title": TITLE,
                      "description": DESCRIPTION, "key": key.as_posix(),
                      "url": remembered_url(key, PAGE, args.paraos_home)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
