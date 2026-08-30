#!/usr/bin/env python3
"""Append-only record of how a vault actually gets used.

para-os-integration: activity 2026.08.03

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

Install and configuration: see README.md in this folder.
"""

import datetime
import json
import os
import re
import sys
from pathlib import Path

DEFAULTS = {"record_prompts": True, "prompt_max_chars": 500}

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


def vault_root(script_path):
    """The vault is derived from the script's own location, never configured.

    Installed at `<vault>/resources/scripts/activity.py`, so the vault is two levels up.
    Nothing machine-specific is baked into a file that syncs to someone else's tenant.
    """
    return Path(script_path).resolve().parents[2]


def load_config(script_path):
    cfg = dict(DEFAULTS)
    path = Path(script_path).resolve().with_name("activity.config.json")
    try:
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update({k: v for k, v in loaded.items() if k in DEFAULTS})
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


def keep_prompt(prompt, cfg):
    """The prompt truncated, or - when prompts are off - only the slash command in it.

    A leading `/para-triage` is a capability invocation, not something someone said. It is
    also the only place that invocation appears: a slash command is expanded, never issued
    as a tool call, so dropping it with the prose would leave `record_prompts: false`
    unable to answer the question the ledger exists for.
    """
    if not isinstance(prompt, str):
        return None
    if cfg.get("record_prompts", True):
        return prompt[: int(cfg.get("prompt_max_chars", 500))]
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

    path = log_path(root, user_slug(os.environ), event.get("session_id"), now.strftime("%Y%m%d"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
