#!/usr/bin/env python3
"""Scheduled runs: what each one is, and how its last run went.

    py -3 paraos_runs.py status [--task <id>] [--app-tasks <file>]
    py -3 paraos_runs.py check [--app-tasks <file>] [--tasks-dir <folder>]

The task registry, `$PARAOS_HOME/tasks.json`, is a JSON list with one entry per scheduled
task: `id` (its folder's name under the tasks folder), `title`, `cron` (the schedule as the app
runs it), `skill` (the skill it invokes, null for a prompt of its own), `vaults` (the vault
registry names it reads or writes, or `"*"` for every one), and `sources`, each outside source
it reads that no vault's `## Triage sources` or `## Agenda sources` declares, as
`{"name": <source>, "via": [<connection>, ...]}`. A connection is `mcp:<server>`, `browser`,
`script:<path>` or `cli:<tool>`. A missing registry is an empty one.

How a run went is the app's to say, never a log of our own. `--app-tasks` names the app's task
list saved as JSON: a list, or `{"tasks": [...]}`, of the scheduled-tasks tool's objects, each
holding `taskId`, `cronExpression`, `enabled` and, where the caller added it, `runs`, what
`list_task_runs` answered for it, newest first (`id` and `cron` also read).

`status` prints `tasks`, every registry entry (or the one `--task` names) with `enabled` and
`last`, its newest run in the app's list: `start`, `end` (its last activity), `summary` (its
error, else its summary, on one line) and `status`, `ok`, `failed` or `running` for the app's
`succeeded`, `failed` and `running`, and `partial` for any other word the app uses. Both are
null where the app's list was not given or does not hold the task.

`check` compares the registry with the task folders on disk (each holding a `SKILL.md`, under
`--tasks-dir`, default `$CLAUDE_CONFIG_DIR/scheduled-tasks` or `~/.claude/scheduled-tasks`)
and, given `--app-tasks`, with the app's own list. It prints `registry` (the path), `exists`,
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
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paraos_vault import emit, paraos_home_dir, registry, utf8_stdout  # noqa: E402

CONNECTION_KINDS = ("mcp:", "script:", "cli:")
APP_STATUS = {"succeeded": "ok", "failed": "failed", "running": "running"}


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


# ------------------------------------------------------------------ the app's runs

def parse_time(text):
    try:
        moment = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def app_tasks(path):
    """The app's task list from a file: every object naming its task. Raises ValueError where
    the file holds no list."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("tasks")
    if not isinstance(data, list):
        raise ValueError('not a list of tasks, nor {"tasks": [...]}')
    return [t for t in data if isinstance(t, dict) and isinstance(t.get("taskId") or t.get("id"), str)]


def app_list(path):
    """The app's task list from a file: `{id: cron}`."""
    return {t.get("taskId") or t.get("id"): t.get("cronExpression", t.get("cron"))
            for t in app_tasks(path)}


def last_run(task):
    """A task's newest run in the app's list, as `status` prints it, or None."""
    runs = task.get("runs")
    run = runs[0] if isinstance(runs, list) and runs and isinstance(runs[0], dict) else None
    if run is None:
        return None
    return {"start": run.get("started_at"), "end": run.get("last_activity_at") or run.get("started_at"),
            "status": APP_STATUS.get(run.get("status"), "partial"),
            "summary": " ".join(str(run.get("error") or run.get("summary") or "").split())}


def app_runs(tasks):
    """`{id: {"enabled", "last"}}` for each task of the app's list."""
    return {t.get("taskId") or t.get("id"): {"enabled": t.get("enabled"), "last": last_run(t)}
            for t in tasks}


def status(task=None, paraos_home=None, app=None):
    """Every registry entry, or the one `task` names, with how the app (`app_runs`) last ran it."""
    entries, error = load_tasks(paraos_home)
    rows = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        if task and entry["id"] != task:
            continue
        seen = (app or {}).get(entry["id"]) or {}
        rows.append(dict(entry, enabled=seen.get("enabled"), last=seen.get("last")))
    return {"registry": str(tasks_file(paraos_home)), "error": error,
            "app_compared": app is not None, "tasks": rows}


# ------------------------------------------------------------------ drift

def default_tasks_dir():
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(config or (Path.home() / ".claude")) / "scheduled-tasks"


def task_folders(tasks_dir):
    folder = Path(tasks_dir)
    if not folder.is_dir():
        return set()
    return {p.name for p in folder.iterdir() if (p / "SKILL.md").is_file()}


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
    ap = argparse.ArgumentParser(description="Scheduled runs: the registry and the app's runs.")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status")
    st.add_argument("--task")
    st.add_argument("--app-tasks")
    ck = sub.add_parser("check")
    ck.add_argument("--app-tasks")
    ck.add_argument("--tasks-dir")
    args = ap.parse_args(argv)
    utf8_stdout()

    app = None
    if args.app_tasks:
        try:
            app = app_runs(app_tasks(args.app_tasks)) if args.cmd == "status" else app_list(args.app_tasks)
        except (OSError, ValueError) as err:
            print(f"paraos_runs: --app-tasks {args.app_tasks}: {err}", file=sys.stderr)
            return 2
    if args.cmd == "status":
        result = status(args.task, args.paraos_home, app)
    else:
        result = check(args.paraos_home, app, args.tasks_dir)
    emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
