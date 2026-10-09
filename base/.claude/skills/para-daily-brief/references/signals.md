# Everything in the brief that is not a task (Steps 4c to 5c)

## Step 4c: Health flags

Emit each only when it fires:

- **Over the cap:** an action file holding **more than 8 open items**. Flag: `<scope>: N open, over the cap of 8 - close or demote before adding. /para-deep-clean grooms`.
- **Long headline:** an open item whose headline (its bold lead, or the whole line without one) reaches **120 characters**. Flag the count and the worst: `N actions of 120+ characters - worst: <scope>:<line>, N`.
- **Waiting too long:** a `Waiting on` line whose `since` date is **14 or more days** ago. Flag the oldest, `<what> from <person>: N days - chase or drop?`, and how many more.
- **Stray checkboxes:** open checkboxes in a file under `projects/` or `areas/` that is neither an action file nor a contact file (a log, a plan, a meeting note). Flag the total and the worst file: no brief counts them.
- **Stale file:** an action file with open items last touched **60+ days ago**. Flag with the date.
- **Falsely-overdue candidates:** items overdue by **more than 30 days**. Flag the count and the worst offender.
- **Stale recurrence:** a `🔁` item whose `📅` is more than one full cadence period in the past. Flag the count and the worst: `<scope>:<line> - 🔁 every <cadence>, 📅 <date>, N periods behind`.
- **Undated majority:** when undated items exceed half of all open items and there are **8 or more** open items, one line: `N of M open items are undated - the backlog is bigger than the brief can date. /para-deep-clean grooms.`
- **Misplaced checkboxes:** open checkboxes under `archive/` or `resources/`, and on contact cards where the vault's `areas/network/` checkbox row says `never`. One line per bucket, naming the worst file: `N open checkboxes under archive/ (worst: <file>, N) - archive hygiene requires zero`.
- **Nothing open:** a folder under `projects/` or `areas/` with no open item anywhere under it. One line each for the first three the scan lists: `<entity>: nothing open - finished (archive) or stalled (next step)?`
- **Over-grown brief:** an entity's brief past **500 lines**. One line per offender: `<file>: N lines - content grooming via /para-deep-clean`.
- **Silent source:** a `## Triage sources` row carrying a cadence hint (`🔁 every <period>`) whose newest delivery to this vault is more than one period old. One line per source: `<source>: nothing since <date> (N days)`. A ledger that cannot be read is flagged, never passed ([para-shared/absent-is-not-zero.md](../../para-shared/absent-is-not-zero.md)).

## Step 4d: Ideas lane

The scan's `ideas`, newest-touched first: each idea's `name`, `touched` date and `stage` line, cut to its first sentence. An idea with no stage line renders as name and date. One marked `dormant`, untouched for 6+ months, is a retirement candidate.

A **sentence end** is a `.`, `!` or `?` outside parentheses, at the line's end or followed by a space and anything but a lowercase letter or a digit: `€500.000`, `e.g. the call` and `art. 12` hold none.

## Step 4e: Read the Vision

On every run, for the Next action, read the root `README.md`'s `## Vision` section: Grep `-n` for the heading, then Read from that line to the next `## ` heading. If the README or the section is missing, skip silently.

## Step 5b: Check the triage folder

The terminal brief lists the scan's `triage` by name only; `triage_preview`, each item's sender, subject and first lines, is the dashboard's.

## Step 5c: Build the agenda

Two sources, merged. Entries from different sources dedupe by (date, start time), keeping the longer title; within one source only by (date, start time, title). An entry with no time dedupes by (date, title).

**1. Calendar connectors - the optional `## Agenda sources` block.** If the vault's CLAUDE.md has one, it is a table `| Source | Type | Endpoint | Relevant when |`, the same shape as `## Triage sources`. For each `connector:` row, read the calendar **read-only**:

- `connector: google-workspace`: `list_calendars` / `get_events` with the Endpoint as `user_google_email`, time-bounded to today through `T+30` in every scope.
- Any other calendar connector: ToolSearch for the tool *suffix* (`list_events`, `search_events`, `get_events`). Only when that search comes back empty is the connector absent: skip the source and note it (`<source> declared but not connected - skipped`).
- **A source that answers with an error is not absent.** Carry on with the other sources and print one line under the agenda naming the source, what failed, and the remedy the error gives.
- Apply the row's `Relevant when` filter, drop all-day "free" placeholders, and never write, accept, or decline anything.
- Convert every start into the vault's declared time zone before bucketing or printing it, per [para-shared/timestamps.md](../../para-shared/timestamps.md).

**2. `meetings.md` - the manual fallback.** Grep the vault: `pattern`: `^- 🗓 `, `glob`: `**/meetings.md`, content mode, unlimited. Discard `archive/` paths. Parse `- 🗓 <date> [<time>] · <title> [· <field>...] [🔁 every <cadence>]`.

Bucket both sources against `T`: `🔁` to Recurring; `== T` to Today; `<= T+7` to This week; later to Upcoming (count only, expanded in `all`); past and not recurring is ignored. Sort by date then time. Omit the Agenda entirely if both sources are empty or absent.

**When Today and This week are both empty, expand Upcoming instead of counting it** (nearest five, then a count for the rest).
