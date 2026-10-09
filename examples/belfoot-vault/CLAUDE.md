# BelFoot Vault Conventions

<!-- para-os-template: 2026.10.01 -->
**Type:** vault

The consulting vault for BelFoot Royal Sporting Club ("BelFoot FC", Belgian Pro League) and its multi-stream IT modernisation programme - an external consultant engagement, started Q1 2026, running through 2027.

The lines above are machine-read: keep them through every upgrade.

## Context

BelFoot internal data (financials, employee records, contracts) is confidential to this engagement. This vault is the consultant's working copy; outputs that leave it (decks, reports, emails) are reviewed before send. Never reference another client engagement here - cross-client context violates the engagement letter.

**This is a synthetic example vault with a frozen reference date of 2026-06-24** (see the top of `README.md`). Every date in it is internally consistent as of that day and anchored to real match days. Do not "refresh" dates to the current calendar and do not treat the gap as drift to clean up. A brief reporting them overdue against today is correct, not a misread: judge the vault's *content* against 2026-06-24.

## PARA layout

The sorting test: **committed and dated → project. Maintained, no end date → area. Only thinking about it → idea. Over → archive.**

- **triage/** - the inbox `/para-triage` empties; nothing lives here, not even a `README.md` (a `.gitkeep` holds the folder).
- **projects/** - time-bound IT workstreams with a committed deliverable and deadline. One folder each, holding a `brief.md`, an `actions.md` and, where needed, `sources/` (RFP PDFs, vendor decks, scanned contracts). A rolling backlog on a system the club already runs is an area.
- **areas/** - ongoing responsibilities. `stadium/` = the stadium modernisation programme as a standing responsibility: cross-cutting strategic actions not tied to a single workstream. `network/` = one file per BelFoot stakeholder. Systems that gate each other (the wallet, the ticketing platform it integrates with, the stadium network both depend on) form **one** area.
- **resources/** - reusable reference (procurement templates, vendor evaluations, regulatory notes). `prompts/` = reusable specs and drafts. `ideas/` = one folder per idea: a `brief.md` of open questions with at most one "revisit when X" trigger, and a `sources/` where documents back it. `scripts/` = persistent tools. No loose file at its root beyond its `README.md` index.
- **archive/** - inactive artifacts, always in a subfolder. `meetings/` = records spanning several entities. `projects/` = completed workstreams and `ideas/` = shelved concepts (`/para-archive` fills both).

Root `README.md` is the single source of truth for identity, operating model and track record. Its first four `##` headings are exactly `Identity`, `Operating model`, `Track record`, `Vision`, in English, and Vision is never a stub. It holds no work state (a checkbox, a `📅`, a status list, a "to confirm"); a status fact about the subject (`| Status | Active |`) is not work state.

### Lifecycle

- `/para-new` creates every workstream, area, idea and contact.
- An idea **promotes** to a project when someone waits on a dated deliverable, money or a formal engagement is committed, or a go/no-go is on the calendar; it gets its `actions.md` then. Retiring one is the operator's call: never started goes to `archive/ideas/`, started and stopped to `archive/projects/`.
- A big dated push on a maintained asset is a **project alongside its area**; surviving work returns to the area when it archives. A project with no dated commitment for six months is proposed for **demotion** to an area.
- An entity **archives whole** via `/para-archive`, its open items routed first to the owning area, a successor project or a contact file. Where this file names an archive destination for a kind of entity, that kind goes there.
- **Every move repoints inbound links in the same pass.**

### Archive hygiene

- **No live work**: zero open actions, each done or noted "fully closed; minor gaps not material".
- **History archives; living references move to `resources/<name>/`.**
- **No loose files at the archive root.**
- **Minimum record**: a status marker saying why, plus its `brief.md` or `README.md`.
- **Zero dangling links** to the old path; a historical mention inside the archived folder is fine.

## Actions

### Where a checkbox may live

A folder whose work is tracked elsewhere (an external tracker, a generated file) gets its own row at `never`.

| Bucket | `actions.md` | State |
|---|---|---|
| `projects/`, `areas/` | yes | open + closed |
| `areas/network/` | yes | any action about the person; `relationship only` keeps replies, introductions, thanks and check-ins; `never` keeps none |
| `resources/` | **never** | a checkbox here is a filing error |
| `archive/` | yes | **all closed** - one open `- [ ]` means it was archived too early |

An action goes in the `actions.md` of the workstream or area it belongs to; one about a stakeholder in their contact file under `## Next actions`, as far as the `areas/network/` row allows, else with the entity it serves; strategic work tied to no single entity in `areas/stadium/actions.md`, and a dated go/no-go on an idea there too, linking the idea. Never a root `actions.md`.

### The actionable frontier

A checkbox is something you could act on now or on its marked date. A step behind an uncleared dependency stays prose (a `## Backlog` section or the brief) until its gate opens. A file holds at most 8 open items, waits on others aside: at 8, close or demote one first. Triage and working sessions add at most one next step per inbound item. An action's headline (its bold lead, or the whole line) stays under 120 characters, detail going to a sub-bullet or the brief; an item that moves is closed and its successor written as a new line.

### Task markers

`📅 YYYY-MM-DD` due, `🛫` start, `⏳` scheduled, `🔁 every <cadence>` recurring (with `📅` for the next occurrence), `🔺 🔼 🔽 ⏬` priority (none = medium), `✅ YYYY-MM-DD` done. Markers go at the end of the line, and a fuzzy date ("Q4") becomes one concrete marker. A `📅` is a real-world deadline; work gated on an outside event stays undated. One `## Recurring` section per file. Something owed by someone else is `- [ ] Waiting on [<person>](<card>): <what> (since YYYY-MM-DD)`, with no `📅`.

### The content frontier

- **Say it once.** Every fact has one owning file; elsewhere it is a link. The full convention is in [.claude/rules/figures.md](.claude/rules/figures.md), which loads on its own when a brief or an entity README is read; read it explicitly before writing a figure into one.
- **A development log records decisions** and their reasons, never activity.
- **Superseded content leaves the live buckets.**
- **Never delete to satisfy this.** Pruning is proposed item by item, *move* or *demote* by default, deletion only for a duplicate whose contents were compared; never a source document or `triage/`.

## Filing and naming

- **Contacts**: one file per stakeholder at `areas/network/<firstname-lastname>.md` (kebab-case, no diacritics): relationship context, an optional `## History`, then `## Next actions` (`_None currently._` when empty or at `never`), then any `## Backlog`. A shared workstream lives in the primary stakeholder's file; the others point to it.
- **Dated conversation records**: in the owning workstream's or area's `sources/`; in `archive/meetings/YYYYMMDD Description.md` only when they span several entities.
- **Source documents**: `sources/YYYYMMDD <Who> <Description>.<ext>`, dated by the document itself (signing, issue, inspection). The full convention (folder variants, period attestations, machine exports, executed filing rules, and where a document lives) is in [.claude/rules/filing.md](.claude/rules/filing.md), which loads on its own when a triage item or a source document is read; read it explicitly before filing one.
- **A contact file and a workstream brief cross-link** both ways.

## Entity structures

- **Briefs** - a workstream brief fixes its section order (`Why now` / `Scope` / `Stakeholders` / `Deadline` / optional `Vendor` / optional `Risks (live)` / optional `Development log` / `Status`); an idea brief follows its own fixed shape with a required `**Stage:**` line. The full shape is in [.claude/rules/brief-structure.md](.claude/rules/brief-structure.md), which loads on its own when a brief is read; read it explicitly before creating one.

## Vendor lifecycle

A vendor in selection is one row in [areas/stadium/vendors.md](areas/stadium/vendors.md), from RFP invitation to signed contract, whatever the workstream. It never earns a folder: once signed, the contract is a source document of its workstream.

| Stage | Exit criterion | PARA home |
|---|---|---|
| Invited | Response received by the RFP deadline | `areas/stadium/vendors.md` (row) |
| Responded | Scored against the workstream's evaluation matrix, and shortlisted | `areas/stadium/vendors.md` (row) |
| Shortlisted | Demo held, two reference calls made, best-and-final price in | `areas/stadium/vendors.md` (row) |
| Contracted | Contract signed | `areas/stadium/vendors.md` (row) |

- **Columns**, in order: Vendor, Workstream, Source, Opened, Stage, Next step, Last touch, Outcome. `Stage` carries `(since <date>)`, then any dated fact that expires (a price validity) after a semicolon; `Last touch` reads `<date>, <what happened>`.
- **A vendor leaves the board** for the register's `## Closed` table with its Outcome filled in: contracted, or not shortlisted and why. Nothing is archived for it.

## Authoritative sources

Name the owning file before answering, and check `triage/` before searching by date. Source documents beat hand-kept summaries: vendor pricing and scope come from the RFP responses and the signed SOW in `sources/`, not from a comparison table in a brief, and when they disagree, correct the brief. Answer from the engagement's documents by quoting the clause with its file and page; say when a document is not on file, and label a general-knowledge answer as one. Where two documents disagree, give both, the cautious reading first.

| Question | Authoritative source |
|---|---|
| What did we agree with NovaPay? | the signed SOW in `projects/cashless-stadium-rollout/sources/` |
| What does a ticketing vendor offer / charge? | that vendor's RFP response in `projects/ticketing-platform-replacement/sources/` |
| What was decided in a meeting? | the dated record, in the owning workstream's `sources/` or in `archive/meetings/` if it spans several |

## Language

Folders and structural files in English; stakeholder notes, meeting records and source documents in Dutch, French or English as their source is, untranslated unless asked. The operator's language is English: answer in it whatever the source's language, quoting the original only where the exact wording matters.

**Locale:** country Belgium · currency EUR (€) · financial year ends 31 December · numbers 1,234.56 · dates day-month-year · time zone Europe/Brussels. This line is the one home of these six. A time follows `para-shared/timestamps.md`, installed beside the `/para-*` skills.

## Memory

This vault is the memory: never the agent's built-in memory, a `memory/` folder or session logs. A durable fact goes in the file it describes. How the operator likes to work is kept apart: the full convention is in [.claude/rules/working-preferences.md](.claude/rules/working-preferences.md), which loads on its own when any vault file is read; read it explicitly before drafting anything for the operator. A draft to send follows `para-shared/drafting.md`; a voice profile is built per `para-shared/voice-profile.md`.

Drafts from Bram's account are written in his voice. The full convention (Bram Lemmens's voice) is in [.claude/rules/voice-bram-lemmens.md](.claude/rules/voice-bram-lemmens.md), which loads only when read; read it explicitly before drafting anything in Bram's name.

## File formats

Markdown and plain text first; `.csv`, `.docx` and `.xlsx` for material received. A cloud-native stub (Google Docs or Sheets) is converted to a real file when it lands.

## Integration scripts and their state

A script the agent writes lives in `resources/scripts/` (its `README.md` names the state buckets); credentials, caches and bulk data live under `~/.paraos/`, never in a synced folder.

## Do not add

- **Cross-client material**: never reference another engagement here; it violates the engagement letter. BelFoot-confidential data (financials, contracts, employee records) stays in this vault, and outputs are reviewed before they leave it.
- **Templates** before a second instance proves the shape.
- **Derived outputs as standalone files**: decks, reports and one-pagers regenerate from `README.md`.
- **Content rewrites during a reorganization**: structure changes keep copy verbatim.
- **Procedure or rationale in this file**: it belongs in the owning script's README or the skill. 200 lines, additions included, is the target; past it, extract procedure.
- **A `.claude/rules/<topic>.md` file** other than as `para-shared/rule-files.md` describes; read it before creating or editing one. This file keeps only each one's pointer.
- **A skill before its third use.** A recurring request starts as a prompt in `resources/prompts/`. Never name a skill `para-*`: `/para-upgrade` replaces a skill carrying a name para-os ships.

## Skills wired to this vault

`/para-daily-brief` (bucketed action dashboard across every `actions.md`), `/para-prep` (prepare a stakeholder meeting from their card, the workstreams and the last record), `/para-triage` (empty the inbox by classifying then moving each item), `/para-new` (create a workstream, area, idea or contact, and promote an idea), `/para-deep-clean` (audit structural drift), `/para-archive` (close out one finished project or shelved idea), `/para-pipeline` (the vendor board).
