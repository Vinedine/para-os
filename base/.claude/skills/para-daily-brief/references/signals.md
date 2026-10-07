# Everything in the brief that is not a task (Steps 4c to 5c)

**What the scan already did.** `scripts/brief_scan.py` ([task-scan.md](task-scan.md)) returns the health flags in `flags`, the ideas lane in `ideas`, the triage items in `triage` and the lifecycle counts in `lifecycles`. Steps 4c, 4d, 4f and 5b below are its specification and the fallback for a hand-run scan. Steps 4e and 5c are not the script's and run here on every brief.

## Step 4c: Health flags

Emit each only when it fires:

- **Over the cap:** an action file holding **more than 8 open items**. Flag: `<scope>: N open, over the cap of 8 - close or demote before adding. /para-deep-clean grooms`.
- **Long headline:** an open item whose headline (its bold lead, or the whole line without one) runs **past 120 characters**. Flag the count and the worst: `N actions over 120 characters - worst: <scope>:<line>, N`.
- **Waiting too long:** a `Waiting on` line whose `since` date is **14 or more days** ago. Flag the oldest, `<what> from <person>: N days - chase or drop?`, and how many more. A wait never counts toward a file's cap.
- **Stray checkboxes:** open checkboxes in a file under `projects/` or `areas/` that is neither an action file nor a contact file (a log, a plan, a meeting note), frozen records skipped. Flag the total and the worst file: no brief counts them.
- **Stale file:** an action file with open items whose date, by [Step 4b](task-scan.md#step-4b-aggregate-per-entity)'s rule, is **60+ days ago**. Flag with the date. Without a shell no date can be read: say the flag was not computed.
- **Falsely-overdue candidates:** items overdue by **more than 30 days**. Flag the count and the worst offender.
- **Stale recurrence:** a `🔁` item whose `📅` is more than one full cadence period in the past. Flag the count and the worst: `<scope>:<line> - 🔁 every <cadence>, 📅 <date>, N periods behind`.
- **Undated majority:** when undated items exceed half of all open items and there are **8 or more** open items, one line: `N of M open items are undated - the backlog is bigger than the brief can date. /para-deep-clean grooms.`
- **Misplaced checkboxes:** open checkboxes under `archive/` or `resources/`, and on contact cards where the vault's `areas/network/` checkbox row says `never`, from the scan's own count call. **Skip any file carrying a frozen-record note** (a blockquote in its first 15 lines, before its first checkbox, saying the boxes are a point-in-time record, not live work). Flag only what is left, one line per bucket, naming the worst file: `N open checkboxes under archive/ (worst: <file>, N) - archive hygiene requires zero`.
- **Nothing open:** a folder under `projects/` or `areas/`, never `areas/network/`, with no open item anywhere under it, a `🔁` counting as open. One line each, capped at three, those with no `actions.md` first, then the oldest: `<entity>: nothing open - finished (archive) or stalled (next step)?` By hand: the folders Step 4b gave no row.
- **Over-grown brief:** a `brief.md` under `projects/` or `areas/` past **500 lines**. One line per offender, worst first, capped at three: `<entity>/brief.md: N lines - content grooming via /para-deep-clean`. Count with one `wc -l` over the glob, never by reading the files; without a shell, Read each at offset 500 with limit 1, and a line there puts it past the cap.
- **Silent source:** a `## Triage sources` row carrying a cadence hint (`🔁 every <period>`) whose newest delivery to this vault, by the source's own ledger on this machine, is more than one period old. One line per source: `<source>: nothing since <date> (N days)`. A ledger that cannot be read is flagged, never passed ([para-shared/absent-is-not-zero.md](../../para-shared/absent-is-not-zero.md)); a row with no hint, or a source with no ledger here, is not checked. Which ledger each source keeps: `delivered` in `scripts/brief_scan.py`. Skipped under an entity scope; without a shell, say it was not computed.

**Under an entity scope**, compute the flags against that entity alone and skip misplaced checkboxes, undated majority and nothing open. Steps 4d, 5b and 5c are skipped entirely; Step 4e still runs, for the Next action tiebreak.

## Step 4d: Ideas lane

If `resources/ideas/` exists, list its direct subfolders, then read each one's `brief.md`.

**Date:** that `brief.md`'s, by the dating rule in [task-scan.md](task-scan.md#step-4b-aggregate-per-entity).

**Stage**, first rule that yields a line:

1. the first line opening on a stage label, bold, italic or plain (`**Stage:**`, `_Stage:_`, `Status:`), label and emphasis markers stripped;
2. under a `## Status` heading, when the first non-empty line starts with `|`, the section is a **table**: take the cell of the row whose first column is `Stage`, or the term the vault's brief shape file uses for it, case-insensitively. **Never the header row** - `| Detail | Value |` is a column label, not a stage;
3. otherwise that first non-empty line, trimmed to one line.

Then cut the line: link syntax reduced to its label and `_x_` / `*x*` emphasis to its text, then everything from the first sentence end dropped. A sentence end is a `.`, `!` or `?` outside parentheses, at the line's end or followed by a space and anything but a lowercase letter or a digit: `€500.000`, `e.g. the call` and `art. 12` hold none.

An idea with no stage line renders as name and date.

**For the dashboard**, the scan adds `days_in_stage` from the stage line's `(since <date>)`, `revisit` (the sentence holding the brief's "revisit when", cut like the stage line), and `actions`: the open items elsewhere that name the idea, by the scan's mention rule. By hand, skip them.

