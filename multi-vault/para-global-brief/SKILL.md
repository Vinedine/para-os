---
name: para-global-brief
description: One brief and one page across every vault the registry lists - today, the rest of the week and the next two weeks with every calendar's meetings, the operator's own vaults by area, project and person, the vaults they keep but sum counted, every vault's health card, and one next action. Read-only. Use when the operator runs several vaults and asks "what's going on across my vaults", "what do I need to do today across everything", "what does my week look like", "brief me on all my vaults", "are my vaults healthy", or types /para-global-brief.
allowed-tools: Bash(python3 *), Bash(py *), Read, Write, Artifact, ToolSearch, mcp__google-workspace__list_calendars, mcp__google-workspace__get_events
argument-hint: '[--test]'
---

# Global brief

One view across every registered vault, so an operator with several does not run `/para-daily-brief` in each. **It writes nothing but its scan output, its judgment file and its page.**

- **It needs `para-audit/`, `para-daily-brief/` and `para-shared/` beside it.** Its scripts run over theirs.
- **Run it from anywhere.** The registry, `${PARAOS_HOME:-~/.paraos}/vaults.json`, is the only list of vaults. A para-os home the operator names in prose replaces it for the run.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Every registered vault |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

A leftover argument follows [para-shared/operating-discipline.md](../para-shared/operating-discipline.md#arguments).

## Step 1: Run the scan

Per [para-shared/scripts.md](../para-shared/scripts.md):

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/global_scan.py" --model <your own model id> [--paraos-home <folder holding vaults.json>] > <scan output path>
```

Exit 3: no registry, or one listing nothing. Say so, point at `vaults.json.template` in the multi-vault README, and stop. What each vault shows, and every field, is in the script's docstring.

## Step 2: Read the calendars

Each of the scan's `calendars` once, per [para-shared/connectors.md](../para-shared/connectors.md#calendar), from today to its `horizon`, starts in the operator's time zone ([timestamps.md](../para-shared/timestamps.md)), all-day "free" placeholders dropped. Each event becomes `{date, start, end, title, source}`, `source` the row's Source. A calendar that answers with an error goes in `agenda_note` with what failed, never silently out. The scan's `meetings` are already read.

## Step 3: Report in chat

Everything comes from the scan and the calendars. Read no vault's files.

1. **Today**: the meetings, then the `urgent` items, at most five, each tagged with its vault; then one line per `summaries` vault with its overdue and due-today counts.
2. **One table, one row per vault**, in registry order: `Vault`, `Shown` (the `treatment`, and the `role` where it is not keeper), `Open`, `Overdue`, `This week`, `Triage` (with a waiting proposal named), and `Health`: the card's level (healthy, watch, needs care) and each signal at watch or care.
3. **Excluded**: every `excluded` entry with its `status` word and its reason, or one line saying none was.
4. **One next action**, closing the brief: the single item to do first, its vault named; the close names no second item.

## Step 4: The page

Write a judgment file beside the scan output: `next_action` as the close names it (`vault`, plus its `file` and `line` where it is a task), `events` from Step 2, and any `agenda_note`. Then:

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/render_global.py" --scan <scan output path> --judgment <judgment file> --out <scratch folder>/global-brief.html [--paraos-home <folder>]
```

Exit 2 names what the judgment got wrong: fix it and render again. Publish per [para-shared/pages.md](../para-shared/pages.md), the printed `key` standing in for the vault root.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Never drop a vault silently.** A vault left out reads exactly like one with nothing due.
- **Never invent a meeting, time or attendee**: render only what a calendar or `meetings.md` holds.
