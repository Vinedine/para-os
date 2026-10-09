# Lifecycles (shared across skills)

A lifecycle names the stages one kind of entity passes through inside the PARA buckets, which home each stage lives in, and where the entity leaves the live buckets. The vault declares it in its `CLAUDE.md` and a skill only reads it; a vault holding properties and deals carries two.

## The declaration

A `CLAUDE.md` section whose heading ends in `lifecycle`, holding a table whose first column is `Stage` and which carries a `PARA home` column; every other column is free text to print, never parse.

- The heading's first word is the entity noun (`## Deal lifecycle` gives `deal`), what `/para-new <noun> <name>` takes.
- A `Stage` cell names one or more stages: emphasis stripped, what stands before the first `:` split on commas; the rest is a gloss.
- A `PARA home` cell is a path, backticks stripped, with one `<...>` placeholder for the entity's own folder or row name. The union of the homes is what a skill scans.
- A stage whose home sits under `archive/` is terminal: an entity there is closed, read for the metrics and its reason, never rendered as live work.

## Folder homes and row homes

A folder home (`resources/ideas/<name>/`) is one entity per folder, carrying its stage in the `brief.md` or `README.md` the vault's shape gives it. A row home is a path suffixed `(row)` (`areas/business/leads.md (row)`): one table row per entity, the `Stage` column its stage, the other columns its header, its own next-step column its next step. A row under `## Closed` counts in the metrics and nowhere else.

## The Stage line

A folder entity carries its stage directly under the title, on the first line whose text begins with `Stage:`:

```
**Stage:** Proposal (since YYYY-MM-DD; prices hold to YYYY-MM-DD)
```

- The name is what stands before the first `(`, with emphasis, the leading `Stage:`, a trailing ` - ` clause and trailing punctuation removed, matched case-insensitively; in the `_Stage: Acquiring - <key date>_` form the dash clause is the qualifier.
- `since <date>` in the qualifier gives days in stage; without it, days in stage is unknown, never a modification time. Any other date there is a dated fact, read for the expiry flag while it is ahead.
- An entity with no Stage line, or one matching no declared name, is in no lifecycle: an idea's `**Stage:** Concept` is not a deal at a stage called Concept.

## What each skill does with one

- `/para-pipeline` renders the board, flags and metrics, reading `Opened`, `Source`, `Champion`, `Signer`, `Value`, `Last touch`, `Won`, a terminal stage's `<Stage> reason`, and a row's `Contact` and `Next step` wherever the rule file declares them, names matched case-insensitively.
- `/para-daily-brief` adds one line per lifecycle, counts by stage. `/para-prep` shows a meeting's staged entities with stage, days in stage, `Last touch` and `Signer`, and the stage's exit criterion as the meeting's starting objective.
- `/para-new <noun> <name>` scaffolds at the first non-row stage's home with the Stage line and header the rule file states. `/para-triage` offers a new counterparty's first mail as a row at the first stage, and proposes Last touch, Signer and next step from a meeting record ([filing.md](../para-triage/references/filing.md#a-meeting-record)). `/para-archive` refuses a move into a terminal stage unless the Stage line names it, plus any reason line the rule file requires.
- A stage is never written by a skill's own judgment: moving an entity is the operator's call; a skill reports what the files say and flags what has stopped moving.
