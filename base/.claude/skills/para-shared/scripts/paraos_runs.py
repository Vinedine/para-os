#!/usr/bin/env python3
"""Scheduled runs: what each one is, and how its runs went.

    py -3 paraos_runs.py record --task <id> --status ok|failed|partial --summary "<one line>" [--started <ISO time>]
    py -3 paraos_runs.py status [--task <id>]
    py -3 paraos_runs.py check [--app-tasks <file>] [--tasks-dir <folder>]

The task registry, `$PARAOS_HOME/tasks.json`, is a JSON list with one entry per scheduled
task: `id` (its folder's name under the tasks folder), `title`, `cron` (the schedule as the app
runs it), `skill` (the skill it invokes, null for a prompt of its own), `vaults` (the vault
registry names it reads or writes, or `"*"` for every one), and `sources`, each outside source
it reads that no vault's `## Triage sources` or `## Agenda sources` declares, as
`{"name": <source>, "via": [<connection>, ...]}`. A connection is `mcp:<server>`, `browser`,
`script:<path>` or `cli:<tool>`. A missing registry is an empty one.

`record` appends one JSON line to `$PARAOS_HOME/cache/runs/<id>.jsonl`, `task`, `start`
(`--started`, else null), `end` (now, UTC), `status` and `summary` (on one line, cut at
`SUMMARY_MAX` characters), prints it, and drops the file's lines that ended more than
`KEEP_DAYS` days ago. A line that does not parse is kept. A task the registry does not list is
recorded all the same.

`status` prints `tasks`, every registry entry (or the one `--task` names) with `last`, its
newest run line or null, and `runs`, its kept lines counted by status; and `unregistered_runs`,
the run files no entry names.

`check` compares the registry with the task folders on disk (each holding a `SKILL.md`, under
`--tasks-dir`, default `$CLAUDE_CONFIG_DIR/scheduled-tasks` or `~/.claude/scheduled-tasks`)
and, given `--app-tasks`, with the app's own list: a JSON list, or `{"tasks": [...]}`, of objects
holding `taskId` and `cronExpression`, the scheduled-tasks tool's fields (`id` and `cron` also
read). It prints `registry` (the path), `exists`,
`app_compared` and `findings`, each with `task`, `kind`, `detail` and `fix`:

    invalid           an entry with no string `id`, a repeated id, `vaults` that is neither
                      a list nor "*", a vault the vault registry does not list, a source with
                      no `name`, or a connection of no known kind; or a registry that does not
                      parse (`task` null)
    unregistered      a task the app runs, or with no app list a task folder, that no entry names
    not_scheduled     an entry the app's list does not hold
    no_folder         with no app list, an entry with no task folder
    schedule_differs  an entry whose `cron` is not the app's
    stale_folder      a task folder that neither the app's list nor the registry holds

Exit codes: 0 answered; 2 an argument is wrong, or `--app-tasks` cannot be read.
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paraos_vault import paraos_home_dir, registry  # noqa: E402

STATUSES = ("ok", "failed", "partial")
CONNECTION_KINDS = ("mcp:", "script:", "cli:")
KEEP_DAYS = 90
SUMMARY_MAX = 500


# ------------------------------------------------------------------ the registry

def tasks_file(paraos_home=None):
    return paraos_home_dir(paraos_home) / "tasks.json"


def load_tasks(paraos_home=None):
    """`(entries, error)`: the registry's list as written, `[]` where the file is missing, and
    the reason it cannot be used where it does not parse or is not a list."""
    path = tasks_file(paraos_home)
    if not path.is_file():
        return [], None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        return [], f"{path} does not parse: {err}"
    if not isinstance(data, list):
        return [], f"{path} is not a JSON list"
    return data, None


def task_ids(entries):
    return [e["id"] for e in entries if isinstance(e, dict) and isinstance(e.get("id"), str)]


def known_connection(via):
    return isinstance(via, str) and (via == "browser" or any(
        via.startswith(kind) and len(via) > len(kind) for kind in CONNECTION_KINDS))


def entry_problems(entry, vault_names):
    """Why one registry entry cannot be read as declared, one string per problem."""
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
        return ["has no string `id`"]
    out = []
    vaults = entry.get("vaults", [])
    if vaults != "*":
        if not isinstance(vaults, list):
            out.append("`vaults` is neither a list nor \"*\"")
        else:
            out += [f"names vault {v!r}, which the vault registry does not list"
                    for v in vaults if v not in vault_names]
    sources = entry.get("sources", [])
    for source in sources if isinstance(sources, list) else [None]:
        if not isinstance(source, dict) or not source.get("name"):
            out.append("has a source with no `name`")
            continue
        via = source.get("via", [])
        out += [f"reaches {source['name']!r} through {v!r}, no known connection"
                for v in (via if isinstance(via, list) else [via]) if not known_connection(v)]
    return out


# ------------------------------------------------------------------ run records

def runs_dir(paraos_home=None):
    return paraos_home_dir(paraos_home) / "cache" / "runs"


def now_utc():
    return datetime.now(timezone.utc)


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(text):
    try:
        moment = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def read_runs(path):
    """Every line of one run file: a dict where it parses, else the raw text."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in filter(str.strip, lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            out.append(line)
    return out


