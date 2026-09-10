#!/usr/bin/env python3
"""Append-only record of how a vault actually gets used.

para-os-integration: activity 2026.09.02

A Claude Code hook. Reads one event as JSON on stdin, writes one JSONL line into
`<vault>/resources/logs/sessions/`, exits 0 no matter what. `/para-activity-review`
reads the result; nothing else does.

Three properties are load-bearing and none of them is an optimization:

  Fail open      Every exception is swallowed and the exit code is always 0. A hook
                 runs inside someone else's session, so a ledger that can fail is a
                 ledger that can stop a person working. Losing a line is nothing;
                 breaking a session is the whole product.

  One file per   Several people sync one folder. A single shared append target
  session        across several sync clients does not produce a log, it produces
                 conflict copies. The session id owns the filename.

  Record the     Prompts, tool names and skill names say what someone tried.
  ask, not the   `tool_response` carries file contents and is never written; a Bash
  contents       command keeps its first token and loses the rest, because a command
                 line is exactly where a password gets typed by accident.

Keeping only a command's first token leaves one gap: a script run through Bash writes
files this hook never learns about, so a run that wrote sixty files is recorded as `py`.
`touched_paths` closes it by asking the filesystem what moved while the tool was running,
which stays inside the privacy rule above - a path, never content, and only inside the
vault.

That answer is **inferred, not observed**. The window is the tool's own duration, so on a
synced library a file another person's sync client landed during that window is
indistinguishable from one this call wrote, and a long-running command widens the window.
The field is named `touched` rather than `wrote` for exactly that reason: treat it as
evidence of what changed, not proof of who changed it.

Install and configuration: see README.md in this folder.
"""

import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

DEFAULTS = {
    "record_prompts": True,
    "prompt_max_chars": 500,
    "record_touched": True,
    "touched_max_files": 40,
    "touched_slack_ms": 2000,
    "record_summary": True,
}

# Tools whose input names a file the vault owns. Everything else records its name only:
# an MCP call's arguments can hold anything, and guessing which keys are safe is how a
# ledger quietly starts collecting mail bodies.
PATH_KEYS = ("file_path", "notebook_path", "path")
PATTERN_TOOLS = ("Grep", "Glob")

# Tools whose input names a CAPABILITY rather than content. A skill name is metadata of
# exactly the kind `tool` already is, and it is the one signal /para-activity-review is built
# on: "Skill" alone says a skill ran, never which, so the capabilities nobody reached for
# could not be found. The value is a name in both cases, never a prompt or an argument.
NAME_KEYS = {"Skill": "skill", "Task": "subagent_type", "Agent": "subagent_type"}

# Tools that already name the file they wrote. Scanning these would record the same path
# twice and make one edit look like two.
PATH_NAMING_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

# Tools that cannot write. Scanning these is not merely wasted work: on a synced library
# something else lands a file every few seconds, so scanning a read is a machine for
# attributing other people's writes to whoever happened to be reading at the time.
READ_ONLY_TOOLS = ("Read", "NotebookRead", "Grep", "Glob", "WebFetch", "WebSearch",
                   "TodoWrite", "AskUserQuestion", "ToolSearch")

# Never walked: build noise, and the sync/VCS metadata that changes constantly for reasons
# nobody reviewing a vault cares about.
SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", "node_modules", ".obsidian", ".venv",
             "venv", ".pytest_cache", ".mypy_cache"}

# The ledger writes into this folder. Without excluding it the hook reports its own log
# file on every call, forever.
LEDGER_PREFIX = "resources/logs/"


def vault_root(script_path):
    """The vault is derived from the script's own location, never configured.

    Installed at `<vault>/resources/scripts/activity.py`, so the vault is two levels up.
    Nothing machine-specific is baked into a file that syncs to someone else's tenant.
    """
    return Path(script_path).resolve().parents[2]


def load_config(script_path):
    """The defaults, overlaid with any setting that matches its default's type.

    Type-checked rather than trusted, because a value reaches arithmetic before the line is
    written: `"touched_slack_ms": "2s"` would raise, the catch-all in __main__ would swallow
    it, and the whole ledger would stop being written with nothing to show why. A wrong type
    falls back to the default instead - this hook fails open, including on its own config.
    """
    cfg = dict(DEFAULTS)
    path = Path(script_path).resolve().with_name("activity.config.json")
    try:
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update({k: v for k, v in loaded.items()
                            if k in DEFAULTS and type(v) is type(DEFAULTS[k])})
    except Exception:
        pass
    return cfg


def user_slug(env):
    """A filename-safe writer id. Identity here is 'which teammate', not an account."""
    raw = env.get("USERNAME") or env.get("USER") or "unknown"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-").lower()
    return slug or "unknown"


