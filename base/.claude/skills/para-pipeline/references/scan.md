# Scan the homes, resolve each entity (Steps 2 and 3)

`scripts/pipeline_scan.py` returns:

| Field | Holds |
|---|---|
| `vault`, `today` | The vault root, and the date every count is measured against |
| `lifecycles` | One entry per declared lifecycle (or the one `--lifecycle` matched) |
| `lifecycles[].heading`, `.noun`, `.stages` | The heading as written, its entity noun, and the stage names in table order |
| `lifecycles[].entities` | One record per entity, [below](#what-a-record-holds) |
| `lifecycles[].no_stage`, `.unknown_stage` | Documents in a declared home that look like a filing gap: no Stage line, or one naming no declared stage (`{path, stage}`) |
| `lifecycles[].empty_homes` | Declared homes that do not exist yet or hold nothing |
| `lifecycles[].counts_by_stage` | `{stage, count}` per live, non-terminal stage, in table order |
| `lifecycles[].terminal_this_quarter` | Entities closed into any terminal stage this quarter |
| `lifecycles[].metrics` | `quarter`, `quarter_start`, `quarter_end`, `year_end_unread`, `opened`, `promoting_stage`, `reached_promoting`, `median_days_opened_to_promoting` (`n`, `median`), `terminal` (per stage: `this_quarter`, `reasons_this_quarter`, `all_time_reasons`, `missing_reason`) and `referrers` |

## What a record holds

`name`, `path` (with `line` for a register row), `stage`, `terminal`, `closed`, `live`, `fields` (the header as read), `opened`, `source`, and:

- **`next_step`**: `{text, date, days, file, line, source}`, null where nothing is open. `source` is where it was found: the entity's own `actions.md` (`own_actions`), an open checkbox in another `actions.md` whose first link is the entity (`linked_checkbox`), the next actions of the contact its `Champion` links (`champion`), or the register row's next-step column (`register_row`).
- **`days_in_stage`**, null without a `since`; `since_from: "opened"` where a first-stage row took its Opened column instead.
- **`last_touch`**, and **`dated_facts`**: any other date in the Stage qualifier, with its clause and `days_ahead`.
- **`name_from: "contact"`** where a row's name read `unknown` and its Contact column stood in; **`duplicate_document`** where a folder holds both `brief.md` and `README.md`, read from the `README.md`.
- **`home_mismatch`**, naming both paths, and **`row_missing_columns`**.
- **`flags`**: `no_next_step`, `stale` (`{basis, days}`), `expiring`, `signer_unknown` and `name_collision`, computed, never worded.