def expired(run, cutoff):
    end = parse_time(run.get("end")) if isinstance(run, dict) else None
    return end is not None and end < cutoff


def record(task, status, summary, started=None, paraos_home=None, now=None):
    """Append one run line for `task`, prune the file to `KEEP_DAYS`, and return the line."""
    now = now or now_utc()
    one_line = " ".join(str(summary).split())
    if len(one_line) > SUMMARY_MAX:
        one_line = one_line[:SUMMARY_MAX - 3] + "..."
    line = {"task": task, "start": started, "end": iso(now), "status": status,
            "summary": one_line}
    folder = runs_dir(paraos_home)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{task}.jsonl"
    cutoff = now - timedelta(days=KEEP_DAYS)
    kept = [r for r in read_runs(path) if not expired(r, cutoff)] + [line]
    text = "".join((json.dumps(r, ensure_ascii=False) if isinstance(r, dict) else r) + "\n"
                   for r in kept)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=f".{task}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)
    return line


def status(task=None, paraos_home=None):
    entries, error = load_tasks(paraos_home)
    folder = runs_dir(paraos_home)
    rows = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        if task and entry["id"] != task:
            continue
        runs = [r for r in read_runs(folder / f"{entry['id']}.jsonl") if isinstance(r, dict)]
        counts = {s: sum(1 for r in runs if r.get("status") == s) for s in STATUSES}
        rows.append(dict(entry, last=runs[-1] if runs else None, runs=counts))
    named = set(task_ids(entries))
    stray = sorted(p.stem for p in folder.glob("*.jsonl") if p.stem not in named) \
        if folder.is_dir() else []
    return {"registry": str(tasks_file(paraos_home)), "error": error, "tasks": rows,
            "unregistered_runs": stray}


# ------------------------------------------------------------------ drift

def default_tasks_dir():
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(config or (Path.home() / ".claude")) / "scheduled-tasks"


def task_folders(tasks_dir):
    folder = Path(tasks_dir)
    if not folder.is_dir():
        return set()
    return {p.name for p in folder.iterdir() if (p / "SKILL.md").is_file()}


