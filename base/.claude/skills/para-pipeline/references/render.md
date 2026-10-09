# Render the board (Step 4)

One block per lifecycle, in the order `CLAUDE.md` declares them, then the close. A section with nothing to show is left out, except the counts line and the metrics, which state a zero.

````
# Pipeline - <YYYY-MM-DD> - <vault name>

## <Lifecycle heading, without the word lifecycle> (N live)
```
<Stage> N · <Stage> N · <Stage> N · <Stage> N   (terminal this quarter: N)
```

### <Stage> (N)
1. <entity> · <N>d in stage · <next step text> · 📅 <date> (<N>d ago) - [<file>:<line>](<relative/path>#L<line>) · <Source header>
2. <entity> · ?d in stage · 🚩 no next step · <Source header>

## 🚩 Flags (N)
- <entity> - <what is wrong, and the one edit that fixes it>

## 📈 <Lifecycle> this quarter
- **Opened:** N · **Reached <promoting stage>:** N · **<Terminal stage>:** N
- **<Terminal stage> reasons:** <reason> N, <reason> N
- **Median days from Opened to <promoting stage>:** N (over N entities)

| Referrer | Entities | Reached <promoting stage> |
|---|---|---|
| <source> | N | N |

---
**Next action:** <exactly one concrete step>
````

**Line rules.** One line per entity, never wrapped: a long cell is cut after its first clause and ends in `…`. Stages in the table's order, terminal ones off the board; within a stage, most days in stage first. `?d` is a null `days_in_stage`, and `since_from: "opened"` reads `<N>d since opened`. The step links to its `next_step.file` and `line`; percent-encode every link target, never the text. A row home renders like a folder home, its register the link; a stage over fifteen rows shows the ten with the nearest dated step, then `(+N more in <register>)`.

## The flags

One line each, naming the entity and the edit that clears it, never what to decide about the entity itself:

- **`no_next_step`.**
- **`stale`**: no movement in 14 days, saying which `basis` it was measured by, last touch or days in stage.
- **`expiring`**: a dated fact in the Stage qualifier due within 14 days, its clause printed as written.
- **`signer_unknown`**: the `Signer` field reads `unknown`.
- **`home_mismatch`**, naming both paths; **`name_collision`**, each with its path; **`row_missing_columns`**, the row rendered with what it has.

Then one line naming the `empty_homes` once, and one closing line listing `no_stage` and `unknown_stage` by path. A lifecycle with nothing live says so in one line.

## The metrics

From `metrics`, for the `quarter` named in the heading. Where `year_end_unread` holds a year end, a line under the heading says the `**Locale:**` year end could not be read and the calendar's quarter stands in.

- **Opened**, **reached `promoting_stage`**, and each terminal stage's `this_quarter`, followed by its `reasons_this_quarter`; where the quarter holds none, its `all_time_reasons` on one line marked as all-time. A `missing_reason` entity is named, not counted.
- **The referrers table** from `referrers`, its `unrecorded` row included.
- **The median** from `median_days_opened_to_promoting`, with its `n`; a null `median` (fewer than three) prints `n` alone.
- **No `promoting_stage`**: say so once, and drop that count and the median.

## The close

One **Next action**: the most concrete step the board justifies, naming an entity, what to do and its file link. Prefer an `expiring` fact, then an overdue next step, then no next step, then any other; within each, the most advanced stage, then the longest since last touch (else in stage). A clean board closes on the review itself.
