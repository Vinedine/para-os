# Scan the homes, resolve each entity (Steps 2 and 3)

`scripts/pipeline_scan.py` implements every rule below. What comes back:

| Field | Holds |
|---|---|
| `vault`, `today` | The resolved vault root, and the date every count is measured against |
| `lifecycles` | One entry per declared lifecycle (or the one `--lifecycle` matched) |
| `lifecycles[].heading`, `.noun`, `.stages` | The heading as written, its entity noun, and the declared stage names in table order |
| `lifecycles[].entities` | One record per resolved entity - see the field table below |
| `lifecycles[].no_stage` | Paths of documents with no Stage line that still look like a filing gap - see Step 2 |
| `lifecycles[].unknown_stage` | `{path, stage}` for each document whose Stage line names no declared stage but that still looks like a filing gap - see Step 2 |
| `lifecycles[].empty_homes` | Declared homes that do not exist yet or hold nothing, each named once |
| `lifecycles[].counts_by_stage` | `{stage, count}` for every live, non-terminal stage, in table order |
| `lifecycles[].terminal_this_quarter` | Closed entities across every terminal stage whose Stage line dates them into the current quarter |
| `lifecycles[].metrics` | Everything [render.md](render.md)'s metrics section reads: the quarter's name, opened, reached-promoting, the median, the terminal-stage reasons and the referrers table |

Where the script cannot run, apply the rest of this file by hand.

## Step 2 - Collect the entities

For each lifecycle, glob the union of its `PARA home` cells, with the `<...>` placeholder
standing for one path segment.

- **A folder home** yields the `brief.md` or `README.md` at its root, whichever is there. A
  folder holding both is one entity, read from the `README.md`, and the duplicate is a flag.
- **A row home** yields one record per row of the register's table, the header row excluded,
  with the row's `##` section kept so a closed section can be excluded from the live board.
  **A row whose name column reads `unknown` takes its Contact column instead** (the second
  column where the table has no Contact column), and the record carries `name_from:
  "contact"`; the collision check below skips every name recovered this way. Either name
  is reduced to its label: a link to its text, then a trailing parenthetical dropped, so
  `Jan Janssen (via a partner)` reads as `Jan Janssen`.
- **A terminal home** is globbed like any other. Its entities are collected and marked
  closed, for the metrics alone.

Read the Stage line and the header of every entity collected, per
[para-shared/lifecycles.md](../../para-shared/lifecycles.md). A Stage line whose name matches
none of the lifecycle's declared stages is reported with the name read (`unknown_stage`)
under the same test as a missing one, below, and skipped silently otherwise.

**A document in a declared home with no Stage line at all** is reported by path (`no_stage`)
only when it carries one of the header fields a staged entity would (`Opened`, `Source`,
`Champion`, `Signer`, `Value`, `Last touch`, `Won`), or when no ordinary project, area or
idea can occupy its home: any home but `projects/`, `areas/`, `resources/ideas/`,
`archive/projects/` or `archive/ideas/` followed directly by the `<placeholder>`. Otherwise it
is skipped silently.

**A row whose Stage cell names a stage declared with a folder home** is a `home_mismatch`
too, naming that stage's own home and the register the row was found in. A closed row
never is.

**Header fields are whatever the entity's rule file declares**, read as bold-led lines under
the title (`**Opened:** <date>`, `**Source:** <text>`, `**Champion:** [<contact>](<path>)`).
Read them as text. The only ones this skill computes with are the dates, the champion link,
and the one field [render.md](render.md) names by name.

## Step 3 - Resolve the next step

One next step per entity, taken from the first of these that produces an open checkbox:

1. **The entity's own `actions.md`**, where its bucket allows one: the earliest-dated open
   `- [ ]`, undated ones after every dated one.
2. **An open checkbox whose first link is the entity's document**, in any other `actions.md`
   under `projects/` or `areas/` (a revisit filed with an area), chosen the same way: resolve
   the link relative to the file that holds it and compare real paths.
3. **The contact file its `Champion` line links to**: every open item under that file's
   next-actions heading, earliest dated first, never one filed under any other heading in
   the same file. Follow the link as written; a champion line with no
   link, or a link resolving to nothing, is the no-next-step case rather than a name to
   search for.
4. **The row's own next-step column**, for an entity in a row home. Its date is the one the
   wording attaches to the step, ranked: a `📅` marker, then `by` before it, then `on`, then
   the date closing the cell. A date elsewhere in the prose is not the due date. An undated step still
   counts; `None planned`, `-` and an empty cell do not.

An entity that reaches the end of that list with nothing open **has no next step**, which is
a flag rather than an error. Never compose one from the brief's prose, and never present a
closed item as the next step.

**Skip what sits inside a fenced code block** while scanning for checkboxes, per
[para-shared/operating-discipline.md](../../para-shared/operating-discipline.md).

## The dates each record carries

- **Days in stage**, from `since <date>` in the Stage qualifier, against today. No `since`
  means unknown, rendered as `?` and never substituted from a file's modification time -
  except a row at the lifecycle's **first** stage with no `since`: its Opened column stands
  in, and the record carries `since_from: "opened"` so the skill can say which one it used.
- **Days since last touch**, from the header field the rule file names for it (`**Last
  touch:** <date>, <what happened>`) or the register's equivalent column. Absent, the
  staleness flag falls back to days in stage and the record says which of the two it used.
- **Opened**, from the header field of that name. It feeds the metrics only.
- **A dated fact in the Stage qualifier**, any date there other than the `since` one, kept
  with the clause around it and its days ahead, so the flag can print it while it is still
  ahead.

## What a record holds

Name (and `name_from` where it came from the Contact fallback), path (or register file and
line), stage, `terminal` and `closed`/`live`, `duplicate_document`, days in stage and
`since_from`, the dated facts, the header fields as read, last touch, opened, source,
`home_mismatch` where a folder entity's directory is not the home its stage declares, or a
row entity's stage declares a folder home instead of the register it sits in (naming both),
`row_missing_columns` for a register row narrower than its header, the next step, and
the flag inputs `no_next_step`, `stale`, `expiring`, `signer_unknown` and `name_collision` -
computed and named, never worded; [render.md](render.md) words them.
