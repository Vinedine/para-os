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
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "para-audit" / "scripts"))

try:
    from audit_scan import SKILLS_ROOT  # noqa: E402
    sys.path.insert(0, str(SKILLS_ROOT / "para-daily-brief" / "scripts"))
    from paraos_vault import WAITING_FLAG_DAYS, paraos_home_dir, parse_date  # noqa: E402
    from paraos_pages import PUBLISH, local_page, publish_choice, remembered_url, store  # noqa: E402
    from render_dashboard import HEALTH_SIGNALS, cut, health_card, plain  # noqa: E402
except ImportError as missing:
    print(f"render_global: {missing}. install para-audit, para-daily-brief and para-shared "
          "beside this skill", file=sys.stderr)
    sys.exit(2)

TEMPLATE = HERE / "global.html"
PAGE = "global-brief"
TITLE = "All Vaults"
DESCRIPTION = ("Every vault at once: today, this week and the next two weeks with their "
               "meetings, your own vaults by area and person, and each vault's health.")


class JudgmentError(ValueError):
    pass


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
                        "type": v["type"], "card": health_card(v)} for name, v in shown.items()],
            "signals": [{"label": label, "what": what, "why": why, "fix": plain(fix)}
                        for _, label, what, why, fix in HEALTH_SIGNALS],
            "excluded": scan["excluded"]}


def render(scan, judgment, local=False):
    data = page_data(scan, judgment, local)
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    page = TEMPLATE.read_text(encoding="utf-8")
    return page.replace("__PARAOS_TITLE__", html.escape(TITLE)).replace("__PARAOS_DATA__", blob)


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
        page = render(scan, judgment, local=publish == "local")
    except JudgmentError as wrong:
        print(f"render_global: {wrong}", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(json.dumps({"out": out.as_posix(), "page": PAGE, "publish": publish, "title": TITLE,
                      "description": DESCRIPTION, "key": key.as_posix(),
                      "url": remembered_url(key, PAGE, args.paraos_home)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
