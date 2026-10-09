---
name: para-daily-brief
description: Produce a vault-state dashboard from the current vault - open actions per project and area, health flags, latest ideas, agenda - closing on one concrete next action, with a visual dashboard artifact where the harness supports it. Naming one project or area scopes the brief to it; `review` reports what closed, slipped and moved in a window. Use when user asks "what should I work on today" (the full brief, not the `today` scope), "what's overdue", "where does <project> stand", "what did I get done this week", or types /para-daily-brief [today|week|overdue|all|review|<entity>].
allowed-tools: Bash(python3 *), Bash(py *), Glob, Grep, Read, Write, Artifact, ToolSearch, mcp__google-workspace__list_calendars, mcp__google-workspace__get_events
argument-hint: '[today|week|overdue|all|<entity>|review [week|month|since <date>] [<entity>]] [--test]'
---

# Daily Brief

A single-pass, date-aware picture of **where the vault stands**: which projects and areas carry the open work, what is actually due, what is quietly rotting, and which ideas are waiting. Covers project and area action files plus per-contact files (relationship-paced actions).

**Read-only contract.** It reports; the operator decides. Repairs belong to `/para-deep-clean`.

**Operator-language output.** Every line must be actionable by a reader who has not seen this skill's internals: plain sentences, the vault's own entity names, no bucket jargon beyond the section titles.

**This skill is vault-agnostic.** It discovers action-bearing files at runtime and reads the vault's emoji task markers.

## Arguments

