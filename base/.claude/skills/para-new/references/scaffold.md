# Propose and scaffold (Step 4)

Nothing is written until the proposal is approved. The proposal is short: the folder path, the files, and the brief's headings with the user's own answers already in them. Show the actual content, not a description of it.

## Resolve the brief shape first

- **If the vault declares a shape for the new file's path**, resolved per [A vault's rule files](../../para-shared/operating-discipline.md#a-vaults-rule-files), use it. Where two shape files match, each file's own text says which kind of entity it takes.

  **Follow the order only where the vault fixes one.** A declared shape may state its sections as an ordered contract, or may say explicitly that order varies by entity and is not enforced. Honour whichever it does. A declared section this entity has no answer for gets whatever the vault says to do with it, typically an explicit `_n/a_`.
- **If it describes a shape without naming sections** ("outcome up top, then a development log"), open the closest existing entity of the same shape, take its header block and section names, and fill them with this entity's answers. Where the vault holds no existing entity of that shape, the minimal spine is right and this is the first instance.
- **If it declares none**, use the minimal spine below and **do not add a template file to the vault**: templating a shape is the operator's decision once a second instance proves it.

Minimal project brief: a title, `## Goal` (what it produces), `## Why it matters` (what it unblocks), and `## Source` (where this came from - the meeting, the mail, the conversation) when there is one. Nothing else earns a heading on day one.

Minimal area brief: a title, what the area covers, and what keeping it going involves. An area's brief is the running narrative of something that has no end, so it states scope rather than an outcome.

Minimal idea brief: a title, the concept as the user phrased it, and the promotion trigger as one prose line. No status field: the folder it sits in is the only state an idea has.

## Record the deadline the project was created for

Interview question 2 asks who is waiting and by when. **The answer gets written down, not merely used to classify.**

- **It goes in the brief.** Into the vault's status or header line where its declared shape has one, and into `## Goal` otherwise.
- **It bounds the seeded action.** A next step for work owed on a date falls on or before that date, and where the next step *is* the delivery, it carries the project's own date.
- **A date in a brief is prose, and no skill reads it.** Where the deadline and the next step are different dates, say which is which in the closing report.

## What gets written

| Shape | Path | Files |
|---|---|---|
| Project | `projects/<slug>/` | `brief.md`, `actions.md` |
| Area | `areas/<slug>/` | `brief.md`, `actions.md` |
| Idea | `resources/ideas/<slug>/` | `brief.md` only |
| Contact | `areas/network/<firstname-lastname>.md` | the one file |

`<slug>` follows the vault's naming convention, kebab-case by default, no diacritics. `areas/business/` and `areas/network/` are the skeleton's standing subfolders and are never created here; a person goes in `areas/network/` as a contact file, not in an area of their own. Take the name from what the user calls the work, not from a summary of it: they have to recognise it in a dashboard.

On the read-only iPad delivery these writes run inside [its edit cycle](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery).

**Create no empty containers.** A `sources/` folder is created when there is a document to put in it, not in advance. The same goes for headings with nothing under them.

## Seed exactly one action

A project's or area's `actions.md` carries the vault's heading shape and **one** open item: the answer to the third interview question, with a `📅` only if the deadline is real and belongs to that step rather than to the project as a whole. Anything else the user volunteered goes under `## Backlog` in the same file, as prose, verbatim.

**A date never survives as free text.** "before the contract renews in November" is a real deadline written where no skill can read it, and most vaults forbid it outright. Convert it to the vault's marker, and where the answer is a month or a quarter rather than a day, ask for the day instead of guessing one.

An area whose only outstanding work is recurring gets that item under the vault's recurring heading and no open next step, which is a complete file rather than an empty one. An idea gets no `actions.md`. A contact's outstanding item, if there is one, goes under the contact file's own next-actions heading; if there is none, the vault's empty sentinel goes there instead.

Where the vault's conventions drop action tracking altogether, the next step is prose in the brief and no `actions.md` is created.

## Cross-link before finishing

- **Project or idea involving a person already in the vault**: add a pointer line to that contact file, and link the contact from the brief. The contact file stays the relationship summary; the brief holds the execution detail.
- **Promoted from an idea, or spun out of another entity**: link back to where it came from, and forward from there.
- **Created from a document** already in the vault, or one `/para-triage` is filing in the same run: link it as the brief's source, at the destination path triage gives it, rather than copying its contents into the brief.
- **A project or idea with a counterparty, where nothing above applies**: **create the counterparty's contact file too**, the one exception to creating a single entity. Where the counterparty is an organisation, the file is for the person dealt with there. Propose it alongside the project rather than after it, scaffolded to the contact shape with a pointer to the new entity and the vault's empty-actions sentinel unless the interview surfaced something outstanding. If the operator declines it, the closing report says the entity has no inbound link and names the contact file as what would give it one.

Report what was created and what was linked, in one short block. Do not restate the brief back to the user; they just wrote it.

## Edge cases

- **The slug collides with an archived entity.** Allowed, and worth naming: say which archived entity shares the name so the operator can pick a distinct one if this is a successor rather than a repeat.
- **The user's name for the work is a sentence.** Slug the short form, and keep their full phrasing as the brief's title line.
- **Two people are creating in the same vault at once** (a synced drive with no merge step): re-check the folder does not exist immediately before writing, not only at Step 1.
- **The vault declares a shape this entity genuinely breaks** (a commercial section in a household vault, say). Use the declared shape anyway and mark the section `_n/a_`. Changing the vault's declared shape is a `/para-deep-clean` decision, not a side effect of creating one entity.
