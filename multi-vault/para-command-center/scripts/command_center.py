#!/usr/bin/env python3
"""The Command Center: every registered vault on one page, with what comes into it, the runs
that move it and what it produces. Built from files on disk; no model judgment goes into it.

    py -3 command_center.py [--events <events.json>] [--today YYYY-MM-DD] [--days N]
                            [--code-root DIR] [--offline] [--model <id>] [--out <page.html>]
                            [--paraos-home DIR]
    py -3 command_center.py --calendars [--today YYYY-MM-DD] [--paraos-home DIR]
    py -3 command_center.py --publish claude|local [--paraos-home DIR]

The page is `command-center.html` beside this script with the data embedded; it loads nothing
from the network. Where it goes, and the artifact it was last published to, is para-shared's
`paraos_pages.py` under the page name `command-center`, keyed by the para-os home, which
stands in for a vault since the page belongs to none. A run writes the page, writes the same
data to `<para-os home>/cache/command-center/data.json` through a temporary file, and prints
one JSON line: `out`, `page`, `publish`, the page's `title` and `description`, `key` (the
para-os home, the `--vault` that paraos_pages.py's `remember` takes) and `url`, the artifact
last published to, or null.

`--events` names the one input a script cannot read for itself, the calendars' meetings, which
the skill fetches through the vaults' agenda connectors:

    {"events": [{"date": "YYYY-MM-DD", "start": "13:00", "end": "14:00", "title": "...",
                 "source": "workspace", "recurring": false}],
     "note": "optional: a calendar that could not be read, and why"}

`--calendars` prints what to fetch, and builds nothing: `today`, `horizon` (the last day to
read) and `calendars`, each `## Agenda sources` row of a vault the operator keeps, once per
calendar account, with the `vaults` declaring it.

An event with no date or no title is dropped and counted in `notes`; one matching a
`meetings.md` line on date, start and title, case and spacing ignored, shows once. The events
given are kept in `<para-os home>/cache/command-center/events.json` and used again by a run
given none, such as the rebuild after an ingest. With none ever given, the agenda holds the
vaults' own `meetings.md` lines.

What the data holds, and where each part comes from:

- `tasks`, `agenda`, `health` and the counts of `vaults`: `global_scan.py` beside this script,
  which scans each vault the way its own `/para-daily-brief` does. A dated item's `band` is
  `late`, `today`, `week` (to Sunday), `next2` (the two weeks after) or `later`.
- `vaults` also carries where a vault stands on the page: the `neighbourhood` and `street` of
  its registry entry. An entry with neither stands in "Your vaults" where the operator keeps
  it, else in "Vaults you look after". `<para-os home>/past-vaults.json`, a list of `name`,
  `ended`, `neighbourhood`, `street` and `note`, adds vaults no longer read, shown as handed
  over with no counts: the registry itself lists only vaults that are read.
- `funnel` and `flows`: para-ingest's `funnel_page.gather()` over `--days` days (default 7)
  and the ingest ledger, a thread counted once per vault it was routed to. An item a
  scheduled run held for the operator is counted once, however many proposals list it, and
  only while it is still in the vault's triage folder. A recording
  source's notes are counted from its sync script's own ledger in each vault.
- `repos` and `sites`: the `owned` rows of each vault's code-repos table
  (`paraos_repos.py`), each repo looked for under `--code-root` (repeatable; default
  `~/Code`), then `git fetch`, `git status` and, for a GitHub remote, `gh` for open issues and
  the last workflow run. `--offline` skips the fetch and `gh`. A repo with nothing pending is
  fine however old its last commit.
- `nodes` and `edges`, every part and every link a file declares: each vault's triage and
  agenda sources, the connections registry (`paraos_connections.py`), the task registry and
  its run records (`paraos_runs.py`), the repo tables and the pages index. A script the
  registry does not list and whose code reaches outside is a part too: under the source of
  each listed CLI it runs, or under `Not labelled yet` where it names hosts alone, with what
  it calls, the skills that run it and its path in its `detail`. A scheduled run is
  `ok`, `watch` (its last record is older than its last due time), `warn` (partial), `bad`
  (failed) or `none` (no record yet). `meta.hub` is the run whose skill is `para-ingest`.
- `meta`: `today`, `generated_at`, `days`, `hub` and `notes`, what was missing or left out.

Exit codes: 0 answered; 2 the libraries are missing or an argument is wrong; 3 no registry, or
one listing no entry.
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "para-audit" / "scripts"))
sys.path.insert(0, str(HERE.parents[1] / "para-ingest" / "scripts"))

try:
    from audit_scan import SKILLS_ROOT  # noqa: E402
    sys.path.insert(0, str(SKILLS_ROOT / "para-daily-brief" / "scripts"))
    from funnel_page import gather as funnel_gather  # noqa: E402
    from global_scan import build_report, calendars_only  # noqa: E402
    from paraos_connections import gather as connections_gather, key as connection_key  # noqa: E402
    from paraos_pages import (  # noqa: E402
        PUBLISH, load_index, local_page, publish_choice, remembered_url, store, vault_key)
    from paraos_repos import list_repos  # noqa: E402
    from paraos_runs import parse_time, status as runs_status  # noqa: E402
    from paraos_vault import (  # noqa: E402
        date_arg, iso, paraos_home_dir, parse_date, read_json, registry, triage_sources,
        utf8_stdout,
    )
    from render_dashboard import cut, health_card, plain  # noqa: E402
except ImportError as missing:
    print(f"command_center: {missing}. install para-audit, para-daily-brief, para-ingest and "
          "para-shared beside this skill", file=sys.stderr)
    sys.exit(2)

TEMPLATE = HERE / "command-center.html"
PAGE = "command-center"
TITLE = "Command Center"
DESCRIPTION = ("Every vault on one map: what came in this week and where it went, how each "
               "vault stands, the scheduled runs, and what the vaults produce.")
DAYS = 7
QUIET_DAYS = 90
GRACE = timedelta(minutes=20)
LATE = timedelta(hours=1)
OWN, KEPT = "Your vaults", "Vaults you look after"
DAY_NAMES = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
KIT_SIGNAL = ("kit", "Kit", "Kit files that differ from the para-os clone at stable, as /para-audit counts them.",
              "Run /para-upgrade for what it applies; the rest is yours to decide.")
SEVERITY = {"ci": 3, "diverged": 3, "unpushed": 2, "dirty": 2, "behind": 2, "missing": 1,
            "quiet": 0, "clean": 0}
SEVERITY_WORD = {3: "bad", 2: "warn", 1: "mute", 0: "ok"}
UNLISTED = "not in the connections registry"
UNLABELLED = "Not labelled yet"


# ------------------------------------------------------------- the scan, as page rows

def band(day, today):
    """Where a dated item falls against today."""
    if day < today:
        return "late"
    if day == today:
        return "today"
    week_end = today + timedelta(days=6 - today.weekday())
    if day <= week_end:
        return "week"
    return "next2" if day <= week_end + timedelta(days=14) else "later"


def task_rows(scan, today):
    """Every dated open task the scan lists, and each summed vault's top items."""
    rows = []
    for t in scan["tasks"] + [t for s in scan["summaries"] for t in s["top"]]:
        day = parse_date(t.get("effective_date"))
        if not day:
            continue
        rows.append({"id": f"t{len(rows) + 1}", "vault": t["vault"], "text": cut(t["text"]),
                     "date": iso(day), "days_late": max(0, (today - day).days),
                     "band": band(day, today), "priority": t.get("priority") or "",
                     "recurring": t.get("recurring") or "", "file": t.get("file"),
                     "line": t.get("line")})
    return rows


