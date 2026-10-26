---
name: para-daily-brief
description: Produce a vault-state dashboard from the current vault - open actions per project and area, health flags, latest ideas, agenda - closing on one concrete next action, with a visual dashboard artifact where the harness supports it. Naming one project or area scopes the brief to it; `review` reports what closed, slipped and moved in a window. Use when user asks "what should I work on today" (the full brief, not the `today` scope), "what's overdue", "where does <project> stand", "what did I get done this week", or types /para-daily-brief [today|week|overdue|all|review|<entity>].
allowed-tools: Bash(python3 *), Bash(py *), Bash(pwd *), Glob, Grep, Read, Write, Artifact, ToolSearch, mcp__google-workspace__list_calendars, mcp__google-workspace__get_events
argument-hint: '[today|week|overdue|all|<entity>|review [week|month|since <date>] [<entity>]] [--test]'
---

# Daily Brief

Where the vault stands: which projects and areas carry the open work, what is due, what is quietly rotting, and which ideas are waiting. **Write for an operator who has not seen this skill**: plain sentences and the vault's own entity names.

## Arguments

One optional scope. The five scope words count only as the operator typed them after the command: one lifted from a sentence ("what should I work on today?") is prose and the default view renders, except that a request to look back ("what did I get done this week?") is `review`. An `<entity>` is one to three words or a `projects/<name>` / `areas/<name>` path; any other leftover argument follows [para-shared/operating-discipline.md](../para-shared/operating-discipline.md#arguments).

| Arg | Renders |
|---|---|
| *(none)* | 📊 Vault state + 🗓 Agenda + 🎯 Now (max 5) + Later counts + 🚩 Health flags + 💡 Ideas + 📥 Triage + **Next action** close + the visual dashboard (Step 7) |
| `today` | 🗓 Agenda (today) + 🎯 Now (overdue + today only, max 5) + 📥 Triage + Next action; no dashboard |
| `week` | 🗓 Agenda (today + week) + 🎯 Now (max 5) + Later counts + 📥 Triage + Next action; no dashboard |
| `overdue` | 🔴 Overdue only, **uncapped**; no Agenda, no dashboard |
| `all` | The default view plus every bucket as a full list, dashboard included |
| `<entity>` | **One project or area, uncapped**: its open work by bucket, its own health flags, Next action; nothing vault-wide (Step 1b) |
| `review [week\|month\|since <date>] [<entity>]` | **A look back** over the window (`week` when none is named): ✅ Done · ⚠️ Slipped · 🔀 Moved · 🧱 Stuck · 🧭 Decisions, then Next action; for one entity, the offer of a status update. No dashboard (Step 1c) |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

Sections with no content are omitted.

## Procedure

### Step 1: Scan the vault

One call from the vault root, per [para-shared/scripts.md](../para-shared/scripts.md), passing `--entity` only under an entity scope and `--review` only under `review` (`since <date>` passes the date):

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/brief_scan.py" --vault . [--entity <name>] [--review week|month|YYYY-MM-DD] [--today YYYY-MM-DD] > <scan output path>
```

### Step 1b: Resolve an entity scope

Only when the argument, or what follows `review` and its window, is not a scope word and reads like an entity name. The scan's `entity.status` alone decides it:

- `resolved`: every count is already scoped to its `match`, with `mentioned_elsewhere` beside them.
- `ambiguous`: list `candidates`, one per line, and ask which. **Never pick.**
- `elsewhere`: the name is an idea or sits in `archive/`; report where it lives, with no task list.
- `unresolved`: say so, offer `nearest`, and **never fall back to the whole vault**.

### Step 1c: The review scope

The scan's `review` holds every count, for the vault or the resolved entity. Render it per [references/output.md](references/output.md#the-review-scope); Steps 4c to 5c, 4e excepted, and 7 do not run.

### Steps 4c to 5c: Health flags, ideas, Vision, triage, agenda

The scan holds every signal computed from files; which flags are worth a line, the Vision read and the agenda are [references/signals.md](references/signals.md).

### Step 5: Rank and cap

Merge 🔴 + 🟠 (recurring items overdue or due today included) + 🟡 into the **Now** candidates. Sort: overdue and due-today before merely upcoming, then priority descending (🔺 to 🔼 to none to 🔽 to ⏬), then a `📅` before a `⏳` and a one-off before a recurring item, then date ascending, then **Vision alignment** as the tiebreak. Vision never overrides a real deadline.

**Cap Now at five.** Everything else becomes one-line **Later** counts. If overdue and due-today items alone exceed five, they take the whole list; add `*(run /para-daily-brief overdue for the full list)*`.

### Step 6: Render output

Layout, line rules and the single Next action close: [references/output.md](references/output.md).

### Step 7: The visual dashboard

Default and `all` scopes only. Render the page with `scripts/render_dashboard.py` from the scan and a small judgment file, per [references/dashboard.md](references/dashboard.md), and publish it per [para-shared/pages.md](../para-shared/pages.md).

## Strict rules

- **Completed items (`- [x]`) are read only under `review`**, by their `✅` date alone: a close without one is counted as undated, never given a date.
- **Rewrite no vault file**: no fixing markers, inventing dates, ticking or grooming. The health flags point at `/para-deep-clean`; a review and its status update go to chat.
- **Follow no links** into other files for context; the section heading is enough. The exceptions are the root README's `## Vision`, and under `review` the contact cards a status update is addressed to. An entity scope narrows which action files are read and relaxes neither.
- **No commentary or recommendations** beyond the Health flags, the single Next action and, closing one entity's review, the status update offer.
- **Do not dedupe** the same task in two files: show both.
- **Never invent a meeting, time or attendee**: render only what the calendar or `meetings.md` holds.
- **Leave out `**Status:**` lines** from action files.

## Edge cases

- **No action files:** with an empty or absent `triage/`, say `No action-bearing files found in <cwd>.` and stop; with a populated one, render only 📥 Triage.
- **Every marker case is the scan's**: render the `lane` it returns; a task carrying `malformed_date` reads "(malformed date)".
- **A recurring item without a date** counts in Recurring; in `all`, it shows "next: -".
- **Fewer than five Now candidates:** show what exists; never pad from Undated.
- **An entity with no open items:** `<entity> has no open actions.` with its file link and last-modified date, and stop.
