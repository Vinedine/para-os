# para-os core

<!-- para-os-template: 2026.11.01 -->
The fixed para-os rules, the same in every vault. `/para-upgrade` replaces this file whole: never edit it. The vault's own `CLAUDE.md` holds only what is true of that vault, and **wins wherever the two differ**. The lines that open it (title, `**Type:**`, `**Flavor:**`, `**Modules:**`) are machine-read: keep them.

**A rule is written once.** The vault's `CLAUDE.md` repeats nothing from this file, a rule file or a skill: it holds what the vault adds and where it departs. Check before adding a line there.

## PARA layout

The sorting test: **committed and dated → project. Maintained, no end date → area. Only thinking about it → idea. Over → archive.**

- **triage/** - the inbox `/para-triage` empties; nothing lives here, not even a `README.md`.
- **projects/** - time-bound work with a committed deliverable and deadline. One folder each, holding a `brief.md`, an `actions.md` and, where needed, `sources/`. A rolling backlog with no deadline is an area.
- **areas/** - ongoing responsibilities. One folder per maintained asset, with its own `brief.md` + `actions.md`; assets that gate each other form **one** area.
- **resources/** - reusable reference. `prompts/` = reusable specs and drafts. `ideas/` = one folder per idea: a `brief.md` of open questions with at most one "revisit when X" trigger, and a `sources/` where documents back it. `scripts/` = persistent tools. No loose file at its root beyond its `README.md` index.
- **archive/** - inactive artifacts, always in a subfolder. `projects/` and `ideas/` = finished projects and retired ideas.

Root `README.md` is the single source of truth for identity, operating model and track record. Its first four `##` headings are exactly `Identity`, `Operating model`, `Track record`, `Vision`, and it holds no work state (a checkbox, a due date, a status list).

### Lifecycle

- `/para-new` creates every project, area, idea and contact.
- An idea **promotes** to a project when someone waits on a dated deliverable, money or a formal engagement is committed, or a go/no-go is on the calendar; it gets its `actions.md` then. Something on a declared lifecycle moves by its stages instead. Retiring an idea is the operator's call: never started goes to `archive/ideas/`, started and stopped to `archive/projects/`.
- Scheduled multi-step work is not an idea: it is a project, or an area where the thing is maintained.
- A big dated push on a maintained asset is a **project alongside its area**; surviving work returns to the area when it archives.
- An entity **archives whole** via `/para-archive`, its open items routed first to the owning area, a successor project or a contact file. Where the vault's `CLAUDE.md` names an archive destination for a kind of entity, that kind goes there.
- **Every move repoints inbound links in the same pass.**

## Actions

### Where a checkbox may live

| Bucket | `actions.md` | State |
|---|---|---|
| `projects/`, `areas/` | yes | open + closed |
| `areas/network/` | yes | any action about the person; `relationship only` keeps replies, introductions, thanks and check-ins; `never` keeps none |
| `resources/` | **never** | a checkbox here is a filing error |
| `archive/` | yes | **all closed** - one open `- [ ]` means it was archived too early |

A row the vault's `CLAUDE.md` writes under the same heading replaces the row of that bucket, and a new bucket adds one. A folder whose work is tracked elsewhere (an external tracker, a generated file) gets its own row at `never`.

An action goes in the `actions.md` of the project or area it belongs to; one about a person in their contact file under `## Next actions`, as far as the `areas/network/` row allows, else with the entity it serves; work tied to no single entity in the area the vault names for it, and a dated go/no-go on an idea there too, linking the idea. There is no root `actions.md`.

How an action is written (what is actionable, how many a file holds, the markers) is in `.claude/rules/writing-actions.md`, which loads when an `actions.md` or a contact card is opened; read it explicitly before writing an action anywhere else.

### The content frontier

- **Say it once.** Every fact has one owning file; elsewhere it is a link. The full convention is in `.claude/rules/figures.md`; read it explicitly before writing a figure into a brief.
- **A development log records decisions** and their reasons, not activity.
- **Superseded content leaves the live buckets.**
- **Never delete to satisfy this.** Pruning is proposed item by item, *move* or *demote* by default, deletion only for a duplicate whose contents were compared; never a source document or `triage/`.

## Filing and naming

- **Contacts**: one file per person or organisation at `areas/network/<firstname-lastname>.md` (kebab-case, no diacritics; an organisation under its own name). How a card is laid out is in `.claude/rules/writing-actions.md`.
- **Source documents and dated records**: `YYYYMMDD <Who> - <Description>.<ext>` in every vault. The date is the document's own, and who is its most identifying party, or the subject for the operator's own notes. The rest of the convention is in `.claude/rules/filing.md`; read it explicitly before filing one.
- **A dated conversation record** lives in the owning project's or area's `sources/`; in `archive/meetings/` when it spans several entities or none owns it.
- **A contact file and a project brief cross-link** both ways.

## Authoritative sources

Name the owning file before answering, and check `triage/` before searching by date. System-of-record data beats a hand-kept table; when they disagree, correct the table. Answer from the operator's own documents by quoting the clause with its file and page.

A mailbox or calendar read through a connector is read-only: surface and draft, never send or change anything in it.

## Who is working

The operator is the person in the session. Where the vault's `CLAUDE.md` has a `## Who writes this vault` table, their row gives their role: the keeper decides for the vault, a member works in their own areas, the steward keeps the conventions. The table says who owns what; the operator's row is the one whose contact card `~/.paraos/operator.json` names.

Two people saving one file at once is the one real failure of a shared vault, and it is silent: say so before editing a file in someone else's area. A vault several people sync holds no `.git` folder; its history is the sync service's version history plus the vault's mirror.

## Language

Folders and structural files in English; content in its source's language, untranslated unless asked. The operator's language is English unless the vault's `CLAUDE.md` names another, and is the default; answer a request in the language it is written in, whatever the source's language, quoting the original only where the exact wording matters. A time follows `para-shared/timestamps.md`, installed beside the `/para-*` skills.

## Memory

This vault is the memory: never the agent's built-in memory, a `memory/` folder or session logs. A durable fact goes in the file it describes before the turn ends: what the conversation settled that no file holds (a date, a decision and its reason, an action done or promised) is written, or asked about in one question, not left as an offer for later. Each reply ends with `Close: ready` when closing would lose nothing (written-down open work does not count), else `Close: not yet, <what closing would lose>`. A draft to send follows `para-shared/drafting.md`.

## Integration scripts and their state

A script the agent writes lives in `resources/scripts/` (its `README.md` names the state buckets); credentials, caches and bulk data live under `~/.paraos/`, never in a synced folder.

**A failing integration is repaired or reported, never replaced**: two scripts for one source is a defect, and one for a source no integration covers is first proposed as that gap.

## Do not add

- **Content rewrites during a reorganization**: structure changes keep copy verbatim.
- **A `.claude/rules/<topic>.md` file** other than as `para-shared/rule-files.md` describes; read it before creating or editing one.
- **A skill before its third use.** A recurring request starts as a prompt in `resources/prompts/`. A vault's own skill takes a name that does not start with `para-`: `/para-upgrade` replaces a skill carrying a name para-os ships.