def event_key(e):
    return (e["date"], e.get("start") or "", re.sub(r"\s+", " ", e["title"]).strip().lower())


def agenda_rows(scan, fetched, today):
    """`(rows, dropped)`: the vaults' own meetings and the calendars' events, one per date,
    start and title, and how many fetched events named no date or no title."""
    good, dropped = [], 0
    for e in fetched:
        if not isinstance(e, dict) or not parse_date(e.get("date")) or not e.get("title"):
            dropped += 1
            continue
        good.append({"date": e["date"], "start": e.get("start") or "", "end": e.get("end") or "",
                     "title": plain(str(e["title"])), "source": e.get("source") or "calendar",
                     "recurring": bool(e.get("recurring"))})
    own = [{"date": m["date"], "start": m.get("start") or "", "end": m.get("end") or "",
            "title": m["title"], "source": m["vault"], "recurring": bool(m.get("recurring"))}
           for m in scan["meetings"]]
    rows, seen = [], set()
    for e in sorted(own + good, key=lambda e: (e["date"], e["start"])):
        if event_key(e) in seen:
            continue
        seen.add(event_key(e))
        rows.append(dict(e, id=f"e{len(rows) + 1}", band=band(parse_date(e["date"]), today)))
    return rows, dropped


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


def health_rows(v, today):
    """The vault's health card with the Kit row after Template and the deep-clean audit's
    count on the Deep clean row, where the scan carries them. None where it has no card."""
    card = health_card(v)
    if not card:
        return None
    k = v.get("kit") or {"level": "unknown"}
    kit_row = {"key": "kit", "label": KIT_SIGNAL[1], "level": k["level"], "value": kit_value(k),
               "what": KIT_SIGNAL[2], "fix": plain(KIT_SIGNAL[3])}
    rows = []
    for r in card["rows"]:
        if r["key"] == "deep_clean" and v.get("deep_clean_audit"):
            a = v["deep_clean_audit"]
            days = (today - parse_date(a["date"])).days
            when = "today" if days == 0 else f"{days}d ago"
            r = dict(r, value=f"{r['value']} · audit {when}: {a['total']} finding{'s' * (a['total'] != 1)}")
        rows.append(r)
        if r["key"] == "template":
            rows.append(kit_row)
    return dict(card, rows=rows)