Sort newest-touched first, then by name. Flag any idea untouched for **6+ months** as a retirement candidate; never retire it.

## Step 4e: Read the Vision

Read the root `README.md`'s `## Vision` section: Grep `-n` for the heading, then Read from that line to the next `## ` heading. If the README or the section is missing, skip silently.

## Step 4f: Lifecycle counts

The scan's `lifecycles` field, one entry per declared lifecycle with its heading and the live count at each non-terminal stage. **One line per lifecycle, in 📊 Vault state, and nothing else**: the board is `/para-pipeline`'s.

A declared lifecycle with no live entity renders its zeros.

## Step 5b: Check the triage folder

Glob the **direct file children** of `triage/` (top-level only). **`.gitkeep` is not an item.** The terminal brief lists names only; the scan's `triage_preview` reads each item's head for the dashboard alone: an `.eml`'s sender, subject and plain-text body, a note's `From:` field, H1 and first prose paragraph, a PDF through its markdown twin, nothing from any other format. By hand, skip the preview. No item means omit the section.

## Step 5c: Build the agenda

Two sources, merged. Entries from different sources dedupe by (date, start time), keeping the longer title; within one source only by (date, start time, title). An entry with no time dedupes by (date, title).

**1. Calendar connectors - the optional `## Agenda sources` block.** If the vault's CLAUDE.md has one, it is a table `| Source | Type | Endpoint | Relevant when |`, the same shape as `## Triage sources`. For each `connector:` row, read the calendar **read-only**:

- `connector: google-workspace`: `list_calendars` / `get_events` with the Endpoint as `user_google_email`, time-bounded to today through `T+30` in every scope.
- Any other calendar connector: ToolSearch for the tool *suffix* (`list_events`, `search_events`, `get_events`), never a full tool name. Only when that search comes back empty is the connector absent: skip the source and note it (`<source> declared but not connected - skipped`).
- **A source that answers with an error is not absent.** Carry on with the other sources and print one line under the agenda naming the source, what failed, and the remedy the error gives.
- Apply the row's `Relevant when` filter, drop all-day "free" placeholders, and never write, accept, or decline anything.
- Convert every start into the vault's declared time zone before bucketing or printing it, per [para-shared/timestamps.md](../../para-shared/timestamps.md).

**2. `meetings.md` - the manual fallback.** Grep the vault: `pattern`: `^- 🗓 `, `glob`: `{**/meetings.md,**/*__meetings.md}`, content mode, unlimited. Discard `archive/` paths, decoded. Parse `- 🗓 <date> [<time>] · <title> [· <field>...] [🔁 every <cadence>]`.

Bucket both sources against `T`: `🔁` to Recurring; `== T` to Today; `<= T+7` to This week; later to Upcoming (count only, expanded in `all`); past and not recurring is ignored. Sort by date then time. Omit the Agenda entirely if both sources are empty or absent.

**When Today and This week are both empty, expand Upcoming instead of counting it** (nearest five, then a count for the rest).
