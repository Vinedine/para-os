#!/usr/bin/env python3
"""The vault scan of /para-command-center: every vault the registry lists, scanned the way its
own /para-daily-brief scans it, as one JSON document on stdout.

    py -3 global_scan.py [--today YYYY-MM-DD] [--paraos-home DIR] [--model <id>] [--indent N]

Read-only: never writes a file. Each vault's numbers come from para-daily-brief's
`brief_scan.scan()`, so they cannot disagree with that vault's own brief; which entries are
read, and what a malformed or missing one becomes, is para-audit's
`excluded_status()`. Both are found beside this skill, or in a para-os checkout.

How a vault is shown follows the operator's role in it: `paraos_vault.writer()` against the
card `operator.json` names. A vault they keep is `full`, or `summary` where its registry entry
says `"brief": "summary"`; one they steward, are a member of, or whose roster does not name
them is `health` only, since action lines carry no assignee yet.

`vaults`, in registry order: `name`, `role` (null where the roster does not name the
operator), `treatment`, `machine` (the registry's, naming the machine that pulls the vault,
else null), `open`, `overdue`, `triage` (loose files in `triage/`, null with a `machine`),
`health`, the vault's health card as brief_scan.py's `health()` gives it, `kit` and
`deep_clean_audit`.

`tasks`: every dated open task of a `full` vault, with its `vault`.

`summaries`: per `summary` vault, its `overdue`, `today` and `this_week` counts, the areas
those come from (`by_area`, the largest first) and up to three top-priority items late or
due today (`top`).

`calendars`: every `## Agenda sources` row of a `full` or `summary` vault, one per
`endpoint` (the calendar's account, whatever connector a vault wrote), with the `vaults`
declaring it, so each calendar is read once. `meetings`:
every `meetings.md` line of those vaults (outside `archive/`) from today to `horizon`, a
`🔁 every <cadence>` line repeated from its date, rolled forward past today where it was
never moved.

`excluded`: every entry not read, with `status` (`INVALID`, `UNREACHABLE`) and `reason`; a vault whose scan fails is `UNREACHABLE` too, never dropped.

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
    import audit_scan  # noqa: E402
    from audit_scan import SKILLS_ROOT, excluded_status  # noqa: E402
    sys.path.insert(0, str(SKILLS_ROOT / "para-daily-brief" / "scripts"))
    from brief_scan import scan  # noqa: E402
    from paraos_clone import clone_session  # noqa: E402
    from paraos_vault import (  # noqa: E402
        utf8_stdout,
        cadence_days, deep_clean_stamp, iso, live_lines, operator_card,
        paraos_home_dir, parse_date, read_lines, register_rows, registry, vault_paths,
        weekday_index, writer)
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


def treatment(entry, role):
    if role != "keeper":
        return "health"
    return "summary" if entry.get("brief") == "summary" else "full"


def open_kit(paraos_home=None):
    """The para-os clone the audit measures against, opened once for every vault: `(kit, ref,
    in_development)`, or `(None, None, None)` with no clone, a clone that cannot be read, or
    a ref that does not resolve; the Kit signal then reads unknown."""
    try:
        clone, _ = audit_scan.find_clone(None, paraos_home)
        if clone is None:
            return None, None, None
        block, code, kit = audit_scan.open_clone(Path(clone).resolve(), None)
        if code or kit is None:
            return None, None, None
        ref = block["ref"]
        developing = audit_scan.master_template(kit.clone, ref, worktree=True)["marker"]
        in_development = developing if developing and developing > kit.master else None
        return kit, ref, in_development
    except Exception:  # noqa: BLE001  a clone the audit cannot open is unknown, not a crash
        return None, None, None


def kit_signal(entry, kit, ref, in_development):
    """The audit's per-vault check as one health signal: the findings count, how many of them
    /para-upgrade applies, and the revision verdict. Unknown where the audit does not judge."""
    if kit is None:
        return {"level": "unknown", "verdict": None, "findings": None, "upgrade": None,
                "behind": None}
    try:
        row, _ = audit_scan.audit_vault(entry, kit, ref, in_development)
    except Exception:  # noqa: BLE001
        return {"level": "unknown", "verdict": None, "findings": None, "upgrade": None,
                "behind": None}
    verdict = row["revision"].get("verdict")
    findings = row["findings"]
    upgrade = sum(1 for f in findings if f.get("route") == "upgrade")
    behind = len(row["revision"].get("entries") or []) if verdict == "behind" else 0
    if verdict in ("ahead", "unverified"):
        level = "unknown"
    elif behind >= 2:
        level = "care"
    elif findings or behind:
        level = "watch"
    else:
        level = "ok"
    return {"level": level, "verdict": verdict, "findings": len(findings), "upgrade": upgrade,
            "behind": behind}


def deep_clean_audit(vault, paraos_home=None):
    """The last `/para-deep-clean audit` record for the vault, written by `clean_scan.py
    --record` beside the deep-clean stamp, or None."""
    path = deep_clean_stamp(vault, paraos_home).with_suffix(".audit.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not parse_date(data.get("date")):
        return None
    return {"date": data["date"], "total": int(data.get("total") or 0),
            "findings": data.get("findings") if isinstance(data.get("findings"), dict) else {}}


def vault_row(entry, report, home, role, shown, kit=None):
    t = report["totals"]
    name, machine = entry["name"], entry.get("machine") or None
    return {"name": name, "role": role, "treatment": shown, "machine": machine, "open": t["open"],
            "overdue": t["overdue"], "triage": None if machine else len(report["triage"]),
            "health": report["health"], "kit": kit_signal(entry, *(kit or (None, None, None))),
            "deep_clean_audit": deep_clean_audit(entry["path"], home)}


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
    """A recurring meeting's period in days: a cadence word, or a weekday, which is weekly, or
    every second one for `every 2 tuesdays`. None for other wording: the meeting shows once."""
    words = cadence[len("every"):].lower().split()
    count = int(words.pop(0)) if words and words[0].isdigit() else 1
    try:
        return cadence_days(cadence) or (7 * count if words and
                                         weekday_index(words[0].rstrip("s")) is not None else None)
    except ValueError:
        return None


def meetings(vault, name, today, until):
    out = []
    for path in vault_paths(vault, "meetings.md"):
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


def add_calendars(calendars, vault, name):
    for row in calendar_rows(vault):
        cal = calendars.setdefault(row["endpoint"] or row["source"], dict(row, vaults=[]))
        cal["vaults"] += [] if name in cal["vaults"] else [name]


def calendars_only(entries, today, paraos_home=None):
    """What `build_report` says about calendars, without scanning a vault to say it."""
    me, calendars = operator_card(paraos_home), {}
    for entry in entries:
        if excluded_status(entry) is None:
            place = writer(entry["path"], me)
            if treatment(entry, place["role"] if place else None) != "health":
                add_calendars(calendars, entry["path"], entry["name"])
    return {"today": today.isoformat(), "horizon": iso(today + timedelta(days=HORIZON_DAYS)),
            "calendars": list(calendars.values())}


@clone_session()
def build_report(entries, today, paraos_home=None, model=None):
    home = paraos_home_dir(paraos_home)
    me = operator_card(paraos_home)
    until = today + timedelta(days=HORIZON_DAYS)
    out = {"today": today.isoformat(), "horizon": iso(until), "vaults": [], "tasks": [],
           "summaries": [], "calendars": [], "meetings": [], "excluded": []}
    calendars = {}
    kit = open_kit(paraos_home)
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
        out["vaults"].append(vault_row(entry, report, home, role, shown, kit))
        if shown == "full":
            out["tasks"] += [dict(t, vault=name) for t in report["tasks"]
                             if t["lane"] not in NOT_DATED and t["effective_date"]]
        elif shown == "summary":
            out["summaries"].append(summary(name, report))
        if shown != "health":
            add_calendars(calendars, entry["path"], name)
            out["meetings"] += meetings(entry["path"], name, today, until)
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
    utf8_stdout()
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