def places(entries, scan_vaults):
    """`{name: (neighbourhood, rank, street)}`: where each vault stands, from its registry
    entry, the neighbourhoods ranked in the order the registry first names them."""
    by_name = {v["name"]: v for v in scan_vaults}
    out, order = {}, []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("name") not in by_name:
            continue
        hood = str(entry.get("neighbourhood") or "").strip()
        if not hood:
            hood = OWN if by_name[entry["name"]]["treatment"] != "health" else KEPT
        if hood not in order:
            order.append(hood)
        out[entry["name"]] = (hood, order.index(hood), str(entry.get("street") or "").strip())
    return out, order


def vault_rows(scan, entries, inbound, repos, today, past):
    """`(rows, health)`: one row per vault the scan read, then the vaults handed over, and
    every health signal of every card."""
    where, order = places(entries, scan["vaults"])
    rows, health = [], []
    for v in scan["vaults"]:
        name = v["name"]
        card = health_rows(v, today) or {"level": "unknown", "word": "not judged", "rows": []}
        value = {r["key"]: r["value"] for r in card["rows"]}
        oldest = re.search(r"oldest (\d+)d", value.get("triage", ""))
        mine = [r for r in repos if r["vault"] == name]
        hood, rank, street = where[name]
        rows.append({
            "vault": name, "role": v["role"] or "", "treatment": v["treatment"],
            "machine": v["machine"] or "", "state": "", "note": "",
            "level": card["level"], "word": card["word"], "open": v["open"],
            "overdue": v["overdue"], "triage_items": v["triage"] or 0,
            "triage_oldest_days": int(oldest.group(1)) if oldest else 0,
            "held": inbound["held"].get(name, 0), "routed": inbound["routed"].get(name, 0),
            "acted": inbound["acted"].get(name, 0), "last_edit": value.get("last_edit", ""),
            "neighbourhood": hood, "neighbourhood_rank": rank, "street": street,
            "repos": len(mine)})
        health += [{"id": f"{name}:{r['key']}", "vault": name, "key": r["key"], "label": r["label"],
                    "value": r["value"], "level": r["level"], "what": r.get("what", ""),
                    "fix": r.get("fix", "")} for r in card["rows"]]
    listed = {r["vault"] for r in rows}
    for p in past:
        if not isinstance(p, dict) or not p.get("name") or p["name"] in listed:
            continue
        hood = str(p.get("neighbourhood") or "").strip() or KEPT
        if hood not in order:
            order.append(hood)
        ended = str(p.get("ended") or "").strip()
        rows.append({
            "vault": p["name"], "role": "", "treatment": "none", "machine": "",
            "state": "handed over" + (f", ended {ended}" if ended else ""),
            "note": str(p.get("note") or "").strip() or "Handed over: no longer read on this machine.",
            "level": "", "word": "", "open": 0, "overdue": 0, "triage_items": 0,
            "triage_oldest_days": 0, "held": 0, "routed": 0, "acted": 0, "last_edit": "",
            "neighbourhood": hood, "neighbourhood_rank": order.index(hood),
            "street": str(p.get("street") or "").strip(), "repos": 0})
    return rows, health


# ------------------------------------------------------------- what came in

def flow_rows(home, since, labels):
    """Threads per mailbox and where each went in the window: a vault, the exclusion list, or
    no vault. A thread routed to two vaults is one row in each."""
    ledger = read_json(Path(home) / "cache" / "ingest" / "ledger.json", {})
    boxes = ledger.get("mailboxes") if isinstance(ledger, dict) else None
    counts = Counter()
    for mailbox, entries in (boxes.items() if isinstance(boxes, dict) else []):
        for e in (entries.values() if isinstance(entries, dict) else []):
            if not isinstance(e, dict) or (e.get("date") or "") < since:
                continue
            reason = (e.get("reason") or "").lower()
            if reason.startswith("excluded") or "excluded by triage-exclusions" in reason:
                counts[(mailbox, "", "excluded")] += 1
            elif reason.startswith("skipped") or (e.get("routed") and "suppressed" in reason):
                continue
            elif e.get("routed"):
                for vault in e["routed"]:
                    counts[(mailbox, vault, "vault")] += 1
            else:
                counts[(mailbox, "", "unrouted")] += 1
    return [{"id": f"{mailbox}>{kind}:{dest}", "address": mailbox,
             "label": labels.get(mailbox.lower(), mailbox), "dest": dest, "kind": kind, "count": n}
            for (mailbox, dest, kind), n in sorted(counts.items())]