Optional single scope argument. The five scope words are reserved, and count only as the operator typed them after the command: one lifted from their sentence ("what should I work on today?") is prose, and the default view renders, except that a request to look back ("what did I get done this week?") is `review`; an `<entity>` is one to three words or a `projects/<name>` / `areas/<name>` path, and any other leftover argument follows [para-shared/operating-discipline.md](../para-shared/operating-discipline.md#arguments).

| Arg | Renders |
|---|---|
| *(none)* | 📊 Vault state + 🗓 Agenda + 🎯 Now (max 5) + Later counts + 🚩 Health flags + 💡 Ideas + 📥 Triage + **Next action** close + the visual dashboard artifact (Step 7) |
| `today` | 🗓 Agenda (today) + 🎯 Now (overdue + today only, max 5) + 📥 Triage + Next action (morning standup view; no artifact) |
| `week` | 🗓 Agenda (today + week) + 🎯 Now (max 5) + Later counts + 📥 Triage + Next action (no artifact) |
| `overdue` | 🔴 Overdue only, **uncapped** - the strict "what's late" view (no Agenda, no artifact) |
| `all` | Full expansion: everything in the default view, plus every bucket as a full list (the audit view), artifact included |
| `<entity>` | **One project or area, uncapped**: its open work by bucket, its own health flags, Next action. No Vault state, Agenda, Ideas, Triage or artifact - those are vault-wide questions and this is not a vault-wide view (Step 1b) |
| `review [week\|month\|since <date>] [<entity>]` | **A look back** over the window (`week` when none is named): ✅ Done · ⚠️ Slipped · 🔀 Moved · 🧱 Stuck · 🧭 Decisions, then Next action; for one entity, the offer of a status update. No artifact (Step 1c) |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

Sections with no content are omitted.

## Procedure

### Step 1: Scan the vault

One call from the vault root, per [para-shared/scripts.md](../para-shared/scripts.md):

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/brief_scan.py" --vault . [--entity <name>] [--review week|month|YYYY-MM-DD] [--today YYYY-MM-DD] > <scan output path>
```

Pass `--entity` only under an entity scope, and `--review` only under `review`, with its window (`since <date>` passes the date). It returns:

| Field | Holds |
|---|---|
| `today` | The date the brief is dated by |
| `tasks` | One record per open item: file, line, bucket, scope, section, text, markers, `lane`, `days`, `also_lane`, `malformed_date` |
| `entities`, `totals` | Per-entity rows with the three counts that partition the open count and a `bar` width, and the same four numbers vault-wide |
| `lanes` | Each lane's `(file, line)` references into `tasks`; a recurring item overdue or due today is in `recurring` and that lane too, tagged `🔁` there |
| `file_dates` | Each action file's last-touched date |
| `entity`, `mentioned_elsewhere` | Step 1b |
| `review` | Step 1c |
| `flags`, `ideas`, `triage`, `triage_preview`, `lifecycles` | Steps 4c to 5b |

### Step 1b: Resolve an entity scope

Only when the argument, or what follows `review` and its window, is not a scope word **and reads like an entity name** by the test in Arguments above. Pass it as `--entity`; the scan answers in `entity.status`, and nothing else decides it:

- `resolved` - its `match` is the one folder, and every count below is already scoped to it, with `mentioned_elsewhere` beside them.
- `ambiguous` - list `candidates`, one per line, and ask which. **Never pick.**
- `elsewhere` - the name is an idea or sits in `archive/`; report where it lives, with no task list.
- `unresolved` - say so, offer `nearest`, and **never fall back to the whole vault**.

### Step 1c: The review scope

Only under `review`. The scan's `review` holds every count, for the vault or the entity Step 1b resolved (null where it did not resolve): `window` (`start`, `end`, `days`), `done` (`count`, `undated`, `by_entity` rows of `items`), `slipped`, `moved` (per lifecycle: `count`, `entities`), `stuck` (`overdue`, `no_next_step`) and `decisions`. Render it per [references/output.md](references/output.md#the-review-scope), with no Agenda, Ideas, Triage or artifact. Steps 4c to 5c, 4e excepted, and 7 do not run.

### Steps 2 to 4b: Scan, parse, bucket, aggregate

Done by the scan.

### Steps 4c to 4f: Health flags, ideas lane, Vision, lifecycle counts

The scan's `flags`, `ideas`, `triage` and `lifecycles` hold every signal computed from files. What stays here: the Vision read (4e), plus deciding which flags are worth a line. **Full procedure: [references/signals.md](references/signals.md).**

### Step 5: Rank and cap

Merge 🔴 + 🟠 (recurring items overdue or due today included) + 🟡 into the **Now** candidates. Sort: overdue and due-today items before merely-upcoming ones, then priority descending (🔺 to 🔼 to none to 🔽 to ⏬), then a `📅` before a `⏳` and a one-off before a recurring item, then date ascending, then **Vision alignment** as the tiebreak - an item that visibly advances the Vision outranks one that doesn't, at equal priority and date. Vision never overrides a real deadline.

**Cap Now at five.** Everything else becomes one-line **Later** counts (this week beyond the cap, overdue and due today included; the rest as [output.md](references/output.md) lists them). If overdue and due-today items alone exceed five, they take the whole list; add `*(run /para-daily-brief overdue for the full list)*`.

### Steps 5b to 5c: Triage count and agenda

**Full procedure: [references/signals.md](references/signals.md).**

### Step 6: Render output

Exact layout, line rules, and the single Next action close. **Full spec: [references/output.md](references/output.md).**

### Step 7: The visual dashboard

Default and `all` scopes only. Without an Artifact tool, or when the publish fails, say so in one line and move on.

Render the page with `scripts/render_dashboard.py` from the scan and a small judgment file, per [references/dashboard.md](references/dashboard.md), which owns what the judgment holds, the remembered URL and the title match that updates yesterday's page in place. The page goes to the harness's scratchpad or temp directory, **never inside the vault**. Publish it and give the user the link on one line.

## Strict rules

- **Do not parse completed items (`- [x]`)** outside `review`, which reads them by their `✅` date alone: a close without one is counted as undated, never given a date.
- **Do not rewrite any vault file.** No fixing missing markers, no inventing dates, no ticking, no grooming - undated is reported as undated. The health flags point at `/para-deep-clean`. A review and its status update go to chat, never to a file.
- **Do not follow links** into other files for extra context. The section heading is sufficient. (Exceptions: the root README's `## Vision`, and under `review` the contact cards a status update is addressed to.)
- **Do not add commentary or recommendations** beyond the Health flags, the single Next action and, closing one entity's review, the status update offer. Decisions are the operator's.
- **Do not dedupe cross-referenced items** (same task in two files). Show both.
- **Never invent a meeting, time or attendee.** Render only what the calendar or `meetings.md` line holds.
- **Do not include `**Status:**` lines** from actions files.
- **An entity scope narrows which action files are read**, nothing more: it neither unlocks `brief.md` nor relaxes the no-follow-links rule.

## Edge cases

- **Vault with no action files:** with empty or absent `triage/`, say `No action-bearing files found in <cwd>.` and stop; with a populated triage, render only 📥 Triage.
- **Every marker case is the scan's**, gate, cadence and malformed date alike: render the `lane` it returns, and a task carrying `malformed_date` reads "(malformed date)".
- **Recurring item without a date:** counts in Recurring; in `all`, show "next: -".
- **Fewer than 5 Now candidates:** show what exists; never pad the list from Undated.
- **Entity scope resolving to an entity with no open items:** say so in one line (`<entity> has no open actions.`) with its file link and last-modified date, and stop.
