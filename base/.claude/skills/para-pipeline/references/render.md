# Render the board (Step 4)

Exact terminal layout. One block per lifecycle, in the order the sections appear in `CLAUDE.md`, then the close. Sections with no content are omitted, except the counts line and the metrics, which state a zero rather than disappearing.

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

**Line rules.** One line per entity, no wraps. Stages render in the lifecycle table's own order, terminal stages excluded from the board. Within a stage, order by days in stage descending. `?d` is an unknown time in stage, never a zero. The next-step link points at the file the step actually lives in (the entity's `actions.md`, the champion's contact file, the register). **Percent-encode every link target**, never the link text.

**A row home renders like any other stage**, with the register file as the link target and the row's own next-step column as the step. Where a stage holds more than fifteen rows, render the ten with the nearest dated next step, then one `(+N more in <register>)` line.

## The flags

One line each, under the board, naming the entity and the edit that clears it. Four of them, and no others:

- **No next step.** None of the sources in [scan.md](scan.md) Step 3 holds an open item.
- **No movement in 14 days**, by last touch where the entity carries one, else by days in stage - already computed as the entity's `stale` flag, `{basis, days}`. Say which of the two `basis` names. Not raised while the next step carries a date that is still ahead; an undated next step, or none at all, never suppresses it.
- **A dated fact in the Stage qualifier expiring within 14 days** (a proposal's validity, an option, a quote). Print the clause as written.
- **An unknown decision-maker.** Where the entity's header carries a `Signer` field whose value reads `unknown`, flag it from the **second** stage on. A lifecycle whose rule file declares no such field never fires it.

A flag is an observation, not an instruction: it says what the file lacks, never what the operator should decide about the entity itself.

## The metrics

Per lifecycle, computed from the records already collected, this quarter only (the calendar quarter containing today's date, named in the heading):

- **Opened this quarter**, from the `Opened` header field. A closed register row whose name matches a folder entity is counted from the folder alone, here and in the referrers table.
- **Reached the promoting stage**, the stage whose `PARA home` sits under `projects/`. A `Won` header date counts as reached wherever the entity now sits, including a delivery project archived outside every declared home once it ships - the script's own extra read of `archive/<promoting home>`. A vault whose lifecycle has none says so once and drops this line and the median.
- **Reached each terminal stage**, one count per stage whose home is under `archive/`, each followed by the reasons recorded on those entities this quarter, grouped the same way as the referrers table (the text before the first comma) and counted (`reasons_this_quarter`). A terminal entity with no reason line is named instead of counted. **Where the quarter holds none, print the all-time counts instead**, one line marked as such (`all_time_reasons`).
- **A referrers table** (`referrers`), grouped by the script on the phrase before the first comma of each `Source` header line (`referral from <contact>`, `inbound via <channel>`, `outreach`), a link reduced to its label, over entities opened this quarter, with how many of each group reached the promoting stage. Entities whose source line is missing are one `unrecorded` row, never dropped.
- **Median days from `Opened` to the promoting stage** (`median_days_opened_to_promoting`), over the entities that reached it, with the count it was taken over. Fewer than three and it prints the individual numbers instead.

**Nothing per stage.** No conversion rate, no funnel percentage, no weighted value, no forecast.

## The close

One **Next action**, the same shape as the daily brief's: the single most concrete step the board justifies, naming an entity and what to do about it, with its file link. Prefer an entity flagged for a dated fact about to expire, then one with no next step at the latest stage reached, then the oldest days-in-stage at the stage nearest the promoting one. Where the board is clean, close on the review itself rather than inventing work.
