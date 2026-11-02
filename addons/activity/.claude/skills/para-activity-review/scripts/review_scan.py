#!/usr/bin/env python3
"""The counting half of /para-activity-review, as a script instead of instructions.

    py -3 scripts/review_scan.py --vault <path> [--days 30] [--today YYYY-MM-DD]
    python3 scripts/review_scan.py --vault <path>

Reads every resources/logs/sessions/*.jsonl whose file date falls in the window and prints
one JSON document: the frame (sessions, people, days), adoption per skill, reach per PARA
bucket, the friction counts, each person's rhythm, and the contradictions a file listing can
settle. A session is one id, however many daily files it wrote. A skill is declared by its
folder in .claude/skills/ or by a `/skill-name` the vault's CLAUDE.md names. It never writes
to the vault. What each number may mean stays with the skill: references/signals.md.

Exit 3: the vault has no ledger folder. The skill says so and stops.
"""

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

LEDGER = Path("resources") / "logs" / "sessions"
PATH_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PROMPT_EVENTS = {"UserPromptSubmit", "UserPromptExpansion"}
FAILURE_EVENTS = ("PostToolUseFailure", "PermissionDenied")
# A hyphenated name after a slash that no word, path or URL runs into: `/para-new`, never
# the `/para-os` of a URL or the `/side-work/` of a path.
SKILL_NAME_RE = re.compile(r"(?<![\w/.~-])/([a-z][a-z0-9]*(?:-[a-z0-9]+)+)(?![\w/-])")
WORD_RE = re.compile(r"\w+")
REPHRASE_OVERLAP = 0.6     # words two consecutive prompts share, over all their words
REPHRASE_MIN_WORDS = 3


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


def entity_of(target):
    """`projects/acme/brief.md` is in projects/acme; a Glob pattern names no entity."""
    parts = (target or "").replace("\\", "/").lstrip("./").split("/")
    if len(parts) > 2 and parts[0] in ("projects", "areas") and not set("*?[") & set(parts[1]):
        return "/".join(parts[:2])
    return None


def in_vault(target):
    """The ledger records a vault file relative to the vault, and any other path as given."""
    return bool(target) and target[:1] not in "/\\~" and target[1:2] != ":"


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
    folder, claude_md = vault / ".claude" / "skills", vault / "CLAUDE.md"
    installed = {p.name for p in folder.iterdir() if p.is_dir()} if folder.is_dir() else set()
    named = set(SKILL_NAME_RE.findall(claude_md.read_text(encoding="utf-8", errors="replace"))
                ) if claude_md.is_file() else set()
    return sorted((installed | named) - {"para-shared"})


def worded(prompt):
    """A request in words: not a slash command, which adoption counts, nor a message the
    harness injects as a tag, such as `<agent-message>`."""
    text = (prompt or "").lstrip()
    return bool(text) and text[0] not in "/<"


def near_repeat(a, b):
    a, b = set(WORD_RE.findall(a.lower())), set(WORD_RE.findall(b.lower()))
    if min(len(a), len(b)) < REPHRASE_MIN_WORDS:
        return False
    return len(a & b) / len(a | b) >= REPHRASE_OVERLAP


def minutes(start, end):
    try:
        return int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
                   // 60)
    except (TypeError, ValueError):
        return None


def monday(day):
    return day - timedelta(days=day.weekday())


