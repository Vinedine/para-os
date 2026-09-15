# Everything in the brief that is not a task (Steps 4c to 5c)

The health flags, the ideas lane, the Vision read, the triage count and the agenda. All read-only: this file computes signals, it never repairs anything.

## Step 4c: Health flags

Standing signals, computed from what the task scan already holds. Emit each only when it fires:

- **Over-threshold file:** an action file with **more than 12 open items** (the actionable-frontier WIP threshold, per the vault's CLAUDE.md). Flag: `<scope>: N open - decomposed plan? Groom via /para-deep-clean`.
- **Stale file:** an action file with open items whose mtime is **60+ days ago**. Flag with the date.
- **Falsely-overdue candidates:** items overdue by **more than 30 days** (`📅` records a real-world deadline, so the date was likely never real). Flag the count and the worst offender.
- **Stale recurrence:** a `🔁` item whose `📅` is more than one full cadence period in the past. Flag the count and the worst: `<scope>:<line> - 🔁 every <cadence>, 📅 <date>, N periods behind`.
- **Undated majority:** when undated items exceed half of all open items, one line: `N of M open items are undated - the backlog is bigger than the brief can date. /para-deep-clean grooms.`
- **Misplaced checkboxes:** open checkboxes under `archive/` or `resources/`, from the scan's own count call. **Decode `resources/mds/` before counting** (SKILL.md Step 1b). **Skip any file carrying a frozen-record note** (a blockquote in its first 15 lines, before its first checkbox, saying the boxes are a point-in-time record, not live work). Flag only what is left, one line per bucket, naming the worst file: `N open checkboxes under archive/ (worst: <file>, N) - archive hygiene requires zero`.
- **Over-grown brief:** a `brief.md` under `projects/` or `areas/` past **500 lines**. One line per offender, worst first, capped at three: `<entity>/brief.md: N lines - content grooming via /para-deep-clean`. Count with one `wc -l` over the glob, never by reading the files; in a collected vault the glob is `resources/mds/*__brief.md` and `resources/mds/*__README.md`, reported under the **decoded** path.

Never fix any of these here - the read-only contract stands. `/para-deep-clean` owns the repair.

**Under an entity scope**, compute the five that are properties of one entity - over-threshold, stale file, stale recurrence, falsely-overdue, over-grown brief - against that entity alone, and skip the two vault-wide ones, misplaced checkboxes and undated majority. Steps 4d, 5b and 5c are skipped entirely; Step 4e still runs, for the Next action tiebreak.

## Step 4d: Ideas lane

If `resources/ideas/` exists, list its direct subfolders, then read each one's `brief.md` (collected: `resources/mds/resources__ideas__<name>__brief.md`, SKILL.md Step 1b).

**Date:** that `brief.md`'s, by the dating rule in [task-scan.md](task-scan.md#step-4b-aggregate-per-entity).

**Stage**, first rule that yields a line:

1. the first line opening on a stage label, bold, italic or plain (`**Stage:**`, `_Stage:_`, `Status:`), emphasis markers stripped;
2. under a `## Status` heading, when the first non-empty line starts with `|`, the section is a **table**: take the cell of the row whose first column is `Stage`, or the term the vault's brief shape file uses for it, case-insensitively. **Never the header row** - `| Detail | Value |` is a column label, not a stage;
3. otherwise that first non-empty line, trimmed to one line.

Base prescribes no such line, so an idea without one renders as name and date, which is normal. Where a shape file prescribes one, a miss renders identically to an absence: an idea whose stage says "Offer made, awaiting reply" must never render as one that says nothing.

Sort newest-touched first, then by name. Flag any idea untouched for **6+ months** as a retirement candidate (the vault's own lifecycle bar) - flag, never retire; retiring is always the operator's call.

## Step 4e: Read the Vision

Read the root `README.md`'s `## Vision` section (Grep with `-A` context is enough; do not read the whole file). It is the ranking tiebreak and it steers the closing next action. If the README or the section is missing, skip silently - never block the brief on it.

## Step 5b: Check the triage folder

Glob the **direct file children** of `triage/` (top-level only), with their [collected copies](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery). Do not parse contents. A `.pdf` and its `.md` are one line, linked to the `.pdf` where one exists. **`.gitkeep` is not an item.** No item means omit the section.

## Step 5c: Build the agenda

Two sources, merged and deduplicated by (date, title).

**1. Calendar connectors - the optional `## Agenda sources` block.** If the vault's CLAUDE.md has one, it is a table `| Source | Type | Endpoint | Relevant when |`, the same shape as `## Triage sources`. For each `connector:` row, read the calendar **read-only**:

- `connector: google-workspace`: `list_calendars` / `get_events` with the Endpoint as `user_google_email`, time-bounded to today through `T+30` (the Upcoming count needs the full window in every scope).
- Any other calendar connector: ToolSearch for the tool *suffix* (`list_events`, `search_events`, `get_events`); the `<server>` half of MCP tool names is not stable across clients. Only when that search comes back empty is the connector genuinely absent: skip the source and note it (`<source> declared but not connected - skipped`), never fail the run.
- **A source that answers with an error is not absent.** Carry on with the other sources and print one line under the agenda naming the source, what failed, and the remedy the error gives (an API to enable, a re-auth, a scope). Never let it read as "nothing scheduled".
- Apply the row's `Relevant when` filter, drop all-day "free" placeholders, and never write, accept, or decline anything.

**2. `meetings.md` - the manual fallback.** Grep the vault: `pattern`: `^- 🗓 `, `glob`: `{**/meetings.md,**/*__meetings.md}`, content mode, unlimited. Discard `archive/` paths, decoded. Parse `- 🗓 <date> [<time>] · <title> [· <field>...] [🔁 every <cadence>]`.

Bucket both sources against `T`: `🔁` to Recurring; `== T` to Today; `<= T+7` to This week; later to Upcoming (count only, expanded in `all`); past and not recurring is ignored. Sort by date then time. Omit the Agenda entirely if both sources are empty or absent.

**When Today and This week are both empty, expand Upcoming instead of counting it** (nearest five, then a count for the rest).
