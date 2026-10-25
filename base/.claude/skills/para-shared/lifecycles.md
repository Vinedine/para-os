# Lifecycles (shared across skills)

A lifecycle names the stages one kind of entity passes through and the home each stage lives in. The vault declares it in its `CLAUDE.md`, one per kind, and a skill only reads it.

## The declaration

A `CLAUDE.md` section whose heading ends in `lifecycle`, holding a table whose first column is `Stage` and which carries a `PARA home` column; every other column is free text to print, never parse.

- The heading's first word is the entity noun (`## Deal lifecycle` gives `deal`), what `/para-new <noun> <name>` takes.
- A `Stage` cell names one or more stages, comma-separated, before an optional `:` gloss.
- A `PARA home` cell is a path with one `<...>` placeholder for the entity's own folder or row name.
- A stage whose home sits under `archive/` is terminal: an entity there is closed, read for the metrics and its reason, never rendered as live work.

## Folder homes and row homes

A folder home (`resources/ideas/<name>/`) is one entity per folder, carrying its stage in the `brief.md` or `README.md` the vault's shape gives it. A row home is a path suffixed `(row)` (`areas/business/leads.md (row)`): one table row per entity, the `Stage` column its stage, the other columns its header, its own next-step column its next step. A row under `## Closed` counts in the metrics and nowhere else.

## The Stage line

A folder entity carries its stage directly under the title, on the first line whose text begins with `Stage:`:

```
**Stage:** Proposal (since YYYY-MM-DD; prices hold to YYYY-MM-DD)
```

- The name stands before the first `(` or ` - `; the rest is the qualifier.
- `since <date>` in the qualifier gives days in stage; without it, days in stage is unknown, never a modification time. Any other date there is a dated fact.
- An entity with no Stage line, or one matching no declared name, is in no lifecycle: an idea's `**Stage:** Concept` is not a deal at a stage called Concept.

## Who moves a stage

The operator. A skill never writes a stage by its own judgment: it reports what the files say and flags what has stopped moving.
