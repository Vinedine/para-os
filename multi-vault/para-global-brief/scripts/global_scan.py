#!/usr/bin/env python3
"""The mechanics of /para-global-brief: every vault the registry lists, scanned the way its
own /para-daily-brief scans it, as one JSON document on stdout.

    py -3 global_scan.py [--today YYYY-MM-DD] [--paraos-home DIR] [--model <id>] [--indent N]

Read-only: never writes a file. Each vault's numbers come from para-daily-brief's
`brief_scan.scan()`, so they cannot disagree with that vault's own brief; which entries are
read, and what a retired, malformed or missing one becomes, is para-audit's
`excluded_status()`. Both are found beside this skill, or in a para-os checkout.

How a vault is shown follows the operator's role in it: `paraos_vault.writer()` against the
card `operator.json` names. A vault they keep is `full`, or `summary` where its registry entry
says `"brief": "summary"`; one they steward, are a member of, or whose roster does not name
them is `health` only, since action lines carry no assignee yet.

`vaults`, in registry order: `name`, `role` (null where the roster does not name the
operator), `treatment`, `type` (the vault's `**Type:**` label), `open`, `overdue`,
`this_week` (due in the next seven days), `undated`, `triage` (loose files in `triage/`),
`flags` (the name of every health flag the scan fired), `proposal` (the newest
`<paraos home>/cache/triage/proposals/<name>-<YYYYMMDD-HHMM>.md` by name, else null) and
`health`, the vault's health card as brief_scan.py's `health()` gives it.

`tasks`: every dated open task of a `full` vault, with its `vault`; `entities`: their
projects and areas; `undated`: their undated count; `people`: their contact cards with
something open either way, one row per card across them, with the `vaults` it is in.

`summaries`: per `summary` vault, its `overdue`, `today` and `this_week` counts, the areas
those come from (`by_area`, the largest first) and up to three top-priority items late or
due today (`top`).

`urgent`: every task of a `full` vault overdue or due today, with its `vault`, sorted as
render_dashboard.py's `--mechanical` sorts a vault's Next action, uncapped.

`calendars`: every `## Agenda sources` row of a `full` or `summary` vault, one per
`endpoint` (the calendar's account, whatever connector a vault wrote), with the `vaults`
declaring it, so each calendar is read once. `meetings`:
every `meetings.md` line of those vaults (outside `archive/`) from today to `horizon`, a
`🔁 every <cadence>` line repeated from its date, rolled forward past today where it was
never moved.

`excluded`: every entry not read, with `status` (`RETIRED (excluded)`, `INVALID`,
`UNREACHABLE`) and `reason`; a vault whose scan fails is `UNREACHABLE` too, never dropped.

Exit codes: 0 answered; 2 the libraries are missing; 3 no registry, or one listing no entry.
"""

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "para-audit" / "scripts"))

try:
    from audit_scan import SKILLS_ROOT, excluded_status  # noqa: E402
    sys.path.insert(0, str(SKILLS_ROOT / "para-daily-brief" / "scripts"))
    from brief_scan import scan  # noqa: E402
    from paraos_vault import (  # noqa: E402
        cadence_days, declarations, iso, live_lines, norm, operator_card, paraos_home_dir,
        parse_date, read_lines, register_rows, registry, weekday_index, writer)
    from render_dashboard import now_key  # noqa: E402
except ImportError as missing:
    print(f"global_scan: {missing}. install para-audit, para-daily-brief and para-shared "
          "beside this skill", file=sys.stderr)
    sys.exit(2)

URGENT_LANES = ("overdue", "today")
NOT_DATED = ("undated", "waiting", "waiting_on")
HORIZON_DAYS = 20      # this week and the two after it, whatever day the brief runs
TOP_ITEMS = 3
MEETING_RE = re.compile(r"^\s*[-*]\s+🗓️?\s*(\d{4}-\d{2}-\d{2})"
                        r"(?:\s+(\d{1,2}:\d{2})(?:\s*[-\u2013]\s*(\d{1,2}:\d{2}))?)?\s*·\s*(.+)$")