def app_list(path):
    """The app's task list from a file: `{id: cron}`. Raises ValueError where it is no list."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("tasks")
    if not isinstance(data, list):
        raise ValueError("not a list of tasks, nor {\"tasks\": [...]}")
    out = {}
    for item in data:
        tid = item.get("taskId") or item.get("id") if isinstance(item, dict) else None
        if isinstance(tid, str):
            out[tid] = item.get("cronExpression", item.get("cron"))
    return out


def finding(task, kind, detail, fix):
    return {"task": task, "kind": kind, "detail": detail, "fix": fix}


def check(paraos_home=None, app=None, tasks_dir=None):
    """The registry against the task folders and, where `app` (`{id: cron}`) is given, the
    app's own list."""
    entries, error = load_tasks(paraos_home)
    path = tasks_file(paraos_home)
    folders = task_folders(tasks_dir or default_tasks_dir())
    vault_names = {v.get("name") for v in registry(paraos_home) if isinstance(v, dict)}
    out = []
    if error:
        out.append(finding(None, "invalid", error, "fix the file so it parses as a JSON list"))
    seen = set()
    for number, entry in enumerate(entries, start=1):
        problems = entry_problems(entry, vault_names)
        tid = entry.get("id") if isinstance(entry, dict) else None
        if isinstance(tid, str) and tid in seen:
            problems.append("repeats an id an earlier entry holds")
        seen.add(tid)
        for problem in problems:
            out.append(finding(tid if isinstance(tid, str) else None, "invalid",
                               f"entry {number} {problem}", f"correct entry {number} in {path}"))
    registered = {e["id"]: e for e in entries
                  if isinstance(e, dict) and isinstance(e.get("id"), str)}
    running = set(app) if app is not None else folders
    for tid in sorted(running - set(registered)):
        out.append(finding(tid, "unregistered",
                           f"{tid} is scheduled but {path.name} does not list it",
                           f"add an entry for {tid} to {path}"))
    for tid, entry in registered.items():
        if app is None:
            if tid not in folders:
                out.append(finding(tid, "no_folder", f"{tid} has no task folder",
                                   f"recreate the task, or delete its entry from {path}"))
        elif tid not in app:
            out.append(finding(tid, "not_scheduled", f"the app does not run {tid}",
                               f"recreate the task, or delete its entry from {path}"))
        elif (app[tid] or None) != (entry.get("cron") or None):
            out.append(finding(tid, "schedule_differs",
                               f"{tid} runs on {app[tid]!r}, {path.name} says "
                               f"{entry.get('cron')!r}",
                               f"copy the app's schedule into {path}"))
    if app is not None:
        for tid in sorted(folders - set(app) - set(registered)):
            out.append(finding(tid, "stale_folder",
                               f"the task folder {tid} is neither run nor registered",
                               "recreate the task, or remove its folder after reading it"))
    return {"registry": str(path), "exists": path.is_file(), "app_compared": app is not None,
            "findings": out}


# ------------------------------------------------------------------ command line

def main(argv=None):
    ap = argparse.ArgumentParser(description="Scheduled runs: the registry and run records.")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--task", required=True)
    rec.add_argument("--status", required=True, choices=STATUSES)
    rec.add_argument("--summary", required=True)
    rec.add_argument("--started")
    st = sub.add_parser("status")
    st.add_argument("--task")
    ck = sub.add_parser("check")
    ck.add_argument("--app-tasks")
    ck.add_argument("--tasks-dir")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if args.cmd == "record":
        if "/" in args.task or "\\" in args.task or args.task.startswith("."):
            print("paraos_runs: --task is a task's folder name, not a path", file=sys.stderr)
            return 2
        if args.started and parse_time(args.started) is None:
            print(f"paraos_runs: --started {args.started!r} is not an ISO time", file=sys.stderr)
            return 2
        result = record(args.task, args.status, args.summary, args.started, args.paraos_home)
    elif args.cmd == "status":
        result = status(args.task, args.paraos_home)
    else:
        app = None
        if args.app_tasks:
            try:
                app = app_list(args.app_tasks)
            except (OSError, ValueError) as err:
                print(f"paraos_runs: --app-tasks {args.app_tasks}: {err}", file=sys.stderr)
                return 2
        result = check(args.paraos_home, app, args.tasks_dir)
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
