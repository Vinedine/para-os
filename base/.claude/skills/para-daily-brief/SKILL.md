---
name: para-daily-brief
description: Produce a vault-state dashboard from the current vault - open actions per project and area, health flags, latest ideas, agenda - closing on one concrete next action, with a visual dashboard artifact where the harness supports it. Naming one project or area instead scopes the whole brief to it. Use when user asks "what should I work on today", "what's overdue", "where does the vault stand", "where does <project> stand", "what's open on <project>", or types /para-daily-brief [today|week|overdue|all|<entity>].
allowed-tools: Bash, Glob, Grep, Read, Write, Artifact, ToolSearch, mcp__google-workspace__list_calendars, mcp__google-workspace__get_events
arg-hint: '[today|week|overdue|all|<entity>]'
---

# Daily Brief

A single-pass, date-aware picture of **where the vault stands**: which projects and areas carry the open work, what is actually due, what is quietly rotting, and which ideas are waiting. The task list is capped and ranked; the shape of the vault leads. Covers project and area action files plus per-contact files (relationship-paced actions).

**Read-only contract.** This skill never edits a file. Its only writes are the temporary HTML for the visual dashboard (Step 7), written outside the vault. It reports; the operator decides. Repairs belong to `/para-deep-clean`.

**Operator-language output.** Every line must be actionable by a reader who has not seen this skill's internals: plain sentences, the vault's own entity names, no bucket jargon beyond the section titles.

**This skill is vault-agnostic.** It discovers action-bearing files at runtime and relies on Obsidian Tasks plugin conventions - no vault-specific paths are hardcoded. There are two vault types, detected in Step 1b.

## Arguments

Optional single scope argument. The four scope words are reserved; **anything else is read as an entity name**.

| Arg | Renders |
|---|---|
| *(none)* | 📊 Vault state + 🗓 Agenda + 🎯 Now (max 5) + Later counts + 🚩 Health flags + 💡 Ideas + 📥 Triage + **Next action** close + the visual dashboard artifact (Step 7) |
| `today` | 🗓 Agenda (today) + 🎯 Now (overdue + today only, max 5) + 📥 Triage + Next action (morning standup view; no artifact) |
| `week` | 🗓 Agenda (today + week) + 🎯 Now (max 5) + Later counts + 📥 Triage + Next action (no artifact) |
| `overdue` | 🔴 Overdue only, **uncapped** - the strict "what's late" view (no Agenda, no artifact) |
| `all` | Full expansion: everything in the default view, plus every bucket as a full list (the audit view), artifact included |
| `<entity>` | **One project or area, uncapped**: its open work by bucket, its own health flags, Next action. No Vault state, Agenda, Ideas, Triage or artifact - those are vault-wide questions and this is not a vault-wide view (Step 1c) |

Sections with no content are omitted - no empty placeholders.

## Procedure

### Step 1: Get today's date

```bash
date +%Y-%m-%d
```

Use the Bash tool. **Do NOT substitute a cached date from memory or context** - the skill must reflect today's actual calendar date.

### Step 1b: Identify the vault type

- **Type B (read-only consumer vault)** - no `actions.md` anywhere **and** a `flip.ps1` or `render.ps1` at the vault root. Action tracking is absent by design, so the missing `actions.md` is **not** an error - never report it as one. Skip everything except 📥 Triage (Step 5b), titled `## 📥 Triage - loose files (N · run /para-triage)`, plus a one-line note that this is a read-only vault.
- **Type A (PARA vault with action tracking)** otherwise - the full flow.

Fold the detection into Step 2: only if the grep returns zero `actions.md` matches, Glob for `flip.ps1` / `render.ps1` to decide Type B vs. a genuinely empty Type A vault.

### Step 1c: Resolve an entity scope

Only when the argument is not one of the four scope words. Resolve it to exactly **one** `projects/<name>/` or `areas/<name>/` folder, then run the rest of the brief over that entity alone. **Never guess between candidates and never silently widen to the vault** - an unresolved name stops the run and asks. **Full procedure: [references/task-scan.md](references/task-scan.md).**

### Steps 2 to 4b: Scan, parse, bucket, aggregate

One tightly scoped Grep over action-bearing files, then heading association, marker parsing, bucketing against today, and per-entity aggregation. **Full procedure: [references/task-scan.md](references/task-scan.md).**

### Steps 4c to 4e: Health flags, ideas lane, Vision