def inbound(home, days, today, labels, entries=()):
    """The funnel's stages, the mail flows and the per-vault counts the page shows. An item a
    scheduled run held is counted once, however many proposals list it, and only while it is
    still in its vault's triage folder, where this machine can look."""
    f = funnel_gather(str(home), days, today)
    led = f["ledger"]
    acted, waiting = Counter(), {}
    roots = {e["name"]: here(e) for e in entries if isinstance(e, dict) and e.get("name")}
    for p in f["proposals"]:
        root = roots.get(p["vault"])
        for item in p["items"]:
            if item["item"] and (root is None or (root / "triage" / item["item"]).exists()):
                waiting.setdefault(p["vault"], set()).add(item["item"])
    held = Counter({vault: len(names) for vault, names in waiting.items()})
    for q in f["quarantine"]:
        if q["in_window"]:
            acted[q["vault"]] += len(q["items"])
    decided = sum(d["window"] for d in f["decisions"].values())
    accepted = sum(d["window_accepted"] for d in f["decisions"].values())
    stages = [
        ("fetch", "Fetched", "code", led["seen"], f"threads from {len(f['mailbox_vaults'])} mailboxes"),
        ("exclude", "Excluded by rule", "code", led["excluded"], "dropped by your exclusion list"),
        ("route", "Routed to a vault", "model", led["routed"], f"{led['unrouted']} belonged to no vault"),
        ("stage", "Staged in triage", "code", f["staged"], "notes written to triage folders"),
        ("classify", "Decided in triage", "model", decided, f"{accepted} took the recommendation"),
        ("execute", "Acted on unattended", "code", f["acted"], "moved to quarantine, nothing deleted"),
        ("operator", "Waiting for you", "you", sum(held.values()), "held by a scheduled run and still in triage"),
    ]
    return {"funnel": [{"stage": s, "order": i + 1, "label": label, "who": who, "value": value,
                        "detail": detail} for i, (s, label, who, value, detail) in enumerate(stages)],
            "flows": flow_rows(home, f["since"], labels), "held": held, "acted": acted,
            "routed": led["routed_per_vault"], "since": f["since"]}


def synced_counts(entries, since):
    """`{(script, vault): notes}` each sync script wrote in the window, from its own ledger,
    `resources/scripts/<script name>.synced.json` in the vault the note went to: the notes
    whose file name opens on a date in the window."""
    floor, out = since.replace("-", ""), Counter()
    for entry in entries:
        root = here(entry)
        if root is None:
            continue
        for row in triage_sources(root)["rows"]:
            if row["kind"] != "sync-script" or not row["path"]:
                continue
            script = script_name(row["path"])
            ledger = read_json(root / "resources" / "scripts" / f"{Path(script).stem}.synced.json", {})
            for note in (ledger.values() if isinstance(ledger, dict) else []):
                stamp = re.match(r"\d{8}", script_name(note)) if isinstance(note, str) else None
                if stamp and stamp.group(0) >= floor:
                    out[(script, entry["name"])] += 1
    return out


# ------------------------------------------------------------- repos and sites

def run_command(args, cwd=None, timeout=30):
    """A command's stdout, or None where it fails, is not installed or takes too long."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    try:
        done = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def host_of(remote):
    if not remote:
        return "none"
    if "github.com" in remote:
        return "GitHub"
    return "Azure DevOps" if "dev.azure.com" in remote or "visualstudio.com" in remote else "other"


def signal_of(row):
    """The one thing to know about a repo, worst first."""
    if row["ci_result"] in ("failure", "timed_out", "startup_failure"):
        return "ci", "Last CI run failed"
    if row["ahead"] and row["behind"]:
        return "diverged", f"{row['ahead']} local, {row['behind']} remote commits apart"
    if row["ahead"]:
        return "unpushed", f"{row['ahead']} unpushed commit{'s' * (row['ahead'] > 1)}"
    if row["dirty"]:
        return "dirty", f"{row['dirty']} uncommitted change{'s' * (row['dirty'] > 1)}"
    if row["behind"]:
        return "behind", f"{row['behind']} behind the remote"
    if row["days_quiet"] is not None and row["days_quiet"] > QUIET_DAYS:
        return "quiet", f"No commit in {row['days_quiet']} days"
    return "clean", "Clean"


def repo_state(name, folder, today, run=run_command, online=True):
    """A repo's local state, and for a GitHub remote its open issues and last workflow run."""
    row = {"repo": name, "host": "", "branch": "", "dirty": 0, "ahead": 0, "behind": 0,
           "last_commit": "", "days_quiet": None, "ci": "", "ci_result": "", "signal": "missing",
           "signal_label": "Not checked out here"}
    if folder is None:
        return row

    def git(*args, timeout=30):
        return run(["git", "-C", str(folder), *args], timeout=timeout)

    remote = git("remote", "get-url", "origin") or ""
    row["host"] = host_of(remote)
    if remote and online:
        git("fetch", "--quiet", "origin", timeout=60)
    row["branch"] = git("rev-parse", "--abbrev-ref", "HEAD") or ""
    row["dirty"] = len((git("status", "--porcelain") or "").splitlines())
    counts = (git("rev-list", "--left-right", "--count", "@{upstream}...HEAD") or "").split()
    if len(counts) == 2 and all(c.isdigit() for c in counts):
        row["behind"], row["ahead"] = int(counts[0]), int(counts[1])
    last = parse_date(git("log", "-1", "--format=%cs"))
    if last:
        row["last_commit"], row["days_quiet"] = iso(last), (today - last).days
    if row["host"] == "GitHub" and online:
        slug = re.sub(r"\.git$", "", re.sub(r".*github\.com[:/]", "", remote))
        try:
            latest = json.loads(run(["gh", "run", "list", "-R", slug, "--limit", "1", "--json",
                                     "conclusion,status,workflowName"]) or "[]")
        except ValueError:
            latest = []
        if isinstance(latest, list) and latest and isinstance(latest[0], dict):
            row["ci"] = latest[0].get("workflowName") or ""
            row["ci_result"] = latest[0].get("conclusion") or latest[0].get("status") or ""
    row["signal"], row["signal_label"] = signal_of(row)
    return row


