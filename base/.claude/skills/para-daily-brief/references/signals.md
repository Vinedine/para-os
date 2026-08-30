# Everything in the brief that is not a task (Steps 4c to 5c)

The health flags, the ideas lane, the Vision read, the triage count and the agenda. All read-only: this file computes signals, it never repairs anything.

## Step 4c: Health flags

Standing signals, computed from what the task scan already holds. Emit each only when it fires:

- **Over-threshold file:** an action file with **more than 12 open items** (the actionable-frontier WIP threshold, per the vault's CLAUDE.md). Flag: `<scope>: N open - decomposed plan? Groom via /para-deep-clean`.
- **Stale file:** an action file with open items whose mtime is **60+ days ago**. Flag with the date.
- **Falsely-overdue candidates:** items overdue by **more than 30 days** (`📅` records a real-world deadline, never an aspiration - see `/para-deep-clean` Phase 3 for why this usually means the date was never real). Flag the count and the worst offender.
- **Undated majority:** when undated items exceed half of all open items, one line: `N of M open items are undated - the backlog is bigger than the brief can date. /para-deep-clean grooms.`
- **Misplaced checkboxes:** the count discarded from `resources/` and `archive/` during the scan, if nonzero.
- **Over-grown brief:** a `brief.md` under `projects/` or `areas/` past **500 lines** (the content-frontier rule's symptom - see `/para-deep-clean` Phase 3.5 for why). One line per offender, worst first, capped at three: `<entity>/brief.md: N lines - content grooming via /para-deep-clean`. Get the counts with one `wc -l` over the glob, not by reading the files - this flag must not turn a brief into a full-vault read.

Never fix any of these here - the read-only contract stands. `/para-deep-clean` owns the repair.

## Step 4d: Ideas lane

If `resources/ideas/` exists, list its direct subfolders with each folder's last-modified date (mtime of the folder's newest file; one `ls -lt` per folder is fine). For each idea, Grep its `brief.md` for the first `\*\*Stage:\*\*` line and show it when present. Sort newest-touched first. Flag any idea untouched for **6+ months** as a retirement candidate (the vault's own lifecycle bar) - flag, never retire; retiring is always the operator's call.

## Step 4e: Read the Vision

Read the root `README.md`'s `## Vision` section (Grep with `-A` context is enough; do not read the whole file). It is the ranking tiebreak and it steers the closing next action. If the README or the section is missing, skip silently - never block the brief on it.

## Step 5b: Check the triage folder

Glob `triage/`; if present, list its **direct file children** (top-level only). Do not parse contents. **`.gitkeep` is not an item**: it exists to hold the empty folder in git, so a `triage/` containing only that is empty and the section is omitted. Missing or empty means omit the section. In a Type B vault this section is the *entire* output.

## Step 5c: Build the agenda

Type A vaults only. Two sources, merged and deduplicated by (date, title).

**1. Calendar connectors - the optional `## Agenda sources` block.** If the vault's CLAUDE.md has one, it is a table `| Source | Type | Endpoint | Relevant when |`, the same shape as `## Triage sources`. For each `connector:` row, read the calendar **read-only**:

- `connector: google-workspace`: `list_calendars` / `get_events` with the Endpoint as `user_google_email`, time-bounded to today through `T+30` (the Upcoming count needs the full window in every scope).
- Any other calendar connector: ToolSearch for the tool *suffix* (`list_events`, `search_events`, `get_events`); the `<server>` half of MCP tool names is not stable across clients. Only when that search comes back empty is the connector genuinely absent: skip the source and note it (`<source> declared but not connected - skipped`), never fail the run.
- Apply the row's `Relevant when` filter, drop all-day "free" placeholders, and never write, accept, or decline anything.

**2. `meetings.md` - the manual fallback.** Grep the vault: `pattern`: `^- 🗓 `, `glob`: `**/meetings.md`, content mode, unlimited. Discard `archive/` paths. Parse `- 🗓 <date> [<time>] · <title> [· <field>...] [🔁 every <cadence>]`.

Bucket both sources against `T`: `🔁` to Recurring; `== T` to Today; `<= T+7` to This week; later to Upcoming (count only, expanded in `all`); past and not recurring is ignored. Sort by date then time. Omit the Agenda entirely if both sources are empty or absent.