def scan(vault, today, days):
    vault = Path(vault)
    start = today - timedelta(days=days - 1)
    dated = [p for p in (vault / LEDGER).glob("*.jsonl") if file_day(p)]
    files = sorted(p for p in dated if start <= file_day(p) <= today)
    first_ever = {}
    for p in dated:
        first_ever[person_of(p)] = min(first_ever.get(person_of(p), file_day(p)), file_day(p))

    skipped = 0
    sessions = {}                          # session id -> what all its files hold
    invocations = {}                       # (session, prompt_id, skill) -> (person, day)
    bucket_sessions = defaultdict(set)
    writers = defaultdict(set)
    readers = defaultdict(set)
    failures = Counter()
    reasons = Counter()
    silent_endings = 0

    for path in files:
        events, bad = read_events(path)
        skipped += bad
        person, day = person_of(path), file_day(path).isoformat()
        sid = next((e.get("session") for e in events if e.get("session")), path.stem)
        s = sessions.setdefault(sid, {"person": person, "days": set(), "prompts": {},
                                      "tools": Counter(), "wrote": False, "entities": set(),
                                      "vault_work": False, "at": []})
        s["days"].add(day)

        for e in events:
            kind, pid = e.get("event"), e.get("prompt_id")
            if isinstance(e.get("at"), str):
                s["at"].append(e["at"])
            if kind in PROMPT_EVENTS and pid:
                s["prompts"].setdefault(pid, e.get("prompt", ""))
                skill = skill_from_prompt(e.get("prompt"))
                if skill:
                    invocations.setdefault((sid, pid, skill), (person, day))
            if kind == "SessionEnd":
                reasons[e.get("reason") or "none"] += 1
                summary = e.get("summary") if isinstance(e.get("summary"), dict) else {}
                silent_endings += bool(summary.get("prompts")) and summary.get(
                    "last_prompt_tools") == 0
            tool, target = e.get("tool"), e.get("target")
            if kind == "PostToolUse" and tool == "Skill" and target:
                invocations.setdefault((sid, pid, bare(target)), (person, day))
            if kind in ("PostToolUse",) + FAILURE_EVENTS and tool:
                s["tools"][pid] += 1
            if kind in FAILURE_EVENTS:
                failures[(kind, tool or "", target or "")] += 1
                continue
            if kind != "PostToolUse":
                continue
            if tool == "Read" and in_vault(target):
                readers[target.replace("\\", "/")].add(sid)
            paths = [target] if tool in PATH_TOOLS else []
            paths += e.get("touched") or []
            s["vault_work"] = s["vault_work"] or any(map(in_vault, paths))
            for p in paths:
                b, entity = bucket_of(p), entity_of(p)
                if b:
                    bucket_sessions[b].add(sid)
                if entity:
                    s["entities"].add(entity)
            written = ([target] if tool in WRITE_TOOLS and target else []) + (e.get("touched") or [])
            for p in written:
                writers[p.replace("\\", "/")].add(person)
                s["wrote"] = True

    invoked = {key[0] for key in invocations}
    for sid, s in sessions.items():
        s["vault_work"] = s["vault_work"] or sid in invoked
    per_request = [{"session": sid, "person": s["person"], "prompt": s["prompts"][pid],
                    "tools": count}
                   for sid, s in sessions.items() for pid, count in s["tools"].items()
                   if pid in s["prompts"] and s["vault_work"]]
    asked = {sid: [p for p in s["prompts"].values() if worded(p)] for sid, s in sessions.items()}
    rephrased = [{"session": sid, "prompts": [a, b]}
                 for sid, s in sessions.items() if s["vault_work"]
                 for a, b in zip(asked[sid], asked[sid][1:]) if near_repeat(a, b)]

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
    typed = [s for s in sessions.values() if s["prompts"]]
    dates = sorted(d for s in sessions.values() for d in s["days"])
    rhythm = defaultdict(lambda: {"sessions": 0, "typed_sessions": 0})
    for s in sessions.values():
        s["first"], s["last"] = min(s["days"]), max(s["days"])
        s["span"] = (date.fromisoformat(s["last"]) - date.fromisoformat(s["first"])).days + 1
        r = rhythm[s["person"]]
        r["sessions"] += 1
        r["typed_sessions"] += bool(s["prompts"])
        r["first"] = min(r.get("first", s["first"]), s["first"])
        r["last"] = max(r.get("last", s["last"]), s["last"])
    weeks = [monday(start) + timedelta(weeks=n)
             for n in range((monday(today) - monday(start)).days // 7 + 1)]
    for person, r in rhythm.items():
        mine = [s for s in sessions.values() if s["person"] == person]
        r["weeks"] = {w.isoformat(): sum(monday(date.fromisoformat(s["first"])) == w
                                         for s in mine) for w in weeks}
        lengths = [m for m in (minutes(min(s["at"]), max(s["at"]))
                               for s in mine if s["prompts"] and s["at"]) if m is not None]
        r["median_minutes"] = round(statistics.median(lengths)) if lengths else None
        r["first_ever"] = first_ever[person].isoformat()
    triage = vault / "triage"
    waiting = [p for p in triage.rglob("*") if p.is_file() and not p.name.startswith(".")
               ] if triage.is_dir() else []

    return {
        "vault": str(vault),
        "today": today.isoformat(),
        "window_days": days,
        "frame": {
            "files": len(files),
            "sessions": len(sessions),
            "typed_sessions": len(typed),
            "unrelated_sessions": sum(1 for s in typed if not s["vault_work"]),
            "people": sorted({s["person"] for s in sessions.values()}),
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
            "read_never_written": {f: len(s) for f, s in sorted(readers.items())
                                   if len(s) > 1 and f not in writers},
        },
        "friction": {
            "failures": [{"event": k, "tool": t, "target": g, "count": n}
                         for (k, t, g), n in sorted(failures.items(),
                                                    key=lambda kv: (-kv[1], kv[0]))],
            "tools_per_request": sorted(per_request, key=lambda r: -r["tools"])[:10],
            "typed_without_writes": sum(1 for s in typed if not s["wrote"]),
            "multi_day_sessions": [
                {"session": sid, "span_days": s["span"], "entities": len(s["entities"])}
                for sid, s in sorted(sessions.items(), key=lambda kv: -kv[1]["span"])
                if s["span"] > 1],
            "rephrased": rephrased,
            "endings": {"reasons": dict(sorted(reasons.items())),
                        "last_request_without_tools": silent_endings},
        },
        "rhythm": {p: rhythm[p] for p in sorted(rhythm)},
        "contradictions": {"triage_unrun": 0 if "para-triage" in adoption else len(waiting)},
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
