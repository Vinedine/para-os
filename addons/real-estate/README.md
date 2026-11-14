# Flavor: real-estate

For a vault whose business is property: buying, renovating, selling, or holding it. A flavor is what a vault is *about*, so this adds a lifecycle, a document shape per property, three skills that verify, underwrite and present a deal, and a deal-sheet template.

**Country-neutral by design.** No file here names a registry, permit, tax or listing portal. Everything local lives in the vault, in two files the skills read at runtime: the source register, and the analyst persona's `knowledge/`.

## What it adds

1. **A fixed file** ([`para-os/real-estate.md`](para-os/real-estate.md)): `## Property lifecycle` (stages, promotion, archive destinations), `## Entity structures` with the rule pointer, and `## Deal sheets` (the pipeline and what it reads). The vault imports it beside the core and never edits it. **`## Property lifecycle` is a lifecycle declaration in base's sense** ([`para-shared/lifecycles.md`](../../base/.claude/skills/para-shared/lifecycles.md)), so `/para-pipeline` renders the property board, and `/para-daily-brief` the counts by stage, from the table already there: nothing to add, provided each dossier carries the header `property-dossier.md` gives it, its Stage line naming a stage of the table.
2. **Rule files** ([`.claude/rules/`](.claude/rules/)): `property-dossier.md` (the shape of a property's `brief.md` at every stage), `property-sources.md` (the naming convention inside a property's `sources/`, extending `filing.md`).
3. **Skills** ([`.claude/skills/`](.claude/skills/)): `/property-reconcile`, `/property-underwrite`, `/property-dealsheet`. They read `para-shared/` and install beside the base skills. They are frozen: they stay installed as they are and take no changes.
4. **Skeleton files** ([`skeleton/`](skeleton/)): `resources/property-evaluation/property-data-sources.md`, the source register to fill in, and `resources/prompts/dealsheet-template.html`.

## What the vault supplies

- **The source register, filled in.** Which facts are free, behind a login, or settled only by a paid request; any local lookup script; the listing portals; transaction costs; the local traps.
- **An analyst persona**: one folder under `resources/prompts/` holding a `*.core.md` (strategy, priorities, guardrails), `adapters/claude-code.md`, and `knowledge/` (tax, legal structure and market reference for the vault's jurisdiction).
- **Which stages it uses**, in one line of its own `CLAUDE.md`: a flip business normally skips Held, a buy-and-hold one uses every stage.
- **Optionally, the owner's books and a capital page**, each named in one line of its own `CLAUDE.md`.

## Setup

1. Add `**Flavor:** real-estate` under the `**Type:**` line of the vault's `CLAUDE.md`. Copy `para-os/real-estate.md` to the vault's `.claude/para-os/` and add `@.claude/para-os/real-estate.md` under the core's import line.
2. Add the two rule files to the vault's `.claude/rules/`. Copy `skeleton/` into the vault, and `.claude/skills/` beside the base skills.
3. Fill in the register and write the persona before the first `/property-underwrite`.