def relative_to_vault(value, root):
    """Absolute paths carry a machine's user folder and say nothing useful. Trim them."""
    try:
        return Path(value).resolve().relative_to(root).as_posix()
    except Exception:
        return str(value)


def redact_tool_input(tool_name, tool_input, root):
    """What the tool was pointed at, or nothing. Never what it returned."""
    if not isinstance(tool_input, dict) or not tool_name:
        return None
    named = NAME_KEYS.get(tool_name)
    if named and isinstance(tool_input.get(named), str):
        return tool_input[named][:60]
    # Checked before PATH_KEYS: Grep/Glob take an optional `path` alongside their `pattern`
    # (scoping a search to a folder), and the pattern - what was searched for - is the signal
    # worth keeping, not the folder it was scoped to.
    if tool_name in PATTERN_TOOLS and isinstance(tool_input.get("pattern"), str):
        return tool_input["pattern"][:120]
    for key in PATH_KEYS:
        if isinstance(tool_input.get(key), str):
            return relative_to_vault(tool_input[key], root)
    if tool_name == "Bash" and isinstance(tool_input.get("command"), str):
        # First token only. The rest of a command line is where a secret gets pasted.
        tokens = tool_input["command"].split()
        return tokens[0] if tokens else None
    return None


def wants_touch_scan(event_name, tool_name):
    """Whether this event earns a filesystem scan.

    Only completed tool calls, and only tools that neither name their own path nor are
    incapable of writing. A prompt or a session boundary wrote nothing by itself. A failed
    call still counts: a script can write half its output and then exit non-zero, and those
    files are real.
    """
    if not isinstance(event_name, str) or not event_name.startswith("PostToolUse"):
        return False
    if not tool_name:
        return False
    return tool_name not in PATH_NAMING_TOOLS and tool_name not in READ_ONLY_TOOLS


def touched_paths(root, since_epoch, limit):
    """Vault files whose mtime moved at or after `since_epoch`, and how many there were.

    Returns `(paths, total)` - the list capped at `limit`, the count uncapped. One script
    run can write dozens of files, so the cap keeps a single ledger line from becoming a
    page while the count keeps the fact that it happened.

    Fails open like everything else here: a locked file, a vanished directory or a sync
    client holding a handle yields fewer paths, never an exception.

    Walked with `os.scandir` rather than `os.walk` + `os.stat`. Both enumerate the same
    directories, but a `DirEntry` carries the mtime the enumeration already returned, while
    `os.stat(path)` opens the file again - one extra syscall per file, on every scanned tool
    call, on a tree the size of the whole vault. Everything in the loop is measured against
    that: the walk runs on a hot path, so no path here is turned into a `Path`.
    """
    found = []
    try:
        base = str(root)
        cut = len(base) + 1                      # strip "<root>/" without a Path round-trip
        ledger = os.path.join(base, *LEDGER_PREFIX.strip("/").split("/"))
        stack = [base]
        while stack:
            try:
                with os.scandir(stack.pop()) as it:
                    entries = list(it)
            except OSError:       # vanished or locked mid-walk: skip it, keep the rest
                continue
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # The ledger is pruned at descent, not filtered after. It is the one
                        # folder in the vault that grows without bound, and this hook is what
                        # grows it, so walking it would cost more every session forever.
                        if entry.name not in SKIP_DIRS and entry.path != ledger:
                            stack.append(entry.path)
                        continue
                    if entry.name.startswith("~$"):   # Word/Excel lock file, not an edit
                        continue
                    if entry.stat().st_mtime < since_epoch:
                        continue
                except OSError:
                    continue
                found.append(entry.path[cut:].replace("\\", "/"))
    except Exception:
        return [], 0
    found.sort()
    return found[:limit], len(found)


PROMPT_EVENTS = ("UserPromptSubmit", "UserPromptExpansion")


def read_session_records(path):
    """Every parseable line of one session's own ledger file, oldest first.

    A truncated final line is normal, not an error: the hook fails open, so a session
    ending mid-write leaves half a line behind. Skip it and keep the rest.
    """
    records = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
    except OSError:
        return []
    return records


