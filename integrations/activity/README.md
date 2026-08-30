# Activity ledger

Record how a vault is actually used, so the vault can be improved against evidence instead of impressions.

```
Claude Code session  ──▶  hook: activity.py  ──▶  <vault>/resources/logs/sessions/*.jsonl
                                                          │
                                                          ▼
                                            /para-activity-review reads it and reports
```

Git tells you what changed in a vault. This tells you what someone **asked for**, which skills they reached for, where a session failed, and what they never touched at all. Those are different questions, and only the second one improves the product: a skill nobody invokes and a `triage/` that fills while `/para-triage` is never run are both invisible to a commit log.

**Opt-in, deliberately.** This is not part of [`base/`](../../base/) and no vault gets it by bootstrapping. It is installed by a decision, per vault, by someone who has said what it collects to everyone it collects from. A knowledge vault that quietly logs its readers would be a worse product than one with no telemetry at all.

## When it earns its place

- A **team** shares a vault and you maintain it for them. The single most valuable output is the list of capabilities nobody used once.
- You are **rolling para-os out** to people who did not build it, and the first weeks are the only chance to see the unlearned version of the system.
- You maintain a vault **for yourself** and want the same answer about your own habits. It works unchanged; the report is just shorter.

It earns nothing on a vault nobody else touches and nobody is improving. Skip it there.

## Prerequisites

- **Python 3.9+**, no packages. Examples below use `py` (Windows); `python3` works in its place.
- **Claude Code**, terminal or the Desktop app's Code tab. Both read the same project settings, and hooks fire in both.
- **The people using the vault know it is on.** Not a technical prerequisite. See [What to tell people](#what-to-tell-people).

## Install

1. Copy `activity.py` into the vault at `resources/scripts/`. The vault root is derived from the script's own path, so there is nothing to configure and no machine-specific path in a file that syncs.

2. Wire the hooks in the vault's `.claude/settings.json`. Hooks run with the vault folder as their working directory, so the relative path below is enough:

   ```json
   {
     "hooks": {
       "SessionStart":      [{ "hooks": [{ "type": "command", "command": "py resources/scripts/activity.py" }] }],
       "UserPromptSubmit":  [{ "hooks": [{ "type": "command", "command": "py resources/scripts/activity.py" }] }],
       "UserPromptExpansion": [{ "hooks": [{ "type": "command", "command": "py resources/scripts/activity.py" }] }],
       "PostToolUse":       [{ "hooks": [{ "type": "command", "command": "py resources/scripts/activity.py" }] }],
       "PostToolUseFailure":[{ "hooks": [{ "type": "command", "command": "py resources/scripts/activity.py" }] }],
       "PermissionDenied":  [{ "hooks": [{ "type": "command", "command": "py resources/scripts/activity.py" }] }],
       "SessionEnd":        [{ "hooks": [{ "type": "command", "command": "py resources/scripts/activity.py" }] }]
     }
   }
   ```

   One command serves one platform. A mixed Windows and macOS team needs `py` on one and `python3` on the other, and settings.json has no branch for that: pick the majority platform and install the minority's copy at user level.

3. Each person accepts the **workspace trust prompt** once, the first time they open the folder. Project hooks do not run before that. It is stored per folder per machine, so it is a first-open step, not a recurring one. Say so in the walkthrough or it reads as a security warning about your own vault.

4. Verify before trusting it: open a session, ask one thing, then look for a file in `resources/logs/sessions/`. No file means the hook did not fire, which is nearly always step 3.

## Configuration

Optional `resources/scripts/activity.config.json`, beside the script:

```json
{ "record_prompts": true, "prompt_max_chars": 500 }
```

| Key | Default | Effect |
|---|---|---|
| `record_prompts` | `true` | Record what people typed. Setting it `false` keeps the structural signal - which skills, which files, what failed - and drops the words: a prompt that opens with a slash command still records that command alone, since `/para-triage` is an invocation rather than something someone said. The report gets thinner but stays useful |
| `prompt_max_chars` | `500` | Truncation. A prompt's first lines carry the intent |

## What it records, and what it refuses to

One JSONL line per event: timestamp, event name, session id, prompt id, the prompt, the tool name, what the tool was pointed at, duration, permission mode, and how the session ended. For a skill or a subagent, "what it was pointed at" is the skill or agent **name** - the signal `/para-activity-review` builds adoption from, since `Skill` alone says a skill ran but never which.

A prompt is recorded as typed, so a credential pasted into one is recorded too. The Bash redaction below does not cover that, and nothing can: switch `record_prompts` off in a vault where that is a real risk.

Three refusals, each closing a way this could quietly become surveillance:

- **`tool_response` is never written.** It carries file contents. The ledger records that someone read `areas/network/x.md`, never what the file said.
- **A Bash command keeps its first token and loses the rest.** `curl` survives; the URL and the bearer token in it do not. A command line is exactly where a credential gets pasted by accident.
- **An unrecognised tool records its name only.** An MCP call's arguments can hold a mail body, and a list of keys that look safe today is a list that rots. Silence is the default; file tools are the exception.

The **full session transcript is not read**, though every hook event names its path. Doing so would be the richest source available and a different bargain entirely: "what you asked the vault to do" is not "everything you said". If you ever want it, ask the people first.

## Where the log goes

`<vault>/resources/logs/sessions/YYYYMMDD-<user>-<session>.jsonl`, one file per session per person per day. Several people syncing one folder cannot share one append target: that produces conflict copies, not a log.

This is machine output living inside a human vault, which the [scripts convention](../../base/resources/scripts/README.md) otherwise avoids by putting runtime state under `~/.paraos/`. It is deliberate and it is the only choice that works: state outside the vault never reaches the person maintaining it. Two things keep it honest - the files are small and machine-readable rather than something a reader must skim, and `/para-activity-review` prunes what it has already reported.

If the vault has a git mirror, exclude `resources/logs/` from it. The files arrive through the sync anyway, and vault history should record decisions, not keystrokes.

## Reading it

[`/para-activity-review`](../../base/.claude/skills/para-activity-review/SKILL.md). It is the consumer, and the log is not meant to be read by eye.

## What to tell people

Whoever uses the vault should hear this before the first session, in their words, not yours:

- What is recorded: what you ask, which tools run, what fails. Not file contents, not your conversation.
- Why: to fix the parts of this that do not work, which is otherwise guesswork.
- Where it lives: in your own vault, in your own tenant. Readable by you.
- What it is not: an audit of individuals or a measure of anyone's output.

If any of that is uncomfortable to say plainly, that discomfort is the finding, and the honest move is not to install this.
