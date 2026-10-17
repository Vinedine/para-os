# Everything in the brief that is not a task (Steps 4c to 5c)

## Step 4c: Health flags

Emit each only when it fires:

- **Over the cap:** `<scope>: N open, over the cap of 8 - close or demote before adding. /para-deep-clean grooms`.
- **Waiting too long:** the oldest `Waiting on` line, `<what> from <person>: N days - chase or drop?`, and how many more.
- **Stray checkboxes:** open checkboxes in a file under `projects/` or `areas/` that is neither an action file nor a contact file (a log, a plan, a meeting note). Flag the total and the worst file: no brief counts them.
- **Stale file:** an action file with open items, with the date it was last touched.
- **Falsely-overdue candidates:** the count and the worst offender.
- **Stale recurrence:** the count and the worst: `<scope>:<line> - 🔁 every <cadence>, 📅 <date>, N periods behind`.
- **Undated majority:** one line, `N of M open items are undated - the backlog is bigger than the brief can date. /para-deep-clean grooms.`
- **Misplaced checkboxes:** open checkboxes under `archive/` or `resources/`, and on contact cards where the vault's `areas/network/` checkbox row says `never`. One line per bucket, naming the worst file: `N open checkboxes under archive/ (worst: <file>, N) - archive hygiene requires zero`.
- **Nothing open:** a folder under `projects/` or `areas/` with no open item anywhere under it. One line each for the first three the scan lists: `<entity>: nothing open`
- **Over-grown brief:** one line per offender, `<file>: N lines - content grooming via /para-deep-clean`.
- **Silent source:** one line per source, `<source>: nothing since <date> (N days)`. A ledger that cannot be read is flagged, never passed ([para-shared/absent-is-not-zero.md](../../para-shared/absent-is-not-zero.md)).

## Step 4d: Ideas lane

The scan's `ideas`, newest-touched first: each idea's `name`, `touched` date and `stage` line, cut to its first sentence. An idea with no stage line renders as name and date. One marked `dormant` is a retirement candidate.

A **sentence end** is a `.`, `!` or `?` outside parentheses, at the line's end or followed by a space and anything but a lowercase letter or a digit: `€500.000`, `e.g. the call` and `art. 12` hold none.

## Step 4e: Read the Vision

On every run, for the Next action, read the root `README.md`'s `## Vision` section: Grep `-n` for the heading, then Read from that line to the next `## ` heading.

## Step 5b: Check the triage folder

The terminal brief lists the scan's `triage` by name only; `triage_preview`, each item's sender and subject, is the dashboard's. `unattended`, where set, goes beside the count in one clause.

## Step 5c: Build the agenda

Two sources, merged. Entries dedupe by (date, start time, normalised title), case and spacing ignored, or by a shared iCalUID; two entries at the same time with different titles both show. An entry with no time dedupes by (date, title).

**1. Calendar connectors - the optional `## Agenda sources` block**, the same table shape as `## Triage sources`: each `connector:` row read per [para-shared/connectors.md](../../para-shared/connectors.md#calendar). Drop all-day "free" placeholders, and convert every start into the vault's declared time zone before bucketing or printing it ([timestamps.md](../../para-shared/timestamps.md)). A source that answers with an error is not absent: carry on and print one line under the agenda naming the source, what failed, and the remedy the error gives.

**2. `meetings.md` - the manual fallback.** Grep the vault: `pattern`: `^- 🗓 `, `glob`: `**/meetings.md`, content mode, unlimited. Discard `archive/` paths. Parse `- 🗓 <date> [<time>] · <title> [· <field>...] [🔁 every <cadence>]`.

Bucket both sources against `T`: `🔁` to Recurring; `== T` to Today; `<= T+7` to This week; later to Upcoming (count only, expanded in `all`); past and not recurring is ignored. Sort by date then time. Omit the Agenda entirely if both sources are empty or absent.

**When Today and This week are both empty, expand Upcoming instead of counting it** (nearest five, then a count for the rest).