def summarise_session(records, now_iso):
    """What the session actually did, counted from its own lines.

    This exists because `reason` cannot answer it. That field is the harness's - its
    documented values are clear, resume, logout, prompt_input_exit and other - and a
    client is free to report `other` for every ending, and one does. Nothing in this script
    makes that field vary, so the ledger states the facts it does own instead.

    `prompts` is counted per `prompt_id`, not per event: a slash command fires both a
    `UserPromptExpansion` and a `UserPromptSubmit` under one id, and counting the pair
    would double every skill invocation in the vault.
    """
    prompts = tools = writes = failures = denials = 0
    seen_prompts = set()
    last_prompt_at = len(records)

    for index, record in enumerate(records):
        event = record.get("event") or ""
        if event in PROMPT_EVENTS:
            last_prompt_at = index
            prompt_id = record.get("prompt_id")
            if prompt_id is None:
                prompts += 1
            elif prompt_id not in seen_prompts:
                seen_prompts.add(prompt_id)
                prompts += 1
        elif event.startswith("PostToolUse"):
            tools += 1
            if event == "PostToolUseFailure":
                failures += 1
            # `touched` counts as a write: work a script did is still work, and it is the
            # only trace of it. Without this the script blind spot reappears one level up.
            # A path-naming tool counts only when it SUCCEEDED - a failed Write changed no
            # file, and counting it hides the session where every write failed behind a
            # non-zero count, which is exactly the friction `writes: 0` exists to surface.
            # `touched` needs no such guard: a script can write half its output and then
            # exit non-zero, and those files are on disk either way.
            if record.get("touched") or (event == "PostToolUse"
                                         and record.get("tool") in PATH_NAMING_TOOLS):
                writes += 1
        elif event == "PermissionDenied":
            denials += 1

    summary = {
        "prompts": prompts,
        "tools": tools,
        "writes": writes,
        "failures": failures,
        "denials": denials,
        # Tool calls after the final prompt. Zero on a session whose last request produced
        # no tool call at all - which is a fact, not a verdict: a question answered in prose
        # looks the same here as one abandoned. The review reads it, it does not judge it.
        "last_prompt_tools": sum(
            1 for r in records[last_prompt_at + 1:]
            if (r.get("event") or "").startswith("PostToolUse")),
    }
    try:
        started = datetime.datetime.fromisoformat(records[0]["at"])
        summary["duration_s"] = int(
            (datetime.datetime.fromisoformat(now_iso) - started).total_seconds())
    except (KeyError, IndexError, ValueError, TypeError):
        pass
    return summary


def keep_prompt(prompt, cfg):
    """The prompt truncated, or - when prompts are off - only the slash command in it.

    A leading `/para-triage` is a capability invocation, not something someone said. It is
    also the only place that invocation appears: a slash command is expanded, never issued
    as a tool call, so dropping it with the prose would leave `record_prompts: false`
    unable to answer the question the ledger exists for.
    """
    if not isinstance(prompt, str):
        return None
    if cfg["record_prompts"]:
        return prompt[: cfg["prompt_max_chars"]]
    m = re.match(r"\s*(/[A-Za-z0-9:._-]+)", prompt)
    return m.group(1) if m else None


def build_record(event, root, cfg, now_iso):
    tool_name = event.get("tool_name")
    prompt = keep_prompt(event.get("prompt"), cfg)

    record = {
        "at": now_iso,
        "event": event.get("hook_event_name"),
        "session": event.get("session_id"),
        "prompt_id": event.get("prompt_id"),
        "prompt": prompt,
        "tool": tool_name,
        "target": redact_tool_input(tool_name, event.get("tool_input"), root),
        "duration_ms": event.get("duration_ms"),
        "mode": event.get("permission_mode"),
        "source": event.get("source"),
        "reason": event.get("reason"),
        "model": event.get("model"),
    }
    return {k: v for k, v in record.items() if v is not None}


def log_path(root, user, session, today):
    session_tag = (session or "nosession")[:8]
    name = "{}-{}-{}.jsonl".format(today, user, session_tag)
    return root / "resources" / "logs" / "sessions" / name


def main():
    if sys.stdin.isatty():   # no piped event, e.g. someone running this by hand - nothing to log
        return
    raw = sys.stdin.read()
    event = json.loads(raw) if raw.strip() else {}
    if not isinstance(event, dict):
        return

    root = vault_root(__file__)
    cfg = load_config(__file__)
    now = datetime.datetime.now()
    record = build_record(event, root, cfg, now.isoformat(timespec="seconds"))
    if not record.get("event"):
        return

    if cfg["record_touched"] and wants_touch_scan(
            record.get("event"), record.get("tool")):
        # The window is the tool's own run, widened by a slack that covers this hook's
        # own start-up: the file was written before the hook was even launched.
        duration_s = (event.get("duration_ms") or 0) / 1000.0
        slack_s = cfg["touched_slack_ms"] / 1000.0
        paths, total = touched_paths(
            root, time.time() - duration_s - slack_s, cfg["touched_max_files"])
        if paths:
            record["touched"] = paths
            if total > len(paths):
                record["touched_total"] = total

    path = log_path(root, user_slug(os.environ), event.get("session_id"), now.strftime("%Y%m%d"))
    path.parent.mkdir(parents=True, exist_ok=True)

    # Read before appending, so the summary describes the session rather than including
    # the line announcing its end. A session running past midnight writes to two files and
    # this summarises today's; that is a rounding error next to having no answer at all.
    if record["event"] == "SessionEnd" and cfg["record_summary"]:
        record["summary"] = summarise_session(read_session_records(path), record["at"])
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
