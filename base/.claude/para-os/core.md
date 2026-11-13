# para-os core

The fixed para-os rules, the same in every vault. `/para-upgrade` replaces this file whole: never edit it. The vault's own `CLAUDE.md` holds its map, its tables and its own rules, and **wins wherever the two differ**.

## PARA layout

The sorting test: **committed and dated → project. Maintained, no end date → area. Only thinking about it → idea. Over → archive.** What each folder holds in this vault is in its `CLAUDE.md`.

Root `README.md` is the single source of truth for identity, operating model and track record. Its first four `##` headings are exactly `Identity`, `Operating model`, `Track record`, `Vision`, in English, and Vision is never a stub. It holds no work state (a checkbox, a `📅`, a status list, a "to confirm"); a status fact about the subject (`| Status | Active |`) is not work state.

### Lifecycle

- `/para-new` creates every project, area, idea and contact.
- An idea **promotes** to a project when someone waits on a dated deliverable, money or a formal engagement is committed, or a go/no-go is on the calendar; it gets its `actions.md` then. Retiring one is the operator's call: never started goes to `archive/ideas/`, started and stopped to `archive/projects/`.
- A big dated push on a maintained asset is a **project alongside its area**; surviving work returns to the area when it archives. A project with no dated commitment for six months is proposed for **demotion** to an area.
- An entity **archives whole** via `/para-archive`, its open items routed first to the owning area, a successor project or a contact file. Where the vault's `CLAUDE.md` names an archive destination for a kind of entity, that kind goes there.
- **Every move repoints inbound links in the same pass.**

### Archive hygiene

- **No live work**: zero open actions, each done or noted "fully closed; minor gaps not material".
- **History archives; living references move to `resources/<name>/`.**
- **No loose files at the archive root.**
- **Minimum record**: a status marker saying why, plus its `brief.md` or `README.md`.
- **Zero dangling links** to the old path; a historical mention inside the archived folder is fine.

## Actions

Which folders may hold a checkbox, and where an action about a person or about no single entity goes, is in the vault's `CLAUDE.md`. Never a root `actions.md`.

### The actionable frontier

A checkbox is something you could act on now or on its marked date. A step behind an uncleared dependency stays prose (a `## Backlog` section or the brief) until its gate opens. A file holds at most 8 open items, waits on others aside: at 8, close or demote one first. Triage and working sessions add at most one next step per inbound item. An action's headline (its bold lead, or the whole line) stays under 120 characters, detail going to a sub-bullet or the brief; an item that moves is closed and its successor written as a new line.

### Task markers

`📅 YYYY-MM-DD` due, `🛫` start, `⏳` scheduled, `🔁 every <cadence>` recurring (with `📅` for the next occurrence), `🔺 🔼 🔽 ⏬` priority (none = medium), `✅ YYYY-MM-DD` done. Markers go at the end of the line, and a fuzzy date ("Q4") becomes one concrete marker. A `📅` is a real-world deadline; work gated on an outside event stays undated. One `## Recurring` section per file. Something owed by someone else is `- [ ] Waiting on [<person>](<card>): <what> (since YYYY-MM-DD)`, with no `📅`.

### The content frontier

- **Say it once.** Every fact has one owning file; elsewhere it is a link. The full convention is in `.claude/rules/figures.md`; read it explicitly before writing a figure into a brief or an entity README.
- **A development log records decisions** and their reasons, never activity.
- **Superseded content leaves the live buckets.**
- **Never delete to satisfy this.** Pruning is proposed item by item, *move* or *demote* by default, deletion only for a duplicate whose contents were compared; never a source document or `triage/`.

## Filing and naming

- **Contacts**: one file per person at `areas/network/<firstname-lastname>.md` (kebab-case, no diacritics): relationship context, an optional `## History`, then `## Next actions` (`_None currently._` when empty or at `never`), then any `## Backlog`. A shared workstream lives in the primary contact's file; the others point to it.
- **Dated conversation records**: in the owning project's or area's `sources/`; in `archive/meetings/YYYYMMDD Description.ext` only when they span several entities.
- **Source documents** are named as the vault's `CLAUDE.md` says. The rest of the convention is in `.claude/rules/filing.md`; read it explicitly before filing one.
- **A contact file and a project brief cross-link** both ways.

## Authoritative sources

Name the owning file before answering, and check `triage/` before searching by date. System-of-record data beats a hand-kept table; when they disagree, correct the table. Answer from the operator's own documents by quoting the clause with its file and page.

## Language

Folders and structural files in English; content in its source's language, untranslated unless asked. The operator's language is in the vault's `CLAUDE.md` and is the default; answer a request in the language it is written in, whatever the source's language, quoting the original only where the exact wording matters. A time follows `para-shared/timestamps.md`, installed beside the `/para-*` skills.

## Memory

This vault is the memory: never the agent's built-in memory, a `memory/` folder or session logs. A durable fact goes in the file it describes before the turn ends: what the conversation settled that no file holds (a date, a decision and its reason, an action done or promised) is written, or asked about in one question, not left as an offer for later. Each reply ends with `Close: ready` when closing would lose nothing (written-down open work does not count), else `Close: not yet, <what closing would lose>`. How the operator likes to work is kept apart, in `.claude/rules/working-preferences.md`; read it explicitly before drafting anything for the operator. A draft to send follows `para-shared/drafting.md`; a voice profile is built per `para-shared/voice-profile.md`.

## File formats

Markdown and plain text first; `.csv`, `.docx` and `.xlsx` for material received. A cloud-native stub (Google Docs or Sheets) is converted to a real file when it lands.

## Integration scripts and their state

A script the agent writes lives in `resources/scripts/` (its `README.md` names the state buckets); credentials, caches and bulk data live under `~/.paraos/`, never in a synced folder.

**A failing integration is repaired or reported, never replaced**: two scripts for one source is a defect, and one for a source no integration covers is first proposed as that gap.

## Do not add

- **Templates** before a second instance proves the shape.
- **Derived outputs as standalone files**: web copy, decks and one-pagers regenerate from `README.md`.
- **Content rewrites during a reorganization**: structure changes keep copy verbatim.
- **Procedure or rationale in the vault's `CLAUDE.md`**: it belongs in the owning script's README or the skill.
- **A `.claude/rules/<topic>.md` file** other than as `para-shared/rule-files.md` describes; read it before creating or editing one. The vault's `CLAUDE.md` keeps only each one's pointer.
- **A skill before its third use.** A recurring request starts as a prompt in `resources/prompts/`. Never name a skill `para-*`: `/para-upgrade` replaces a skill carrying a name para-os ships.
