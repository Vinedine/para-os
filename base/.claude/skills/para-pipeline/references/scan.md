# Scan the homes, resolve each entity (Steps 2 and 3)

`scripts/pipeline_scan.py` returns:

| Field | Holds |
|---|---|
| `vault`, `today` | The vault root, and the date every count is measured against |
| `lifecycles` | One entry per declared lifecycle (or the one `--lifecycle` matched) |
| `lifecycles[].heading`, `.stages` | The heading as written, and the stage names in table order |
| `lifecycles[].entities` | One record per entity, [below](#what-a-record-holds) |
| `lifecycles[].no_stage`, `.unknown_stage` | Documents in a declared home that look like a filing gap: no Stage line, or one naming no declared stage (`{path, stage}`) |
| `lifecycles[].empty_homes` | Declared homes that do not exist yet or hold nothing |
| `lifecycles[].counts_by_stage` | `{stage, count, total}` per live, non-terminal stage, in table order, `total` summing the vault's currency only, null where no entity there has a value |
| `lifecycles[].by_value` | `{currency, ranked, unknown}`: the live folder entities with a value, the vault's currency largest first, then each other currency's; then the names with none. Null where no folder entity carries a `Value` line |
| `lifecycles[].revisits_due` | Won entities archived out of the promoting home, six months past their `Last touch` (else `Won`) with no dated next step and no `Revisit: none` line, one per client, longest first: `{name, path, value, basis, days}` |
| `lifecycles[].metrics` | `quarter`, `year_end_unread`, `opened`, `promoting_stage`, `reached_promoting`, `median_days_opened_to_promoting` (`n`, `median`), `terminal` (per stage: `this_quarter`, `reasons_this_quarter`, `all_time_reasons`, `missing_reason`) and `referrers` |

## What a record holds

`name`, `path` (with `line` for a register row), `stage`, `terminal`, `live`, `fields` (the header as read), `opened`, `source`, `last_touch`, and:

- **`next_step`**: `{text, date, days, file, line}`, null where nothing is open.
- **`days_in_stage`**, null without a `since`; `since_from: "opened"` where a first-stage row took its Opened column instead.
- **`value`**, a folder entity's `{amount, currency}`: the amount its `Value` line opens on, read by the `**Locale:**` line, null where the line opens on none. A register row has no `value`.
- **`name_from: "contact"`** where a row's name read `unknown` and its Contact column stood in.
- **`home_mismatch`**, naming both paths, and **`row_missing_columns`**.
- **`flags`**: `no_next_step`, `stale` (`{basis, days}`), `expiring`, `signer_unknown` and `name_collision`, computed.
