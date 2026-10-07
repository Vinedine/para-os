---
name: para-daily-brief
description: Produce a vault-state dashboard from the current vault - open actions per project and area, health flags, latest ideas, agenda - closing on one concrete next action, with a visual dashboard artifact where the harness supports it. Naming one project or area scopes the brief to it; `review` reports what closed, slipped and moved in a window. Use when user asks "what should I work on today" (the full brief, not the `today` scope), "what's overdue", "where does <project> stand", "what did I get done this week", or types /para-daily-brief [today|week|overdue|all|review|<entity>].
allowed-tools: Bash(python3 *), Bash(py *), Bash(git log *), Bash(git status *), Bash(stat *), Bash(ls *), Bash(wc *), Glob, Grep, Read, Write, Artifact, ToolSearch, mcp__google-workspace__list_calendars, mcp__google-workspace__get_events
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

Pass `--entity` only under an entity scope, and `--review` only under `review`, with its window (`since <date>` passes the date). **Field table, and the by-hand fallback where the script cannot run: [references/task-scan.md](references/task-scan.md).**

### Step 1b: Resolve an entity scope

Only when the argument, or what follows `review` and its window, is not a scope word **and reads like an entity name** by the test in Arguments above. Pass it as `--entity`; the scan answers in `entity.status`, and nothing else decides it:

- `resolved` - its `match` is the one folder, and every count below is already scoped to it, with `mentioned_elsewhere` beside them.
- `ambiguous` - list `candidates`, one per line, and ask which. **Never pick.**
- `elsewhere` - the name is an idea or sits in `archive/`; report where it lives, with no task list.
- `unresolved` - say so, offer `nearest`, and **never fall back to the whole vault**.

### Step 1c: The review scope

Only under `review`. The scan's `review` block holds every count, for the vault or for the entity Step 1b resolved; render it per [references/output.md](references/output.md#the-review-scope), with no Agenda, Ideas, Triage or artifact. A review looks back, so Steps 4c to 5c and 7 do not run; Step 4e still breaks the Next action's ties. **The rules it applies, and the by-hand fallback: [references/task-scan.md](references/task-scan.md#the-review-window).**

### Steps 2 to 4b: Scan, parse, bucket, aggregate

Done by the scan. **What it implements, and the fallback when it cannot run: [references/task-scan.md](references/task-scan.md).**

### Steps 4c to 4f: Health flags, ideas lane, Vision, lifecycle counts

The scan's `flags`, `ideas` and `triage` hold every signal computed from files. The scan's `lifecycles` holds the lifecycle counts (4f). What stays here: the Vision read (4e), plus deciding which flags are worth a line. **Full procedure: [references/signals.md](references/signals.md).**

### Step 5: Rank and cap

Merge 🔴 + 🟠 (recurring items overdue or due today included) + 🟡 into the **Now** candidates. Sort: overdue and due-today items before merely-upcoming ones, then priority descending (🔺 to 🔼 to none to 🔽 to ⏬), then date ascending, then **Vision alignment** as the tiebreak - an item that visibly advances the Vision outranks one that doesn't, at equal priority and date. Vision never overrides a real deadline.

**Cap Now at five.** Everything else becomes one-line **Later** counts (this week beyond the cap, overdue and due today included; next 30 days; later; recurring; waiting; undated). If overdue and due-today items alone exceed five, they take the whole list; add `*(run /para-daily-brief overdue for the full list)*`.

**The cap is a vault-wide device**: an entity scope is already the filter, so it renders every open item, by bucket ([references/output.md](references/output.md)).

### Steps 5b to 5c: Triage count and agenda

**Full procedure: [references/signals.md](references/signals.md).**

### Step 6: Render output

Exact layout, line rules, and the single Next action close. **Full spec: [references/output.md](references/output.md).**

### Step 7: The visual dashboard

Default and `all` scopes only (never an entity scope), and **only when an Artifact tool is available in the harness** - if it is not, the last edge case below applies.

Render the page with `scripts/render_dashboard.py` from the scan and a small judgment file, per [references/dashboard.md](references/dashboard.md), which owns the page spec, the remembered URL and the title match that updates yesterday's page in place. The page goes to the harness's scratchpad or temp directory, **never inside the vault**. Publish it and give the user the link on one line.

## Strict rules

- **Do not parse completed items (`- [x]`)** outside `review`, which reads them by their `✅` date alone: a close without one is counted as undated, never given a date.
- **Do not rewrite any vault file.** No fixing missing markers, no inventing dates, no ticking, no grooming - undated is reported as undated. The health flags point at `/para-deep-clean`; this skill never applies them. A review and its status update go to chat, never to a file.
- **Do not follow links** into other files for extra context. The section heading is sufficient. (Exceptions: the root README's `## Vision`, an idea brief's stage line and revisit sentence, and the head of each triage item, the last two read by the scan for the dashboard; under `review`, the development logs the scan reads and the contact cards a status update is addressed to.)
- **Do not add commentary or recommendations** beyond the Health flags, the single Next action and, closing one entity's review, the status update offer. Decisions are the operator's.
- **Do not dedupe cross-referenced items** (same task in two files). Show both.
- **Meetings: today and future only, never invented.** Render only what the calendar or `meetings.md` line contains - never fabricate a meeting, time, or attendee. Calendars are read-only.
- **Do not include `**Status:**` lines** from actions files.
- **Do not resolve an ambiguous entity name by choosing one**, and never fall back to the whole vault when a name matches nothing. Ask.
- **An entity scope does not unlock the brief.** It narrows *which action files* are read; it does not relax the no-follow-links rule above. A status read that summarises `brief.md` is a different contract, not this argument.

## Edge cases

- **Vault with no action files:** with empty or absent `triage/`, say `No action-bearing files found in <cwd>.` and stop; with a populated triage, render only 📥 Triage.
- **Every marker case is the scan's**, gate, cadence and malformed date alike: render the `lane` it returns, and a task carrying `malformed_date` reads "(malformed date)". Where the fallback is running instead, [references/task-scan.md](references/task-scan.md) holds the same rules.
- **Recurring item without a date:** counts in Recurring; in `all`, show "next: -".
- **Fewer than 5 Now candidates:** show what exists; never pad the list from Undated.
- **`resources/ideas/` missing or empty:** omit the Ideas lane.
- **Entity scope resolving to an entity with no open items:** say so in one line (`<entity> has no open actions.`) with its file link and last-modified date, and stop. An entity that is genuinely clear is a real answer, not an empty brief.
- **Entity scope naming an idea or an archived entity:** neither carries an `actions.md` by the vault's own rule, so report where it lives (`<name> is an idea; ideas hold no actions`) rather than an empty result.
- **Artifact publish fails** (no tool, no network): say so in one line and move on.