def checkout(name, roots):
    """The folder a repo is checked out in, under the first code root that holds it."""
    for root in roots:
        folder = Path(root).expanduser() / name
        if (folder / ".git").exists():
            return folder
    return None


def here(entry):
    """A named registry entry's folder when this machine reads it and it is on disk, else None."""
    if not isinstance(entry, dict) or not entry.get("name") or entry.get("machine") or not entry.get("path"):
        return None
    path = Path(entry["path"])
    return path if path.is_dir() else None


def repo_rows(entries, paraos_home, roots, today, run=run_command, online=True):
    """`(repos, sites)`: every repo a vault owns with its state, and the website each builds."""
    repos, sites = [], []
    for entry in entries:
        root = here(entry)
        if root is None:
            continue
        for r in list_repos(root, paraos_home)["repos"]:
            if r["role"] != "owned":
                continue
            row = repo_state(r["repo"], checkout(r["repo"], roots), today, run, online)
            repos.append(dict(row, vault=entry["name"], what=r.get("what") or ""))
            if r.get("site"):
                sites.append({"site": r["site"], "repo": r["repo"], "vault": entry["name"],
                              "serves": r.get("serves") or entry["name"], "what": r.get("what") or ""})
    return repos, sites


# ------------------------------------------------------------- scheduled runs

def cron_field(field, low, high):
    """The values a cron field lists, or None for `*` and for what this reader does not expand."""
    if field == "*":
        return None
    values = set()
    for part in field.split(","):
        first, _, last = part.partition("-")
        if not first.isdigit() or (last and not last.isdigit()):
            return None
        values.update(range(int(first), int(last or first) + 1))
    return sorted(v for v in values if low <= v <= high) or None


def cron_days(field):
    """The days a cron day field lists, named or numbered. A range closing on Sunday closes on
    7, since 0 comes before the day it starts on."""
    text = field.lower().replace("-sun", "-7")
    for number, name in enumerate(DAY_NAMES):
        text = text.replace(name[:3].lower(), str(number))
    return cron_field(text, 0, 7)


def day_words(days):
    if days is None:
        return "every day"
    names = [DAY_NAMES[d % 7] for d in days]
    if len(days) > 2 and days == list(range(days[0], days[-1] + 1)):
        return f"{names[0]} to {names[-1]}"
    return " and ".join(n + "s" for n in names)


def schedule(cron):
    """`(times, words)` of a five-field cron line: its `HH:MM` fire times where the minute and
    hour fields list them, and the line in words. A line of another shape is its own words."""
    parts = str(cron or "").split()
    if len(parts) != 5:
        return [], str(cron or "")
    minutes, hours = cron_field(parts[0], 0, 59), cron_field(parts[1], 0, 23)
    times = [f"{h:02d}:{m:02d}" for h in hours for m in minutes] if minutes and hours else []
    return times, f"{' and '.join(times) or ' '.join(parts[:2])} {day_words(cron_days(parts[4]))}"


def last_due(cron, now):
    """The last moment before `now` a cron line was due, looking a week back. None where the
    line names a day of the month or a month, or lists no time."""
    parts = str(cron or "").split()
    if len(parts) != 5 or parts[2] != "*" or parts[3] != "*":
        return None
    minutes, hours = cron_field(parts[0], 0, 59), cron_field(parts[1], 0, 23)
    days = cron_days(parts[4])
    if not (minutes and hours):
        return None
    week = ((now - timedelta(days=back)).date() for back in range(8))
    moments = (datetime(day.year, day.month, day.day, h, m, tzinfo=now.tzinfo)
               for day in week if days is None or day.isoweekday() % 7 in {d % 7 for d in days}
               for h, m in sorted(((h, m) for h in hours for m in minutes), reverse=True))
    return next((moment for moment in moments if moment <= now), None)


def run_status(task, now):
    """How a scheduled run stands, from its last run record."""
    last = task.get("last")
    if not isinstance(last, dict):
        return "none"
    if last.get("status") == "failed":
        return "bad"
    if last.get("status") == "partial":
        return "warn"
    due, end = last_due(task.get("cron"), now), parse_time(last.get("end"))
    return "watch" if due and end and end < due - GRACE and now - due > LATE else "ok"


# ------------------------------------------------------------- the parts and their links

