# Scanning, parsing and bucketing tasks (Steps 1b to 4b)

Everything between "the vault is a folder of markdown" and "a set of bucketed, per-entity task records". Mechanical: no judgment lives here.

`scripts/brief_scan.py` does all of it. What comes back:

| Field | Holds |
|---|---|
| `today` | The date the brief is dated by |
| `entity` | `status` of `resolved`, `ambiguous`, `elsewhere` or `unresolved`, with `match`, `candidates`, `elsewhere` and `nearest` (Step 1b) |
| `tasks` | One record per open item: file, line, bucket, scope, section, text, markers, `lane`, `days`, `also_lane`, `malformed_date` |
| `entities`, `totals` | Per-entity rows with the three counts that partition the open count and a `bar` width, and the same four numbers vault-wide |
| `lanes` | Each lane's `(file, line)` references, joined back into `tasks` for the counts a rendered section needs; a recurring item overdue or due today is in `recurring` and that lane too, tagged `🔁` there |
| `mentioned_elsewhere` | Under an entity scope only: open items naming it that live in another file; render five, then a `(+N more)` line |
| `file_dates` | Each action file's last-touched date |
| `flags`, `ideas`, `triage`, `triage_preview`, `lifecycles` | Everything [signals.md](signals.md) computes from files |
| `review` | Under `--review` only: `window` (`start`, `end`, `days`), `done` (`count`, `undated`, `by_entity` rows of `items`), `slipped`, `moved` (one entry per lifecycle: `count`, `entities`), `stuck` (`overdue` references, `no_next_step` entities) and `decisions`; null for an entity name that did not resolve |
