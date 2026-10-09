#!/usr/bin/env python3
"""The counting half of /para-activity-review, as a script instead of instructions.

    py -3 scripts/review_scan.py --vault <path> [--days 30] [--today YYYY-MM-DD]
    python3 scripts/review_scan.py --vault <path>

Reads every resources/logs/sessions/*.jsonl whose file date falls in the window and prints
one JSON document: the frame (sessions, people, days), adoption per skill, reach per PARA
bucket, and the friction counts. It never writes to the vault. What each number may mean,
and the contradictions against the vault's own rules, stay with the skill:
references/signals.md says what each count may mean.

Exit 3: the vault has no ledger folder. The skill says so and stops.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

LEDGER = Path("resources") / "logs" / "sessions"
PATH_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PROMPT_EVENTS = {"UserPromptSubmit", "UserPromptExpansion"}
FAILURE_EVENTS = ("PostToolUseFailure", "PermissionDenied")


def file_day(path):
    """The date a ledger file's name starts with (YYYYMMDD-<person>-<session>.jsonl)."""
    stem = path.name.split("-", 1)[0]
    try:
        return date(int(stem[:4]), int(stem[4:6]), int(stem[6:8]))
    except ValueError:
        return None


def person_of(path):
    parts = path.stem.split("-")
    return "-".join(parts[1:-1]) if len(parts) >= 3 else "unknown"


def skill_from_prompt(prompt):
    """`/para-new acme` names para-new; a prompt not opening on a slash names nothing."""
    first = (prompt or "").strip().split(" ", 1)[0]
    return bare(first[1:]) if first.startswith("/") and len(first) > 1 else None


def bare(name):
    """A plugin-qualified skill (`para-os:para-new`) counts under its own name."""
    return name.rsplit(":", 1)[-1]


def bucket_of(target):
    if not target or "/" not in target.replace("\\", "/"):
        return None
    return target.replace("\\", "/").lstrip("./").split("/", 1)[0]


def read_events(path):
    events, skipped = [], 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            skipped += 1
    return events, skipped


def declared_skills(vault):
    folder = vault / ".claude" / "skills"
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.iterdir() if p.is_dir() and p.name != "para-shared")


def scan(vault, today, days):
    vault = Path(vault)
    start = today - timedelta(days=days - 1)
    files = sorted(p for p in (vault / LEDGER).glob("*.jsonl")
                   if file_day(p) and start <= file_day(p) <= today)

    skipped = 0
    sessions = []
    invocations = {}                       # (session, prompt_id, skill) -> (person, day)
    bucket_sessions = defaultdict(set)
    writers = defaultdict(set)
    failures = Counter()
    per_request = []

    for path in files:
        events, bad = read_events(path)
        skipped += bad
        person, day = person_of(path), file_day(path).isoformat()
        sid = next((e.get("session") for e in events if e.get("session")), path.stem)
        prompts, prompt_text, tools, wrote = set(), {}, Counter(), False

        for e in events:
            kind, pid = e.get("event"), e.get("prompt_id")
            if kind in PROMPT_EVENTS and pid:
                prompts.add(pid)
                prompt_text.setdefault(pid, e.get("prompt", ""))
                skill = skill_from_prompt(e.get("prompt"))
                if skill:
                    invocations.setdefault((sid, pid, skill), (person, day))
            tool, target = e.get("tool"), e.get("target")
            if kind == "PostToolUse" and tool == "Skill" and target:
                invocations.setdefault((sid, pid, bare(target)), (person, day))
            if kind in ("PostToolUse",) + FAILURE_EVENTS and tool:
                tools[pid] += 1
            if kind in FAILURE_EVENTS:
                failures[(kind, tool or "", target or "")] += 1
                continue
            if kind != "PostToolUse":
                continue
            paths = [target] if tool in PATH_TOOLS else []
            paths += e.get("touched") or []
            for p in paths:
                b = bucket_of(p)
                if b:
                    bucket_sessions[b].add(sid)
            written = ([target] if tool in WRITE_TOOLS and target else []) + (e.get("touched") or [])
            for p in written:
                writers[p.replace("\\", "/")].add(person)
                wrote = True

        for pid, count in tools.items():
            if pid in prompt_text:
                per_request.append({"session": sid, "person": person,
                                    "prompt": prompt_text[pid], "tools": count})
        sessions.append({"session": sid, "person": person, "day": day,
                         "prompts": len(prompts), "wrote": wrote})

    adoption = {}
    for (_, _, skill), (person, day) in sorted(invocations.items(), key=lambda kv: kv[1][1]):
        entry = adoption.setdefault(skill, {"invocations": 0, "by_person": {},
                                            "first": day, "last": day})
        entry["invocations"] += 1
        entry["by_person"][person] = entry["by_person"].get(person, 0) + 1
        entry["last"] = day
    for entry in adoption.values():
        entry["by_person"] = dict(sorted(entry["by_person"].items()))

    declared = declared_skills(vault)
    buckets = sorted(p.name for p in vault.iterdir()
                     if p.is_dir() and not p.name.startswith("."))
    typed = [s for s in sessions if s["prompts"]]
    dates = sorted(s["day"] for s in sessions)
    rhythm = defaultdict(lambda: {"sessions": 0, "typed_sessions": 0})
    for s in sessions:
        r = rhythm[s["person"]]
        r["sessions"] += 1
        r["typed_sessions"] += bool(s["prompts"])
        r.setdefault("first", s["day"])
        r["last"] = max(r.get("last", s["day"]), s["day"])
        r["first"] = min(r["first"], s["day"])

    return {
        "vault": str(vault),
        "today": today.isoformat(),
        "window_days": days,
        "frame": {
            "files": len(files),
            "sessions": len(sessions),
            "typed_sessions": len(typed),
            "people": sorted({s["person"] for s in sessions}),
            "first": dates[0] if dates else None,
            "last": dates[-1] if dates else None,
            "days": ((date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1
                     if dates else 0),
            "skipped_lines": skipped,
        },
        "declared_skills": declared,
        "adoption": dict(sorted(adoption.items())),
        "never_invoked": [s for s in declared if s not in adoption],
        "reach": {
            "sessions_by_bucket": {b: len(s) for b, s in sorted(bucket_sessions.items())},
            "untouched_buckets": [b for b in buckets
                                  if b not in bucket_sessions and b != "resources"],
            "writers_by_file": {f: sorted(p) for f, p in sorted(writers.items())},
        },
        "friction": {
            "failures": [{"event": k, "tool": t, "target": g, "count": n}
                         for (k, t, g), n in sorted(failures.items(),
                                                    key=lambda kv: (-kv[1], kv[0]))],
            "tools_per_request": sorted(per_request, key=lambda r: -r["tools"])[:10],
            "typed_without_writes": sum(1 for s in typed if not s["wrote"]),
        },
        "rhythm": {p: rhythm[p] for p in sorted(rhythm)},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Count a vault's activity ledger.")
    ap.add_argument("--vault", default=".")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--today", help="YYYY-MM-DD; the system clock when left off")
    ap.add_argument("--indent", type=int, default=1)
    args = ap.parse_args(argv)
    vault = Path(args.vault).resolve()
    today = date.fromisoformat(args.today) if args.today else date.today()
    if not (vault / LEDGER).is_dir():
        json.dump({"error": "no ledger", "looked_in": str(vault / LEDGER)}, sys.stdout)
        return 3
    json.dump(scan(vault, today, args.days), sys.stdout, ensure_ascii=False, indent=args.indent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
