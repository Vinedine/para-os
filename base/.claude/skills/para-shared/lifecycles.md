# Lifecycles (shared across skills)

A **lifecycle** names the sub-stages one kind of entity passes through inside the PARA buckets, which PARA home each stage lives in, and where the entity leaves the live buckets. It adds no second spine: idea, project, area, archive stays the only rule everyone learns, and a lifecycle opens one of those boxes up for one kind of entity.

**The vault declares it; a skill only reads it.** A flavor or a module ships the section, the vault's `CLAUDE.md` carries it, and every skill that touches a staged entity resolves stages here rather than knowing any of its own. One lifecycle per kind of entity: a vault holding both properties and deals carries two tables, which is a normal vault and not a conflict.

## The declaration

A lifecycle is a `CLAUDE.md` section whose **heading ends in `lifecycle`**, holding a table whose **first column is headed `Stage`** and which carries a column headed **`PARA home`**. Every other column is free text: print it, never parse it.

- **The heading's first word is the entity noun** where the heading has one: `## Deal lifecycle` gives `deal`, `## Property lifecycle` gives `property`. That noun is what `/para-new <noun> <name>` takes.
- **A `Stage` cell names one or more stages.** Strip emphasis marks, take what stands before the first `:` as the names, and split those on commas; the rest of the cell is a gloss for the reader. A cell with no colon at all is read whole as the names. One cell may declare several stages that share a home.
- **A `PARA home` cell is a path**, backticks stripped, with a single `<...>` placeholder (`<name>`, `<company>`, `<property>`) standing for the entity's own folder or row name.
- **The union of the homes is what a skill scans.** Nothing outside them is in the lifecycle.
- **A stage whose home sits under `archive/` is terminal.** An entity there is closed: it is read for the metrics and for the reason recorded on it, never rendered as live work.

## Folder homes and row homes

- **A folder home** (`resources/ideas/<name>/`) is one entity per folder, carrying its stage in the `brief.md` or `README.md` the vault's shape rules give it.
- **A row home** is a file path suffixed `(row)` (`areas/business/leads.md (row)`): one table row per entity in the register that file holds. The row *is* the entity. The table's `Stage` column is its stage, the other columns are the header a brief would carry as bold lines, and its own next-step column is its next step, which is the one exception to the vault's rule about where a next step lives. This is the volume tier, so a list of three hundred names costs three hundred rows and nothing else, and the lifecycle table says at which stage a folder is earned.
- **A closed row leaves the live board.** Where a register separates open rows from closed ones, under `## Open` and `## Closed`, a row under `## Closed` counts in the metrics and nowhere else, whatever its `Stage` column says.

## The Stage line

An entity in a folder home carries its stage **directly under the title**, on the first line whose text begins with `Stage:`, colon included - a line that merely mentions the word `Stage` without it does not count:

```
**Stage:** Proposal (since YYYY-MM-DD; prices hold to YYYY-MM-DD)
```

- **The stage name is what stands before the first `(`**, with the emphasis marks, the leading `Stage:`, any trailing ` - ` clause and trailing punctuation removed, matched case-insensitively against the declared names. An emphasised variant is the same line read the same way (`_Stage: Acquiring - <key date>_`): take the name, and for this dash form the trailing ` - ` clause is the qualifier.
- **`since <date>` in the qualifier gives days in stage.** Without it, days in stage is unknown, reported as unknown and never inferred from a file's modification time.
- **Any other date in the qualifier is a dated fact** (a proposal's validity, an option's expiry), read for the expiry flag and only while it is still ahead.
- **An entity with no Stage line, or a stage text matching no declared name, is in no lifecycle**, which is what lets ordinary ideas and projects share a home with staged entities: an idea brief's own `**Stage:** Concept` line is not a deal at a stage called Concept.

## What each skill does with one

- **`/para-pipeline`** renders the board, the flags and the metrics, reading `Opened`, `Source`, `Champion`, `Signer`, `Value`, `Last touch`, `Won`, a terminal stage's `<Stage> reason`, and a register row's `Contact` and `Next step` columns wherever the entity's rule file declares them, every field and column name matched case-insensitively. Read-only, and the only skill that reads every lifecycle in one pass.
- **`/para-daily-brief`** adds one line per declared lifecycle to its vault state, counts by stage and nothing else.
- **`/para-new <noun> <name>`** scaffolds at the first non-row stage's home, with the Stage line and the header the declaring rule file states. The sorting test still runs.
- **`/para-triage`** offers a new counterparty's first mail as one row in the register its lifecycle opens on, at the first stage.
- **`/para-archive`** refuses a move into a terminal stage unless the entity's Stage line names that stage, plus any reason line the rule file requires.
- **A stage is never written by a skill's own judgment.** Moving an entity forward, back or out is the operator's call; a skill reports what the files say and flags what has stopped moving.
