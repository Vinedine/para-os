# Flavor: real-estate

For a vault whose business is property: buying, renovating, selling, or holding it. A flavor is what a vault is *about*, so this adds a lifecycle, a document shape per property, three skills that verify, underwrite and present a deal, and a deal-sheet template. It works on any [delivery](../../delivery/): on readonly-ipad the deal sheet is rendered to PDF, and on any other it stays HTML.

**Country-neutral by design.** No file here names a registry, permit, tax or listing portal. Everything local lives in the vault, in two files the skills read at runtime: the source register, and the analyst persona's `knowledge/`.

## What it adds

1. **`CLAUDE.md` sections** ([`CLAUDE.md.sections`](CLAUDE.md.sections)): `## Property lifecycle` (stages, promotion, archive destinations), `## Entity structures` with the rule pointers, and `## Deal sheets` (the pipeline and what it reads). They are added beside the sections of base or the delivery skeleton and never replace one.
2. **Rule files** ([`.claude/rules/`](.claude/rules/)): `brief-structure.md` and `readme-structure.md` (the floor, in every vault that declares shapes, here handing property documents over), `property-dossier.md` (the shape of a property's document at every stage, briefs and READMEs alike), `property-sources.md` (the naming convention inside a property's `sources/`, extending `filing.md`).
3. **Skills** ([`.claude/skills/`](.claude/skills/)): `/property-reconcile`, `/property-underwrite`, `/property-dealsheet`. They read `para-shared/` and install beside the base skills.
4. **Skeleton files** ([`skeleton/`](skeleton/)): `resources/property-evaluation/property-data-sources.md`, the source register to fill in, and `resources/prompts/dealsheet-template.html`.

## What the vault supplies

- **The source register, filled in.** Which facts are free, behind a login, or settled only by a paid request; any local lookup script; the listing portals; transaction costs; the local traps.
- **An analyst persona**: one folder under `resources/prompts/` holding a `*.core.md` (strategy, priorities, guardrails), `adapters/claude-code.md`, and `knowledge/` (tax, legal structure and market reference for the vault's jurisdiction).
- **Optionally, the owner's books**, named on the books line of `## Deal sheets`.

## Setup

1. Add `**Flavor:** real-estate` under the `**Type:**` line of the vault's `CLAUDE.md`, and merge in `CLAUDE.md.sections`.
2. Add the four rule files to the vault's `.claude/rules/`. Where the vault has its own `brief-structure.md` or `readme-structure.md`, merge the flavor's into it instead: the property hand-off and the `paths:` join what it already declares. Copy `skeleton/` into the vault, and `.claude/skills/` beside the base skills.
3. Fill in the register and write the persona before the first `/property-underwrite`.