def script_name(path):
    return str(path or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def provider_name(text):
    """A provider as one source: its name up to a remark in parentheses or after a comma."""
    return re.split(r"\s*[(,]", str(text or ""), maxsplit=1)[0].strip()


def catalog(entries, vaults, calendars, flows, synced, routed, repos, sites, listed, boxes,
            tasks, pages, days, now):
    """`(nodes, edges, hub)`: every part of the system in six lanes (outside sources,
    connections, scheduled runs, vaults, repos, websites and pages) and every link a file
    declares between them. A link no file declares is not drawn."""
    nodes, edges = {}, {}
    labels = {b["address"].lower(): b["label"] for b in boxes}

    def node(nid, lane, label, kind, **more):
        nodes.setdefault(nid, dict({"id": nid, "lane": lane, "label": label, "kind": kind,
                                    "status": "none", "sub": "", "ref": "", "group": "",
                                    "detail": {}, "order": len(nodes)}, **more))
        return nid

    def edge(a, b, kind, count=0):
        e = edges.setdefault(f"{a}>{b}", {"id": f"{a}>{b}", "source": a, "target": b,
                                          "kind": kind, "count": 0})
        e["count"] += count
        return e

    def declared(kind, name):
        """The connections registry's entry for what a source row names, or None."""
        if kind == "script":
            return next((c for c in listed if c.get("kind") == "script"
                         and script_name(c.get("path")) == script_name(name)), None)
        return next((c for c in listed if c.get("kind") in ("mcp", "connector")
                     and connection_key(c.get("id")) == connection_key(name)), None)

    def connection(kind, name):
        """The node of the connection a source row or a task names, declared or not."""
        rec = declared(kind, name)
        ident = rec["id"] if rec else (script_name(name) if kind == "script" else name)
        sub = "read-only" if rec and rec.get("read_only") else (UNLISTED if not rec else "")
        return node(f"conn:{ident}", 1, ident, rec["kind"] if rec else kind, sub=sub,
                    detail={"provider": (rec or {}).get("provider") or "",
                            "writes": (rec or {}).get("writes") or ""}), rec

    for i, v in enumerate(vaults):
        if v["state"]:
            sub = v["state"]
        elif v["machine"]:
            sub = f"pulled on {v['machine']}"
        else:
            sub = f"{v['routed']} new · {v['triage_items']} in triage · {v['held']} held"
        node(f"vault:{v['vault']}", 3, v["vault"], "vault", status=v["level"] or "none", sub=sub,
             ref=v["vault"], order=i)

    hub = refresh = None
    for t in tasks:
        times, words = schedule(t.get("cron"))
        last = t["last"] if isinstance(t.get("last"), dict) else {}
        rid = node(f"run:{t['id']}", 2, t.get("title") or t["id"], "task", status=run_status(t, now),
                   sub=words, ref=t["id"],
                   detail={"schedule": words, "times": times, "last": last.get("end") or "",
                           "last_status": last.get("status") or "", "summary": last.get("summary") or "",
                           "skill": t.get("skill") or ""})
        if t.get("skill") == "para-ingest" and hub is None:
            hub = rid
        if t.get("skill") == "para-command-center" and refresh is None:
            refresh = rid
        for source in t.get("sources") or []:
            if isinstance(source, dict) and source.get("name"):
                edge(node(f"src:{source['name']}", 0, source["name"], "source", group="watch"), rid, "watch")
                for name in t["vaults"] if isinstance(t.get("vaults"), list) else []:
                    if f"vault:{name}" in nodes:
                        edge(rid, f"vault:{name}", "watch")

    threads = Counter()
    for f in flows:
        threads[f["address"].lower()] += f["count"]
    fed = set()
    for entry in entries:
        if not isinstance(entry, dict) or f"vault:{entry.get('name')}" not in nodes:
            continue
        vid, machine = f"vault:{entry['name']}", entry.get("machine")
        root = Path(entry["path"]) if entry.get("path") else None
        if root is None or not root.is_dir():
            continue
        away = node(f"machine:{machine}", 2, str(machine), "process", sub="pulls its own vaults") if machine else None
        for row in triage_sources(root)["rows"]:
            if row["mailbox"] and row["kind"] in ("connector", "fetch-script"):
                address = row["mailbox"].lower()
                box = node(f"box:{address}", 0, labels.get(address, address), "mailbox", ref=address,
                           sub=f"{threads[address]} threads in {days} days")
                if away:
                    edge(box, away, "away")
                    edge(away, vid, "away")
                    continue
                kind = "script" if row["kind"] == "fetch-script" else "connector"
                cid, rec = connection(kind, row["path"] if kind == "script" else row["connector"])
                fed.add(cid)
                if f"{box}>{cid}" not in edges:
                    edge(box, cid, "mail", threads[address])
                    edge(cid, hub or vid, "mail", threads[address])
            elif row["kind"] in ("sync-script", "recording"):
                kind = "script" if row["kind"] == "sync-script" else "connector"
                name = row["path"] if kind == "script" else row["connector"]
                if not name:
                    continue
                label = provider_name((declared(kind, name) or {}).get("provider")) or row["source"] or script_name(name)
                src = node(f"src:{label}", 0, label, "source", group="recording")
                if away:
                    edge(src, away, "away")
                    edge(away, vid, "away")
                    continue
                cid, rec = connection(kind, name)
                fed.add(cid)
                written = synced.get((script_name(name), entry["name"]), 0)
                edge(src, cid, "sync", written)
                edge(cid, vid, "sync", written)
    if hub:
        for name, n in routed.items():
            if f"vault:{name}" in nodes:
                edge(hub, f"vault:{name}", "mail", n)

    for cal in calendars:
        kind, _, name = cal["type"].partition(":")
        if not name.strip():
            continue
        cid, _ = connection("connector", name.strip())
        fed.add(cid)
        edge(node(f"cal:{cal['endpoint'] or cal['source']}", 0, cal["source"] or cal["endpoint"], "calendar",
                  ref=cal["endpoint"], sub=cal["endpoint"]), cid, "calendar")
        if refresh:
            edge(cid, refresh, "calendar")

    tools = {connection_key(c["id"]): provider_name(c.get("provider")) or c["id"]
             for c in listed if c.get("kind") == "cli" and c.get("declared")}
    for rec in listed:
        uses = rec.get("used_by") or []
        if rec.get("machine") or f"conn:{rec['id']}" in fed or any(
                u["via"] in ("triage", "agenda") or u["via"].startswith("task:") for u in uses):
            continue
        calls = rec.get("calls") or {}
        through = [c for c in calls.get("clis") or [] if connection_key(c) in tools]
        found = rec.get("kind") == "script" and not rec.get("declared")
        if found:
            providers = list(dict.fromkeys(tools[connection_key(c)] for c in through)) or [UNLABELLED]
        else:
            providers = [provider_name(rec.get("provider")) or rec["id"]]
        cid = node(f"conn:{rec['id']}", 1, rec["id"], rec.get("kind") or "mcp",
                   sub=UNLISTED if found else ("read-only" if rec.get("read_only") else ""),
                   detail={"provider": "" if providers == [UNLABELLED] else ", ".join(providers),
                           "writes": rec.get("writes") or "",
                           "through": ", ".join(through),
                           "calls": ", ".join(calls.get("hosts") or []),
                           "run_by": ", ".join(sorted({u["via"][6:] for u in uses if u["via"].startswith("skill:")})),
                           "path": (rec.get("path") or "") if found else ""})
        for provider in providers:
            edge(node(f"src:{provider}", 0, provider, "source", group="system"), cid, "tool")
        for u in uses:
            if f"vault:{u['vault']}" in nodes:
                edge(cid, f"vault:{u['vault']}", "tool")

    for name in dict.fromkeys(r["vault"] for r in repos):
        mine = [r for r in repos if r["vault"] == name]
        flagged = sum(1 for r in mine if r["signal"] not in ("clean", "quiet"))
        gid = node(f"repos:{name}", 4, f"{name} repos ({len(mine)})", "repos",
                   status=SEVERITY_WORD[max(SEVERITY.get(r["signal"], 0) for r in mine)],
                   sub=f"{flagged} to look at" if flagged else "all clean", ref=name)
        edge(f"vault:{name}", gid, "owns")
    for s in sites:
        sid = node(f"site:{s['site']}", 5, s["site"], "site", sub=s["what"][:40], ref=s["site"])
        edge(f"repos:{s['vault']}", sid, "builds")
        if f"vault:{s['serves']}" in nodes:
            edge(f"vault:{s['serves']}", sid, "serves")

    by_key = {vault_key(e["path"]): e["name"] for e in entries
              if isinstance(e, dict) and e.get("path") and f"vault:{e.get('name')}" in nodes}
    for p in pages:
        if p.get("replaced_by"):
            continue
        pid = node(f"page:{p['key']}:{p['page']}", 5, p.get("title") or p["page"], "page",
                   detail={"url": p.get("url") or ""})
        maker = next((f"run:{t['id']}" for t in tasks if t.get("skill") and t["skill"] == p.get("producer")), None)
        if maker:
            edge(maker, pid, "publish")
        elif p["key"] in by_key:
            edge(f"vault:{by_key[p['key']]}", pid, "publish")
    return list(nodes.values()), list(edges.values()), hub


# ------------------------------------------------------------- the whole page

def build(entries, today, now, paraos_home=None, events=None, note="", days=DAYS, roots=(),
          run=run_command, online=True, model=None):
    """Everything the page shows, as one dict."""
    home = paraos_home_dir(paraos_home)
    notes = [note] if note else []
    scan = build_report(entries, today, paraos_home, model)
    listed, _, _ = connections_gather(paraos_home)
    if not listed["exists"]:
        notes.append("No connections registry: connections are named as the vaults write them.")
    labels = {b["address"].lower(): b["label"] for b in listed["mailboxes"]}
    feed = inbound(home, days, today, labels, entries)
    repos, sites = repo_rows(entries, paraos_home, roots, today, run, online)
    past = read_json(home / "past-vaults.json", [])
    vaults, health = vault_rows(scan, entries, feed, repos, today, past if isinstance(past, list) else [])
    agenda, dropped = agenda_rows(scan, events or [], today)
    if events is None:
        notes.append("No calendar events were given: the agenda holds only the vaults' own meetings.")
    if dropped:
        notes.append(f"{dropped} calendar event{'s' * (dropped > 1)} had no date or no title and {'were' if dropped > 1 else 'was'} left out.")
    tasks = runs_status(paraos_home=paraos_home)["tasks"]
    if not tasks:
        notes.append("No task registry: the scheduled runs are not shown.")
    notes += [f"{e['name'] or 'An entry'} was not read: {e['reason']}" for e in scan["excluded"]]
    nodes, edges, hub = catalog(entries, vaults, scan["calendars"], feed["flows"],
                                synced_counts(entries, feed["since"]),
                                feed["routed"], repos, sites,
                                listed["connections"], listed["mailboxes"], tasks,
                                load_index(paraos_home), days, now)
    return {"meta": {"today": iso(today), "generated_at": now.isoformat(timespec="seconds"),
                     "days": days, "hub": hub, "notes": notes},
            "tasks": task_rows(scan, today), "agenda": agenda, "vaults": vaults, "health": health,
            "funnel": feed["funnel"], "flows": feed["flows"], "repos": repos, "sites": sites,
            "nodes": nodes, "edges": edges}


def page(data):
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    template = TEMPLATE.read_text(encoding="utf-8")
    return template.replace("__PARAOS_TITLE__", html.escape(TITLE)).replace("__PARAOS_DATA__", blob)


def write_data(data, paraos_home=None):
    path = paraos_home_dir(paraos_home) / "cache" / PAGE / "data.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def read_events(path):
    """`(events, note)` from the file the skill wrote, `(None, why)` where it cannot be used."""
    data = read_json(path, None)
    if isinstance(data, list):
        return data, ""
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        return data["events"], plain(str(data.get("note") or ""))
    return None, f"The events file {path} could not be read: the agenda holds only the vaults' own meetings."


def events_file(paraos_home=None):
    return paraos_home_dir(paraos_home) / "cache" / PAGE / "events.json"


def calendar_events(given, now, paraos_home=None):
    """`(events, note)` for a build. A file the skill just wrote is used and kept as the last
    read; with none given, the last read is used again, so a rebuild between two calendar
    reads keeps the meetings, and the note says when they were read if that was another day."""
    kept = events_file(paraos_home)
    if given:
        events, note = read_events(given)
        if events is not None:
            kept.parent.mkdir(parents=True, exist_ok=True)
            kept.write_text(json.dumps({"events": events, "note": note, "read_at": now.isoformat(timespec="seconds")},
                                       ensure_ascii=False), encoding="utf-8")
        return events, note
    if not kept.is_file():
        return None, ""
    events, note = read_events(kept)
    read_at = parse_time(read_json(kept, {}).get("read_at")) if events is not None else None
    if read_at and read_at.astimezone(now.tzinfo).date() != now.date():
        note = (note + " " if note else "") + f"The calendars were last read on {read_at.astimezone(now.tzinfo).date().isoformat()}."
    return events, note


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the Command Center page from files on disk.")
    ap.add_argument("--events", help="the calendars' events, as the skill fetched them")
    ap.add_argument("--today", type=date_arg, help="date to bucket against (default: the system date)")
    ap.add_argument("--days", type=int, default=DAYS, help="the inbound window, in days")
    ap.add_argument("--code-root", action="append", help="a folder repos are checked out under (default: ~/Code)")
    ap.add_argument("--offline", action="store_true", help="no git fetch and no gh")
    ap.add_argument("--model", help="the running model's id, for each health card's skills review")
    ap.add_argument("--out", help="where to write the page when it publishes to claude.ai")
    ap.add_argument("--publish", choices=PUBLISH, help="record where the page goes, and stop")
    ap.add_argument("--calendars", action="store_true", help="print the calendars to read, and stop")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    args = ap.parse_args(argv)
    utf8_stdout()

    key = paraos_home_dir(args.paraos_home)
    if args.publish:
        path = store(key, PAGE, args.paraos_home, publish=args.publish)
        print(json.dumps({"publish": args.publish, "cache": path.as_posix()}))
        return 0
    today = args.today or date.today()
    entries = registry(args.paraos_home)
    if not entries:
        print("command_center: no registry, or one listing no vault", file=sys.stderr)
        return 3
    if args.calendars:
        print(json.dumps(calendars_only(entries, today, args.paraos_home), ensure_ascii=False))
        return 0
    publish = publish_choice(key, PAGE, args.paraos_home)
    if publish == "local":
        out = local_page(key, PAGE, args.paraos_home)
    elif args.out:
        out = Path(args.out).resolve()
    else:
        ap.error("this page publishes to claude.ai: name it with --out")
    now = datetime.now().astimezone()
    events, note = calendar_events(args.events, now, args.paraos_home)
    data = build(entries, today, now, args.paraos_home, events, note,
                 args.days, args.code_root or [str(Path.home() / "Code")], online=not args.offline,
                 model=args.model)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page(data), encoding="utf-8")
    write_data(data, args.paraos_home)
    print(json.dumps({"out": out.as_posix(), "page": PAGE, "publish": publish, "title": TITLE,
                      "description": DESCRIPTION, "key": key.as_posix(),
                      "url": remembered_url(key, PAGE, args.paraos_home)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
