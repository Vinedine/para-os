# para-os core

The fixed para-os rules, the same in every vault. `/para-upgrade` replaces this file whole: never edit it. The vault's own `CLAUDE.md` holds only what is true of that vault, and **wins wherever the two differ**. The lines that open it (title, marker, `**Type:**`, `**Flavor:**`, `**Modules:**`) are machine-read: keep them through every upgrade.

**A rule is written once.** The vault's `CLAUDE.md` repeats nothing from this file, a rule file or a skill: it holds what the vault adds and where it departs. Check before adding a line there, and a rule that would read the same in two vaults belongs here.

## PARA layout

The sorting test: **committed and dated → project. Maintained, no end date → area. Only thinking about it → idea. Over → archive.**

- **triage/** - the inbox `/para-triage` empties; nothing lives here, not even a `README.md`.
- **projects/** - time-bound work with a committed deliverable and deadline. One folder each, holding a `brief.md`, an `actions.md` and, where needed, `sources/`. A rolling backlog with no deadline is an area.
- **areas/** - ongoing responsibilities. `network/` = one file per contact. One folder per maintained asset, with its own `brief.md` + `actions.md`; assets that gate each other form **one** area.
- **resources/** - reusable reference. `prompts/` = reusable specs and drafts. `ideas/` = one folder per idea: a `brief.md` of open questions with at most one "revisit when X" trigger, and a `sources/` where documents back it. `scripts/` = persistent tools. No loose file at its root beyond its `README.md` index.
- **archive/** - inactive artifacts, always in a subfolder. `meetings/` = records spanning several entities or owned by none. `projects/` and `ideas/` = finished projects and retired ideas.

Root `README.md` is the single source of truth for identity, operating model and track record. Its first four `##` headings are exactly `Identity`, `Operating model`, `Track record`, `Vision`, in English, and Vision is written out, not a stub. It holds no work state (a checkbox, a `📅`, a status list, a "to confirm"); a status fact about the subject (`| Status | Active |`) is not work state.

### Lifecycle

- `/para-new` creates every project, area, idea and contact.
- An idea **promotes** to a project when someone waits on a dated deliverable, money or a formal engagement is committed, or a go/no-go is on the calendar; it gets its `actions.md` then. Something on a lifecycle the vault declares moves by that lifecycle's stages instead. Retiring an idea is the operator's call: never started goes to `archive/ideas/`, started and stopped to `archive/projects/`.
- Scheduled multi-step work is not an idea: it is a project, or an area where the thing is maintained.
- A big dated push on a maintained asset is a **project alongside its area**; surviving work returns to the area when it archives.
- An entity **archives whole** via `/para-archive`, its open items routed first to the owning area, a successor project or a contact file. Where the vault's `CLAUDE.md` names an archive destination for a kind of entity, that kind goes there.
- **Every move repoints inbound links in the same pass.**

### Archive hygiene

- **No live work**: zero open actions, each done or noted "fully closed; minor gaps not material".
- **History archives; living references move to `resources/<name>/`.**
- **No loose files at the archive root.**
- **Minimum record**: a status marker saying why, plus its `brief.md`.
- **Zero dangling links** to the old path; a historical mention inside the archived folder is fine.

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

### The actionable frontier

A checkbox is something you could act on now or on its marked date. A step behind an uncleared dependency stays prose (a `## Backlog` section or the brief) until its gate opens. A file holds at most 8 open items, waits on others aside: at 8, close or demote one first. Triage and working sessions add at most one next step per inbound item. An action's headline (its bold lead, or the whole line) stays under 120 characters, detail going to a sub-bullet or the brief; an item that moves is closed and its successor written as a new line.

### Task markers

`📅 YYYY-MM-DD` due, `🛫` start, `⏳` scheduled, `🔁 every <cadence>` recurring (with `📅` for the next occurrence), `🔺 🔼 🔽 ⏬` priority (none = medium), `✅ YYYY-MM-DD` done. Markers go at the end of the line, and a fuzzy date ("Q4") becomes one concrete marker. A `📅` is a real-world deadline; work gated on an outside event stays undated. One `## Recurring` section per file. Something owed by someone else is `- [ ] Waiting on [<person>](<card>): <what> (since YYYY-MM-DD)`, with no `📅`.

### The content frontier

- **Say it once.** Every fact has one owning file; elsewhere it is a link. The full convention is in `.claude/rules/figures.md`; read it explicitly before writing a figure into a brief.
- **A development log records decisions** and their reasons, not activity.
- **Superseded content leaves the live buckets.**
- **Never delete to satisfy this.** Pruning is proposed item by item, *move* or *demote* by default, deletion only for a duplicate whose contents were compared; never a source document or `triage/`.

## Filing and naming

- **Contacts**: one file per person or organisation at `areas/network/<firstname-lastname>.md` (kebab-case, no diacritics; an organisation under its own name): relationship context, an optional `## History`, then `## Next actions` from the card's first action on, then any `## Backlog`. A shared workstream lives in the primary contact's file; the others point to it.
- **Source documents and dated records**: `YYYYMMDD <Who> - <Description>.<ext>` in every vault. The date is the document's own, and who is its most identifying party, or the subject for the operator's own notes. The rest of the convention is in `.claude/rules/filing.md`; read it explicitly before filing one.
- **A dated conversation record** lives in the owning project's or area's `sources/`; in `archive/meetings/` when it spans several entities or none owns it.
- **A contact file and a project brief cross-link** both ways.

## Authoritative sources

Name the owning file before answering, and check `triage/` before searching by date. System-of-record data beats a hand-kept table; when they disagree, correct the table. Answer from the operator's own documents by quoting the clause with its file and page.

A mailbox or calendar read through a connector is read-only: surface and draft, never send or change anything in it.

## Who is working

The operator is the person in the session. Where the vault's `CLAUDE.md` has a `## Who writes this vault` table, their row gives their role: the keeper decides for the vault, a member works in their own areas, the steward keeps the conventions. The table says who owns what; which row is in the session comes from the machine and the account, not from a file everyone shares.

Two people saving one file at once is the one real failure of a shared vault, and it is silent: say so before editing a file someone else is working in. A vault several people sync holds no `.git` folder; its history is the sync service's version history plus the vault's mirror.

## Language

Folders and structural files in English; content in its source's language, untranslated unless asked. The operator's language is English unless the vault's `CLAUDE.md` names another, and is the default; answer a request in the language it is written in, whatever the source's language, quoting the original only where the exact wording matters. A time follows `para-shared/timestamps.md`, installed beside the `/para-*` skills.

## Memory

This vault is the memory: never the agent's built-in memory, a `memory/` folder or session logs. A durable fact goes in the file it describes before the turn ends: what the conversation settled that no file holds (a date, a decision and its reason, an action done or promised) is written, or asked about in one question, not left as an offer for later. Each reply ends with `Close: ready` when closing would lose nothing (written-down open work does not count), else `Close: not yet, <what closing would lose>`. How the operator likes to work is kept apart, in `.claude/rules/working-preferences.md`; read it explicitly before drafting anything for the operator. A draft to send follows `para-shared/drafting.md`; a voice profile is built per `para-shared/voice-profile.md`.

## File formats

Markdown and plain text first; `.csv`, `.docx` and `.xlsx` for material received. A cloud-native stub (Google Docs or Sheets) is converted to a real file when it lands.

## Integration scripts and their state

A script the agent writes lives in `resources/scripts/` (its `README.md` names the state buckets); credentials, caches and bulk data live under `~/.paraos/`, never in a synced folder.

**A failing integration is repaired or reported, never replaced**: two scripts for one source is a defect, and one for a source no integration covers is first proposed as that gap.

## Do not add

- **Templates** before a second instance proves the shape.
- **Content rewrites during a reorganization**: structure changes keep copy verbatim.
- **Procedure or rationale in the vault's `CLAUDE.md`**: it belongs in the owning script's README or the skill.
- **A `.claude/rules/<topic>.md` file** other than as `para-shared/rule-files.md` describes; read it before creating or editing one. The vault's `CLAUDE.md` keeps only each one's pointer.
- **A skill before its third use.** A recurring request starts as a prompt in `resources/prompts/`. A vault's own skill takes a name that does not start with `para-`: `/para-upgrade` replaces a skill carrying a name para-os ships.
