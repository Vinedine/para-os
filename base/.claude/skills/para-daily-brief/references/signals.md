# Everything in the brief that is not a task (Steps 4c to 5c)

The health flags, the ideas lane, the Vision read, the triage count and the agenda. All read-only: this file computes signals, it never repairs anything.

## Step 4c: Health flags

Standing signals, computed from what the task scan already holds. Emit each only when it fires:

- **Over-threshold file:** an action file with **more than 12 open items** (the actionable-frontier WIP threshold, per the vault's CLAUDE.md). Flag: `<scope>: N open - decomposed plan? Groom via /para-deep-clean`.
- **Stale file:** an action file with open items whose mtime is **60+ days ago**. Flag with the date.
- **Falsely-overdue candidates:** items overdue by **more than 30 days** (`📅` records a real-world deadline, never an aspiration - see `/para-deep-clean` Phase 3 for why this usually means the date was never real). Flag the count and the worst offender.
- **Stale recurrence:** a `🔁` item whose `📅` is more than one full cadence period in the past. Recurring outranks every date bucket, so no other flag reaches these. Flag the count and the worst: `<scope>:<line> - 🔁 every <cadence>, 📅 <date>, N periods behind`.
- **Undated majority:** when undated items exceed half of all open items, one line: `N of M open items are undated - the backlog is bigger than the brief can date. /para-deep-clean grooms.`
- **Misplaced checkboxes:** open checkboxes under `archive/` or `resources/`, from the scan's own count call. **Decode `resources/mds/` before counting** (SKILL.md Step 1b): in a collected vault it holds every `.md` in the vault, so counting it raw reports the entire backlog as misplaced. **Skip any file whose opening lines carry a frozen-record note** (a blockquote saying the boxes are a point-in-time record, not live work): that is the archive-hygiene rule's "softened to an explicit note" escape, already taken, and a whole archived meeting series is normally covered by it. Flag only what is left, one line per bucket, naming the worst file: `N open checkboxes under archive/ (worst: <file>, N) - archive hygiene requires zero`.
- **Over-grown brief:** a `brief.md` under `projects/` or `areas/` past **500 lines** (the content-frontier rule's symptom - see `/para-deep-clean` Phase 3.5 for why). One line per offender, worst first, capped at three: `<entity>/brief.md: N lines - content grooming via /para-deep-clean`. Get the counts with one `wc -l` over the glob, not by reading the files - this flag must not turn a brief into a full-vault read. In a collected vault the glob is `resources/mds/*__brief.md` and `resources/mds/*__README.md`; report each offender under its **decoded** vault path, never the encoded filename. This is the one flag a Type B vault computes.

Never fix any of these here - the read-only contract stands. `/para-deep-clean` owns the repair.

**Under an entity scope**, compute the five that are properties of one entity - over-threshold, stale file, stale recurrence, falsely-overdue, over-grown brief - against that entity alone, and skip the two that are statements about the whole vault: misplaced checkboxes (its own count runs over `archive/` and `resources/`, outside any entity) and undated majority (a ratio that means nothing over a single file). Steps 4d, 5b and 5c are skipped entirely; Step 4e still runs, because the Vision remains the tiebreak behind the closing next action.

## Step 4d: Ideas lane

If `resources/ideas/` exists, list its direct subfolders, then for each one read its `brief.md` - **through the flip map when the vault is collected** (SKILL.md Step 1b: `resources/mds/resources__ideas__<name>__brief.md`). In a collected vault no idea folder holds a `brief.md` at all, only a `brief.pdf`, so a grep at the PARA path misses every idea.

**Date:** the mtime of that `brief.md`, not of the folder and never of a `.pdf` - a folder full of rendered PDFs carries the last render date, which makes every idea look touched today.

**Stage**, first rule that yields a line:

1. the first bold status label (`**Stage:**` or `**Status:**`);
2. under a `## Status` heading, when the first non-empty line starts with `|`, the section is a **table**: take the cell of the row whose first column is `Stage` or `Fase`, case-insensitively. **Never the header row** - `| Detail | Value |` is a column label, not a stage, and a property vault's `## Status` is a table every time, so this is the normal path and not the exception;
3. otherwise that first non-empty line, trimmed to one line.

The template prescribes no such line, so an idea without one renders as name and date, which is normal and never a finding - which is also why rules 1 to 3 must actually work. A silent miss is indistinguishable from a genuine absence, so an idea whose stage says "Bod-klaar, bod €500.000" renders identically to one that says nothing.

Sort newest-touched first. Flag any idea untouched for **6+ months** as a retirement candidate (the vault's own lifecycle bar) - flag, never retire; retiring is always the operator's call.

## Step 4e: Read the Vision

Read the root `README.md`'s `## Vision` section (Grep with `-A` context is enough; do not read the whole file). It is the ranking tiebreak and it steers the closing next action. If the README or the section is missing, skip silently - never block the brief on it.

## Step 5b: Check the triage folder

Glob `triage/`; if present, list its **direct file children** (top-level only). Do not parse contents. **`.gitkeep` is not an item**: it exists to hold the empty folder in git, so a `triage/` containing only that is empty and the section is omitted. Missing or empty means omit the section.

In a Type B vault the items are `.pdf` - the flip pipeline's rendered siblings - and that is what to link, since it is what the reader can open. Do not also list the `resources/mds/triage__*.md` source as a second item; one triage item is one line.

## Step 5c: Build the agenda

Both vault types - neither source is an action file, so a Type B vault gets its agenda like any other. Two sources, merged and deduplicated by (date, title).

**1. Calendar connectors - the optional `## Agenda sources` block.** If the vault's CLAUDE.md has one, it is a table `| Source | Type | Endpoint | Relevant when |`, the same shape as `## Triage sources`. For each `connector:` row, read the calendar **read-only**:

- `connector: google-workspace`: `list_calendars` / `get_events` with the Endpoint as `user_google_email`, time-bounded to today through `T+30` (the Upcoming count needs the full window in every scope).
- Any other calendar connector: ToolSearch for the tool *suffix* (`list_events`, `search_events`, `get_events`); the `<server>` half of MCP tool names is not stable across clients. Only when that search comes back empty is the connector genuinely absent: skip the source and note it (`<source> declared but not connected - skipped`), never fail the run.
- **A source that answers with an error is a third case, and the loudest.** Absent means nothing was promised; erroring means the vault declared a calendar, the tool exists, and the call failed - so the agenda is silently short rather than empty, which is the one state a reader cannot detect. Carry on with the other sources and print one line under the agenda naming the source, what failed, and the remedy the error gives (an API to enable, a re-auth, a scope). Never let it read as "nothing scheduled".
- Apply the row's `Relevant when` filter, drop all-day "free" placeholders, and never write, accept, or decline anything.

**2. `meetings.md` - the manual fallback.** Grep the vault: `pattern`: `^- 🗓 `, `glob`: `{**/meetings.md,**/*__meetings.md}`, content mode, unlimited - the second alternate catches a collected vault, where `flip.ps1` may have encoded the file into `resources/mds/`. Discard `archive/` paths, decoded. Parse `- 🗓 <date> [<time>] · <title> [· <field>...] [🔁 every <cadence>]`.

Bucket both sources against `T`: `🔁` to Recurring; `== T` to Today; `<= T+7` to This week; later to Upcoming (count only, expanded in `all`); past and not recurring is ignored. Sort by date then time. Omit the Agenda entirely if both sources are empty or absent.

**When Today and This week are both empty, expand Upcoming instead of counting it** (nearest five, then a count for the rest). A section whose entire content is a number tells the reader less than no section at all, and a quiet fortnight is exactly when what comes after it is worth seeing.