EVERY_RE = re.compile(r"🔁️?\s*(every\s+[^·]+?)\s*(?:·|$)")


def proposal(home, name):
    found = sorted((home / "cache" / "triage" / "proposals").glob(f"{name}-{'[0-9]' * 8}-{'[0-9]' * 4}.md"))
    return found[-1].as_posix() if found else None


def fired(value):
    """A flag's value is a list, a dict of lists (`misplaced`), or null."""
    return any(value.values()) if isinstance(value, dict) else bool(value)


def treatment(entry, role):
    if role != "keeper":
        return "health"
    return "summary" if entry.get("brief") == "summary" else "full"


def vault_row(entry, report, home, role, shown):
    t, lanes = report["totals"], report["lanes"]
    name = entry["name"]
    return {"name": name, "role": role, "treatment": shown,
            "type": declarations(entry["path"])["type"], "open": t["open"],
            "overdue": t["overdue"], "this_week": len(lanes.get("this_week", [])),
            "undated": t["undated"], "triage": len(report["triage"]),
            "flags": sorted(k for k, v in report["flags"].items() if fired(v)),
            "proposal": proposal(home, name), "health": report["health"]}


def in_lanes(report, lanes):
    keys = {(e["file"], e["line"]) for lane in lanes for e in report["lanes"].get(lane, [])}
    return [t for t in report["tasks"] if (t["file"], t["line"]) in keys]


def summary(name, report):
    counted = {lane: in_lanes(report, (lane,)) for lane in ("overdue", "today", "this_week")}
    areas = {}
    for tasks in counted.values():
        for t in tasks:
            areas[t["scope"]] = areas.get(t["scope"], 0) + 1
    late = sorted((t for t in in_lanes(report, URGENT_LANES) if t["priority"] == "🔺"),
                  key=now_key)
    return {"vault": name, **{lane: len(tasks) for lane, tasks in counted.items()},
            "by_area": sorted(areas.items(), key=lambda a: (-a[1], a[0])),
            "top": [dict(t, vault=name) for t in late[:TOP_ITEMS]]}


def merge_people(rows, name, people):
    """One row per contact card across the vaults, its counts added up."""
    for p in people:
        if not (p["owe"] or p["waiting"]):
            continue
        row = rows.setdefault(p["person"], dict(p, owe=0, waiting=0, vaults=[],
                                                owe_next_due=None, waiting_since=None,
                                                last_touch=None))
        row["vaults"].append(name)
        row["owe"] += p["owe"]
        row["waiting"] += p["waiting"]
        row["kind"] = row["kind"] or p["kind"]
        row["entity"] = row["entity"] or p["entity"]
        for key, pick in (("owe_next_due", min), ("waiting_since", min), ("last_touch", max)):
            seen = [v for v in (row[key], p[key]) if v]
            row[key] = pick(seen) if seen else None


def calendar_rows(vault):
    """The vault's `## Agenda sources` rows as {source, type, endpoint}."""
    out = []
    for r in register_rows(Path(vault) / "CLAUDE.md"):
        if (r["section"] or "").strip().lower() != "agenda sources":
            continue
        cell = {k.strip().lower(): v for k, v in r.items() if isinstance(k, str)}
        out.append({"source": cell.get("source", "").strip(),
                    "type": re.sub(r"\s+", " ", cell.get("type", "").replace("`", "")).strip(),
                    "endpoint": cell.get("endpoint", "").replace("`", "").strip().lower()})
    return out


def step_days(cadence):
    """A recurring meeting's period in days: a cadence word, or a weekday, which is weekly."""
    body = cadence[len("every"):].strip().lower()
    return cadence_days(cadence) or (7 if weekday_index(body.split()[0] if body else "")
                                     is not None else None)


