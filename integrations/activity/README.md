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

2. Wire the hooks in the vault's `.claude/settings.json`. Every command is anchored to `$CLAUDE_PROJECT_DIR`, the vault root, and the quotes around it are not optional - a vault path usually contains spaces:

   ```json
   {
     "hooks": {
       "SessionStart":      [{ "hooks": [{ "type": "command", "command": "py \"$CLAUDE_PROJECT_DIR/resources/scripts/activity.py\"" }] }],
       "UserPromptSubmit":  [{ "hooks": [{ "type": "command", "command": "py \"$CLAUDE_PROJECT_DIR/resources/scripts/activity.py\"" }] }],
       "UserPromptExpansion": [{ "hooks": [{ "type": "command", "command": "py \"$CLAUDE_PROJECT_DIR/resources/scripts/activity.py\"" }] }],
       "PostToolUse":       [{ "hooks": [{ "type": "command", "command": "py \"$CLAUDE_PROJECT_DIR/resources/scripts/activity.py\"" }] }],
       "PostToolUseFailure":[{ "hooks": [{ "type": "command", "command": "py \"$CLAUDE_PROJECT_DIR/resources/scripts/activity.py\"" }] }],
       "PermissionDenied":  [{ "hooks": [{ "type": "command", "command": "py \"$CLAUDE_PROJECT_DIR/resources/scripts/activity.py\"" }] }],
       "SessionEnd":        [{ "hooks": [{ "type": "command", "command": "py \"$CLAUDE_PROJECT_DIR/resources/scripts/activity.py\"" }] }]
     }
   }
   ```

   **Not a bare relative path.** A hook inherits the calling session's working directory, not the vault root, and that directory moves: `cd` inside a Bash tool call persists for the rest of the session, so the moment a session steps into a subfolder every later hook fails to locate the script - `can't open file ... No such file or directory` - until something `cd`s back. Nothing surfaces the gap; the ledger simply stops recording, and a usage review reads the silence as an idle session rather than a broken hook.

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
| `record_touched` | `true` | The `touched` scan below. Set `false` to drop it and get the un-scanned behaviour |
| `touched_max_files` | `40` | Cap on paths listed in one line. The uncapped count survives as `touched_total` |
| `touched_slack_ms` | `2000` | How far before the tool's own start the window reaches, covering this hook's start-up. Raise it on a slow machine; every extra second widens the window for a false positive |
| `record_summary` | `true` | The `SessionEnd` summary below. Set `false` to drop it |

## What it records, and what it refuses to

One JSONL line per event: timestamp, event name, session id, prompt id, the prompt, the tool name, what the tool was pointed at, duration, permission mode, and how the session ended. For a skill or a subagent, "what it was pointed at" is the skill or agent **name** - the signal `/para-activity-review` builds adoption from, since `Skill` alone says a skill ran but never which.

### `touched`: the files a script wrote

Keeping only a command's first token leaves a wide gap. A script run through Bash writes files the hook never sees, so a run that wrote sixty files is recorded as `py`, and a review then reports those files as never having been written. In one real vault, **52 of 63 changed files had no write event at all**.

So on any completed tool call that does not already name its own path, the hook asks the filesystem which vault files moved while the tool was running, and records them as `touched` (with `touched_total` when the list is capped). `Write` and `Edit` are skipped: they already name their file, and scanning them would make one edit look like two.

This stays inside the privacy rule - a path, never content, and only inside the vault - and it costs one directory walk per scanned tool call, about 25 ms on a 330-file vault. Tools that cannot write (`Read`, `Grep`, `Glob`, `WebFetch`, ...) are skipped as well, which is not an optimisation: on a synced library something lands a file every few seconds, so scanning a read is a machine for attributing other people's writes to whoever was reading at the time.

**It is inferred, not observed, and the field name says so.** The window is the tool's own duration widened by `touched_slack_ms`, so on a synced library a file that another person's sync client landed inside that window looks exactly like one this call wrote, and a long-running command widens the window further. Read `touched` as evidence of what changed, never as proof of who changed it. `resources/logs/` is excluded, or the hook would report its own log on every call.

### `summary`: what the session did, because `reason` cannot say

`SessionEnd` carries a `reason`, and it belongs to the harness, not to this script. Its documented values are `clear`, `resume`, `logout`, `prompt_input_exit` and `other`, and **a client is free to report `other` for every ending** - one did, for every session in a real ledger, which left the "how did sessions end" signal `/para-activity-review` is specified to compute simply nonexistent.

No amount of care here makes that field vary, and inventing a livelier value would be fabricating data. So `reason` is still recorded exactly as received, and alongside it the `SessionEnd` line now carries a `summary` counted from the session's own ledger file:

| Field | Meaning |
|---|---|
| `prompts` | Distinct requests, counted **per `prompt_id`** - a slash command fires both a `UserPromptExpansion` and a `UserPromptSubmit` under one id, and counting the pair would double every skill invocation |
| `tools` | Tool calls, failures included |
| `writes` | Calls that changed a file, `touched` included, so a script's work still counts |
| `failures`, `denials` | `PostToolUseFailure` and `PermissionDenied` counts |
| `duration_s` | First event to session end |
| `last_prompt_tools` | Tool calls after the final prompt |

`prompts: 0` is the one that matters most in practice. In one real vault, **72% of sessions contained no prompt at all**, so every session count computed from file names was roughly three times the number of sessions anyone actually worked in. Stated as a field, a review can exclude them by reading one number instead of inferring it.

`last_prompt_tools: 0` says the final request produced no tool call. That is a fact and not a verdict: a question answered in prose looks identical here to one abandoned, and the review is told to read it that way.

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
