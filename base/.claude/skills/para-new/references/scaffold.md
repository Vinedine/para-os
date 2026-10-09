# Propose and scaffold (Step 4)

Nothing is written until the proposal is approved: the folder path, the files, and the brief's headings with the user's answers in them, shown as content.

## The brief's shape

- **The vault declares one for the path** ([A vault's rule files](../../para-shared/operating-discipline.md#a-vaults-rule-files)): use it, in its order where it fixes one, a section with no answer filled as the vault says (typically `_n/a_`), even where this entity strains the shape.
- **It describes one without naming sections**: take the header and section names of the closest existing entity of that shape.
- **None**: the minimal spine, and no template file added to the vault. A project: a title, `## Goal`, `## Why it matters`, and `## Source` where there is one (a source still in `triage/` named in prose, not linked). An area: a title, what it covers and what keeping it going involves. An idea: a title, the concept as the user phrased it, and the promotion trigger as one line, with no status field.

**The project's deadline is written down**: in the vault's status or header line where its shape has one, else in `## Goal`. A next step for work owed by that date falls on or before it, and the closing report says which date is which where they differ.

## What gets written

| Shape | Path | Files |
|---|---|---|
| Project | `projects/<slug>/` | `brief.md`, `actions.md` |
| Area | `areas/<slug>/` | `brief.md`, `actions.md` |
| Idea | `resources/ideas/<slug>/` | `brief.md` only |
| Contact | `areas/network/<firstname-lastname>.md` | the one file |

`<slug>` follows the vault's naming convention (kebab-case, no diacritics by default), from what the user calls the work; a long name keeps its full phrasing as the title. No empty containers: `sources/` and headings arrive with content. Re-check the folder does not exist immediately before writing.

### A staged entity

For a lifecycle the vault declares ([para-shared/lifecycles.md](../../para-shared/lifecycles.md)) whose noun the operator used, the path is **the first stage whose `PARA home` is a folder**. An entity belonging at an earlier row home is **one row appended to that register**, in its column order, and nothing else: say which before writing. The document opens with `**Stage:** <Stage> (since <today>)` and the header lines the lifecycle's rule file declares, in its order, an unsettled field written as its `## Placeholders` says. The champion's contact file comes with it, as below: without one, the next step has no home.

## Seed exactly one action

`actions.md` gets the vault's heading shape and **one** open item, the third interview answer, with a `📅` only where the deadline is real and belongs to that step. Anything else volunteered goes under `## Backlog` as prose, verbatim. A date stated in words becomes the vault's marker, a renewal [dated on its last day to give notice](../../para-shared/operating-discipline.md#dating-a-renewing-agreement); a month, a quarter or an unknown notice period is asked, never guessed.

An area with only recurring work gets it under the recurring heading and no open step. A contact's outstanding item goes under its next-actions heading as far as the `areas/network/` row allows, else with the entity it serves, and the empty sentinel otherwise; a declared `**Kind:**` line goes directly under the title.

## Cross-link before finishing

- **A person already in the vault**: a pointer line on their contact file, and the contact linked from the brief.
- **Promoted or spun out**: link back to the origin, and forward from it.
- **Created from a document** in the vault or being filed by `/para-triage`: link it as the brief's source, at its destination path.
- **A counterparty with none of the above**: **create their contact file too** (the person dealt with, where it is an organisation), proposed with the entity, pointing at it, with the empty sentinel unless something is outstanding. Declined, the closing report says the entity has no inbound link.

Report what was created and linked in one short block, without restating the brief.
