# Module: sales

For a vault that sells something: prospects, demos, proposals, and the deals that come from them. A module is a **function a vault adds beside whatever it is about**, so this adds one lifecycle, one document shape, and the register that holds the leads which have not earned a folder yet. It needs no skill of its own: the board is `/para-pipeline`, which base ships, and the stages come from the vault's `CLAUDE.md`.

It sits beside any [flavor](../real-estate/), including none. A property developer carries the real-estate flavor for its properties and this module for its buyers, in two tables, one `CLAUDE.md`, no overlap.

**Vocabulary-neutral where it can be, opinionated where it pays.** The stage names are the phases a prospect hears in the room rather than generic funnel words, so a vault whose sales conversation has its own names renames them in its own table and changes nothing else.

## What it adds

1. **`CLAUDE.md` sections** ([`CLAUDE.md.sections`](CLAUDE.md.sections)): `## Deal lifecycle` (the seven stages and their homes, rows before folders, what promotes and moves back, Nurture and Lost, the weekly review, and the contact card's `**Kind:**` line) and an `## Entity structures` pointer. They are added beside the sections of base or a flavor, and never replace one.
2. **A rule file** ([`.claude/rules/deal-brief.md`](.claude/rules/deal-brief.md)): the eight header lines of a deal brief, the lost-reason list, the rule that keeps the next step out of the header, and the columns of the lead register.
3. **No skill, no skeleton files.** `/para-pipeline` renders the board from the declared lifecycle, and the register is one file the vault creates the first time it has a lead.

## What the vault supplies

- **The register's path**, as the `{{areas/business/leads.md}}` placeholder in the lifecycle table. A vault with a sales area names `areas/sales/leads.md` instead; a one-operator business uses its business area.
- **The target profile** the Qualified stage tests against, in the root `README.md`. The module names the test; what a good customer looks like is the vault's own answer.
- **Its own stage names**, where the sales conversation already has them, and the value basis it quotes in (a cap, a range, a day rate).

## Setup

A new vault for a business gets the module from the bootstrap, which offers it and runs these steps itself. An existing vault adopts it by hand:

1. Add `**Modules:** sales` under the `**Type:**` line of the vault's `CLAUDE.md`, comma-separated where the vault already declares one, and merge in `CLAUDE.md.sections`. Replace the register placeholder with the real path.
2. Copy `.claude/rules/deal-brief.md` into the vault's `.claude/rules/`. Where the vault has a `brief-structure.md`, add a line to it: `deal-brief.md` takes over briefs whose Stage line names a deal stage.
3. Create the register at the path you named, with its `## Open` and `## Closed` headings, and add the weekly review to the business area's actions file under `## Recurring`.
4. Give every deal already in the vault, live or archived, the Stage line and header `deal-brief.md` declares: without a Stage line it never reaches the board.
5. Give every card in `areas/network/` its `**Kind:**` line. A buyer the board does not show gets a register row, a deal folder, or a dropped note.
6. Run `/para-pipeline` once, and the counts line it adds to `/para-daily-brief` arrives with it.
