# Scan the homes, resolve each entity (Steps 2 and 3)

`scripts/pipeline_scan.py` collects each lifecycle's entities from the union of its declared homes, a terminal home's for the metrics alone, and resolves each one's stage, dates, next step and flag inputs. What comes back:

| Field | Holds |
|---|---|
| `vault`, `today` | The resolved vault root, and the date every count is measured against |
| `lifecycles` | One entry per declared lifecycle (or the one `--lifecycle` matched) |
| `lifecycles[].heading`, `.noun`, `.stages` | The heading as written, its entity noun, and the declared stage names in table order |
| `lifecycles[].entities` | One record per resolved entity - see [What a record holds](#what-a-record-holds) |
| `lifecycles[].no_stage` | Paths of documents with no Stage line that still look like a filing gap |
| `lifecycles[].unknown_stage` | `{path, stage}` for each document whose Stage line names no declared stage but that still looks like a filing gap |
| `lifecycles[].empty_homes` | Declared homes that do not exist yet or hold nothing, each named once |
| `lifecycles[].counts_by_stage` | `{stage, count}` for every live, non-terminal stage, in table order |
| `lifecycles[].terminal_this_quarter` | Closed entities across every terminal stage whose Stage line dates them into the current quarter |
| `lifecycles[].metrics` | Everything [render.md](render.md)'s metrics section reads: the quarter's name and its first and last day (`quarter`, `quarter_start`, `quarter_end`, of the financial year the vault's `**Locale:**` line declares), `year_end_unread` where that line's year end could not be read, opened, reached-promoting, the median, the terminal-stage reasons and the referrers table |

## Step 3 - Resolve the next step

`next_step` is `{text, date, days, file, line, source}`, `source` naming where it was found:

1. `own_actions`: the entity's own `actions.md`.
2. `linked_checkbox`: an open checkbox whose first link is the entity's document, in any other `actions.md` under `projects/` or `areas/` (a revisit filed with an area).
3. `champion`: the next-actions heading of the contact file its `Champion` line links to.
4. `register_row`: the row's own next-step column, for an entity in a row home.

Nothing open in any of them is `no_next_step`, a flag rather than an error.

## What a record holds

Name, path (or register file and `line`), stage, `terminal` and `closed`/`live`, the header fields as read (`fields`), `opened`, `source`, the next step, and:

- **`name_from: "contact"`** where a register row's name cell read `unknown` and its Contact column stood in.
- **`duplicate_document`** where a folder holds both `brief.md` and `README.md`; the record is read from the `README.md`.
- **`days_in_stage`**, from the Stage line's `since`, null where unknown. A row at the first stage with no `since` takes its Opened column instead and carries `since_from: "opened"`.
- **`last_touch`**, from the `Last touch` header field or the register's column.
- **`dated_facts`**: any other date in the Stage qualifier, with its clause and `days_ahead`.
- **`home_mismatch`** where a folder entity's directory is not the home its stage declares, or a row entity's stage declares a folder home instead of the register it sits in, naming both.
- **`row_missing_columns`** for a register row narrower than its header.
- **The flag inputs** `no_next_step`, `stale`, `expiring`, `signer_unknown` and `name_collision`, computed and named, never worded; [render.md](render.md) words them.