Standing signals computed from the task scan, plus the ideas lane and the Vision read. All read-only. **Full procedure: [references/signals.md](references/signals.md).**

### Step 5: Rank and cap

Merge 🔴 + 🟠 + 🟡 into the **Now** candidates. Sort: overdue and due-today items before merely-upcoming ones (a blown or due date never drops out of the list below something that can still wait), then priority descending (🔺 to 🔼 to none to 🔽 to ⏬), then date ascending, then **Vision alignment** as the tiebreak - an item that visibly advances the Vision outranks one that doesn't, at equal priority and date. Vision never overrides a real deadline.

**Cap Now at five.** Five ranked beats ten unranked. Everything else becomes one-line **Later** counts (this week beyond the cap, next 30 days, later, recurring, waiting, undated). If overdue and due-today items alone exceed five, they take the whole list; add `*(run /para-daily-brief overdue for the full list)*`.

**The cap is a vault-wide device**: an entity scope is already the filter, so it renders every open item, by bucket ([references/output.md](references/output.md)).

### Steps 5b to 5c: Triage count and agenda

The triage count and the agenda. All read-only. **Full procedure: [references/signals.md](references/signals.md).**

### Step 6: Render output

Exact layout, line rules, and the single Next action close. **Full spec: [references/output.md](references/output.md).**

### Step 7: The visual dashboard

Default and `all` scopes only (never an entity scope), and **only when an Artifact tool is available in the harness** - if it is not, skip this step silently; the terminal output above is complete on its own.

Read [references/dashboard.md](references/dashboard.md) for the page spec, which owns the title, the favicon and the match rule that updates yesterday's page in place instead of forking it. Build the self-contained HTML from the data already collected (no new scanning), write it to the harness's scratchpad or temp directory - **never inside the vault**; it is a derived output and would sync - and publish it. Give the user the link on one line.

## Strict rules

- **Do NOT parse completed items (`- [x]`)** - they're history.
- **Do NOT rewrite any vault file.** No fixing missing markers, no inventing dates, no ticking, no grooming - undated is reported as undated. The health flags point at `/para-deep-clean`; this skill never applies them.
- **Do NOT follow links** into other files for extra context. The section heading is sufficient. (Exceptions: the root README's `## Vision`, and an idea brief's stage line.)
- **Do NOT add commentary or recommendations** beyond the Health flags and the single Next action. Decisions are the operator's.
- **Do NOT dedupe cross-referenced items** (same task in two files). Show both.
- **Meetings: today and future only, never invented.** Render only what the calendar or `meetings.md` line contains - never fabricate a meeting, time, or attendee. Calendars are read-only.
- **Do NOT include `**Status:**` lines** from actions files.
- **Do NOT resolve an ambiguous entity name by choosing one**, and never fall back to the whole vault when a name matches nothing. Both answer a question the operator did not ask, and the wrong-entity answer is indistinguishable from a right one at a glance. Ask.
- **An entity scope does not unlock the brief.** It narrows *which action files* are read; it does not relax the no-follow-links rule above. A status read that summarises `brief.md` is a different contract, not this argument.

## Edge cases

- **Vault with no actions.md files:** apply Step 1b. Type B gives the Triage-only output. Type A with empty or absent `triage/` gives `No actions.md files found in <cwd>.` and stops; with a populated triage, render only 📥 Triage.
- **Item with both future `🛫` AND `📅`:** Waiting (not actionable yet). **Past `🛫`:** ignore the gate, bucket by `D`, else Undated - a past `🛫` never hides a task.
- **Item with `⏳` but no `📅`:** the `⏳` date is `D`. Not Undated.
- **Recurring item without a date:** counts in Recurring; in `all`, show "next: -".
- **Malformed date** (`📅 2026-13-45`): treat as undated, note "(malformed date)".
- **Fewer than 5 Now candidates:** show what exists; never pad the list from Undated.
- **`resources/ideas/` missing or empty:** omit the Ideas lane.
- **Entity scope resolving to an entity with no open items:** say so in one line (`<entity> has no open actions.`) with its file link and last-modified date, and stop. An entity that is genuinely clear is a real answer, not an empty brief.
- **Entity scope naming an idea or an archived entity:** neither carries an `actions.md` by the vault's own rule, so report where it lives (`<name> is an idea; ideas hold no actions`) rather than an empty result.
- **Artifact publish fails** (no tool, no network): say so in one line and move on - the terminal brief already stands.