def meetings(vault, name, today, until):
    out = []
    for path in sorted(Path(vault).rglob("meetings.md")):
        if "archive" in path.relative_to(vault).parts:
            continue
        for _, text in live_lines(read_lines(path)):
            m = MEETING_RE.match(text)
            day = parse_date(m.group(1)) if m else None
            if not day:
                continue
            every = EVERY_RE.search(text)
            title = re.sub(r"\s*🔁.*$", "", m.group(4).split(" · ")[0]).strip()
            step = step_days(every.group(1)) if every else None
            days = [day]
            if step:
                while day < today:
                    day += timedelta(days=step)
                days = []
                while day <= until:
                    days.append(day)
                    day += timedelta(days=step)
            out += [{"date": iso(d), "start": m.group(2), "end": m.group(3), "title": title,
                     "vault": name, "recurring": bool(step)}
                    for d in days if today <= d <= until]
    return out


def build_report(entries, today, paraos_home=None, model=None):
    home = paraos_home_dir(paraos_home)
    me = operator_card(paraos_home)
    until = today + timedelta(days=HORIZON_DAYS)
    out = {"today": today.isoformat(), "horizon": iso(until), "operator": me, "vaults": [],
           "tasks": [], "entities": [], "undated": 0, "people": [], "summaries": [],
           "urgent": [], "calendars": [], "meetings": [], "excluded": []}
    people, calendars = {}, {}
    for entry in entries:
        status = excluded_status(entry)
        name = entry.get("name") if isinstance(entry, dict) else None
        if status is None:
            try:
                report = scan(entry["path"], today, paraos_home=paraos_home, model=model)
            except OSError as err:
                status = ("UNREACHABLE", f"the scan could not read it: {err}")
        if status:
            out["excluded"].append({"name": name, "status": status[0], "reason": status[1]})
            continue
        place = writer(entry["path"], me)
        role = place["role"] if place else None
        shown = treatment(entry, role)
        out["vaults"].append(vault_row(entry, report, home, role, shown))
        if shown == "full":
            out["tasks"] += [dict(t, vault=name) for t in report["tasks"]
                             if t["lane"] not in NOT_DATED and t["effective_date"]]
            out["entities"] += [dict(e, vault=name) for e in report["entities"]]
            out["undated"] += report["totals"]["undated"]
            out["urgent"] += [dict(t, vault=name) for t in in_lanes(report, URGENT_LANES)]
            merge_people(people, name, report.get("people") or [])
        elif shown == "summary":
            out["summaries"].append(summary(name, report))
        if shown != "health":
            for row in calendar_rows(entry["path"]):
                cal = calendars.setdefault(row["endpoint"] or row["source"], dict(row, vaults=[]))
                cal["vaults"] += [] if name in cal["vaults"] else [name]
            out["meetings"] += meetings(entry["path"], name, today, until)
    out["urgent"].sort(key=lambda t: now_key(t) + (t["vault"],))
    out["people"] = sorted(people.values(), key=lambda p: (p["waiting_since"] or "9999",
                                                           p["owe_next_due"] or "9999", p["name"]))
    out["calendars"] = list(calendars.values())
    out["meetings"].sort(key=lambda e: (e["date"], e["start"] or "", e["title"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scan every registered vault for one brief.")
    ap.add_argument("--today", help="date to bucket against (default: the system date)")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    ap.add_argument("--indent", type=int, default=None, help="pretty-print the JSON")
    ap.add_argument("--model", help="the running model's id, for each health card's skills review")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    today = parse_date(args.today) if args.today else date.today()
    if not today:
        ap.error("--today wants YYYY-MM-DD")
    entries = registry(args.paraos_home)
    if not entries:
        print("global_scan: no registry, or one listing no vault", file=sys.stderr)
        return 3
    json.dump(build_report(entries, today, args.paraos_home, args.model), sys.stdout,
              ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
