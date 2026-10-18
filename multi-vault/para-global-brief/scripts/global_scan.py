#!/usr/bin/env python3
"""The mechanics of /para-global-brief: every vault the registry lists, scanned the way its
own /para-daily-brief scans it, as one JSON document on stdout.

    py -3 global_scan.py [--today YYYY-MM-DD] [--paraos-home DIR] [--indent N]

Read-only: never writes a file. Each vault's numbers come from para-daily-brief's
`brief_scan.scan()`, so they cannot disagree with that vault's own brief; which entries are
read, and what a retired, malformed or missing one becomes, is para-audit's
`excluded_status()`. Both are found beside this skill, or in a para-os checkout.

`vaults`, in registry order: `name`, `open`, `overdue`, `this_week` (due in the next seven
days), `undated`, `triage` (loose files in `triage/`), `flags` (the name of every health flag
the scan fired) and `proposal`, the newest
`<paraos home>/cache/triage/proposals/<name>-<YYYYMMDD-HHMM>.md` by name, else null.

`urgent`: every task overdue or due today across the vaults, each with its `vault`, sorted
as render_dashboard.py's `--mechanical` sorts a vault's Next action, uncapped.

`excluded`: every entry not read, with `status` (`RETIRED (excluded)`, `INVALID`,
`UNREACHABLE`) and `reason`; a vault whose scan fails is `UNREACHABLE` too, never dropped.

Exit codes: 0 answered; 2 the libraries are missing; 3 no registry, or one listing no entry.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "para-audit" / "scripts"))

try:
    from audit_scan import SKILLS_ROOT, excluded_status  # noqa: E402
    sys.path.insert(0, str(SKILLS_ROOT / "para-daily-brief" / "scripts"))
    from brief_scan import scan  # noqa: E402
    from paraos_vault import paraos_home_dir, parse_date, registry  # noqa: E402
    from render_dashboard import now_key  # noqa: E402
except ImportError as missing:
    print(f"global_scan: {missing}. install para-audit, para-daily-brief and para-shared "
          "beside this skill", file=sys.stderr)
    sys.exit(2)

URGENT_LANES = ("overdue", "today")


def proposal(home, name):
    found = sorted((home / "cache" / "triage" / "proposals").glob(f"{name}-{'[0-9]' * 8}-{'[0-9]' * 4}.md"))
    return found[-1].as_posix() if found else None


def fired(value):
    """A flag's value is a list, a dict of lists (`misplaced`), or null."""
    return any(value.values()) if isinstance(value, dict) else bool(value)


def vault_row(name, report, home):
    t, lanes = report["totals"], report["lanes"]
    return {"name": name, "open": t["open"], "overdue": t["overdue"],
            "this_week": len(lanes.get("this_week", [])), "undated": t["undated"],
            "triage": len(report["triage"]),
            "flags": sorted(k for k, v in report["flags"].items() if fired(v)),
            "proposal": proposal(home, name)}


def build_report(entries, today, paraos_home=None):
    home = paraos_home_dir(paraos_home)
    vaults, urgent, excluded = [], [], []
    for entry in entries:
        status = excluded_status(entry)
        name = entry.get("name") if isinstance(entry, dict) else None
        if status is None:
            try:
                report = scan(entry["path"], today, paraos_home=paraos_home)
            except OSError as err:
                status = ("UNREACHABLE", f"the scan could not read it: {err}")
        if status:
            excluded.append({"name": name, "status": status[0], "reason": status[1]})
            continue
        vaults.append(vault_row(name, report, home))
        keys = {(e["file"], e["line"])
                for lane in URGENT_LANES for e in report["lanes"].get(lane, [])}
        urgent += [dict(t, vault=name) for t in report["tasks"] if (t["file"], t["line"]) in keys]
    urgent.sort(key=lambda t: now_key(t) + (t["vault"],))
    return {"today": today.isoformat(), "vaults": vaults, "urgent": urgent, "excluded": excluded}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scan every registered vault for one brief.")
    ap.add_argument("--today", help="date to bucket against (default: the system date)")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    ap.add_argument("--indent", type=int, default=None, help="pretty-print the JSON")
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
    json.dump(build_report(entries, today, args.paraos_home), sys.stdout,
              ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
