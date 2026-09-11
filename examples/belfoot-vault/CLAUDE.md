# BelFoot Vault Conventions

<!-- para-os-template: 2026.09.02 -->
**Type:** vault (default flavor: plain editable markdown)

The consulting vault for BelFoot Royal Sporting Club ("BelFoot FC", Belgian Pro League) and its multi-stream IT modernisation programme - an external consultant engagement, started Q1 2026, running through 2027. Per-vault guidance for Claude Code sessions.

Both lines above are machine-read (the comment by `/para-upgrade`, the type by your own tooling) and must survive every upgrade.

## Context

BelFoot internal data (financials, employee records, contracts) is confidential to this engagement. This vault is the consultant's working copy; outputs that leave it (decks, reports, emails) are reviewed before send. Never reference another client engagement here - cross-client context violates the engagement letter.

**This is a synthetic example vault with a frozen reference date of 2026-06-24** (see the top of `README.md`). Every date in it is internally consistent as of that day and anchored to real match days. Do not "refresh" dates to the current calendar and do not treat the gap as drift to clean up. A brief reporting them overdue against today is correct, not a misread: judge the vault's *content* against 2026-06-24.

## PARA layout

The sorting test between buckets: **committed and dated → project. Maintained, no end date → area. Only thinking about it → idea. Over → archive.**

- **triage/** - unprocessed artifacts before they get filed (call notes, screenshots, meeting transcripts, scanned docs, ad-hoc thoughts), emptied via `/para-triage`. Never a `README.md` here (it would count as an item forever); a `.gitkeep` holds the folder in git.
- **projects/** - time-bound IT workstreams with a committed deliverable and deadline, one folder per workstream, each holding a `brief.md` (what it is, who it's for, scope, stakeholders, deadline), an `actions.md`, and a `sources/` subfolder for raw material (RFP PDFs, vendor decks, scanned contracts). A workstream needs a committed deliverable **and** a date; a rolling improvement backlog on a system the club already runs is an area wearing a project name.
- **areas/** - ongoing responsibilities with no end date. `stadium/` = the stadium modernisation programme as a standing responsibility: cross-cutting strategic actions not tied to a single workstream. `network/` = one file per BelFoot stakeholder. Systems that gate each other (the wallet, the ticketing platform it integrates with, the stadium network both depend on) stay **one** area.
- **resources/** - reusable reference (procurement templates, vendor evaluations, regulatory notes), never a checkbox. `prompts/` = reusable specs and drafts. `ideas/` = one folder per concept-stage workstream: a `brief.md` holding open questions plus at most one prose "revisit when X" trigger, and a `sources/` where real documents back it (it travels with the idea on promotion). `scripts/` = persistent tools; their runtime state lives *outside* the vault (see below).
- **archive/** - inactive artifacts, always in a subfolder. `meetings/` = conversation records spanning several entities. `projects/` = completed workstreams and `ideas/` = shelved concepts (both filled by `/para-archive`).

Root `README.md` is the master document, single source of truth for identity, operating model, and track record; derived outputs regenerate from it. Its first four `##` headings are exactly `Identity`, `Operating model`, `Track record`, `Vision`, in that order and in English whatever the body language, and Vision is never a stub; vault-specific sections follow, an optional `## Principles` (standing decisions not to relitigate) among them. It carries no work state in any syntax - no checkbox, `📅` marker, status list, deadline table, Status column, or prose standing in for one (_to confirm_, _still to settle_): live state belongs in `projects/` and `areas/`. A status *fact* about the vault's subject (`| Status | Active |` beside a registration number) is not work state and stays.

### Lifecycle

- `/para-new` **creates** a workstream, area, idea, or contact, settling its shape against the sorting test before scaffolding anything.
- An idea **promotes** to `projects/` when someone waits on a deliverable by a date, money or a formal engagement is committed, or a go/no-go review is on the calendar; it earns its `actions.md` then, not before. Retiring an idea is always the operator's call, never automatic: one that never happened goes to `archive/ideas/`, one where real work ran and then stopped goes to `archive/projects/`.
- The next big, dated push on a maintained asset is a **project running alongside its area**; when it archives, surviving work returns to the area.
- An entity **archives whole** (brief, actions, sources) via `/para-archive`, with open items routed out *first* to the owning area, a successor project, or the contact file.
- **Every move repoints inbound links in the same pass**, not just archiving. `/para-deep-clean` audits for dangling links.

### Archive hygiene

Applied on the way in, audited by `/para-deep-clean`:

- **No live work in the archive.** Zero open actions: every item done, or softened to an explicit "fully closed; minor gaps not material" note.
- **History archives; living references go to `resources/<name>/`.** Playbooks, procurement templates, anything other live work links to.
- **No loose files at the archive root.** Everything lives in a subfolder.
- **Minimum record.** A status marker saying why it is archived, plus its `brief.md`/`README.md`.
- **Zero dangling links.** No inbound reference still points at the pre-archive path; a historical mention *inside* the archived folder is fine.

## Actions

### Where a checkbox may live

A checkbox is a commitment, so the bucket a file sits in decides whether it may hold one.

| Bucket | `actions.md` | State |
|---|---|---|
| `projects/`, `areas/` | yes | open + closed |
| `resources/` | **never** | a checkbox here is a filing error |
| `archive/` | yes | **all closed** - one open `- [ ]` means it was archived too early |

A dated go/no-go on an idea is a strategic action in `areas/stadium/actions.md`, linking to the idea; a stakeholder follow-up lives in that person's contact file; scheduled multi-step work means the thing is a workstream, not an idea.

### The actionable frontier

A checkbox is something you could act on now or on its marked date, not a plan. Steps whose dependencies have not cleared stay prose (a `## Backlog` section in the same file, or the brief) and become checkboxes when their gate opens. Before appending to a file that already holds 12 or more open items, say so and propose grooming instead of adding. Triage and working sessions add at most one next step per inbound item, never a decomposition.

### The content frontier

- **Say it once.** Every fact has one owning file; elsewhere it is a link, never a copy.
- **A development log records decisions, not activity.** A decision and why, a constraint found, a route rejected. "Continued work on X" is not an entry.
- **Superseded content leaves the live buckets** for `archive/` or git history.
- **Never delete to satisfy this.** Pruning is proposed and ruled on one item at a time; the default is *move* or *demote*, and deletion applies only to a genuine duplicate whose contents were compared against the surviving copy. Source documents and `triage/` are never pruned.

### Which file an action goes in

- With the workstream or area it belongs to: `projects/<x>/actions.md`, `areas/<x>/actions.md`.
- Per-stakeholder actions in the contact file under `## Next actions`.
- Strategic work tied to no single entity in `areas/stadium/actions.md`. Never a root `actions.md`.
- An `actions.md` archives *with its entity*, fully closed, never on its own.

### Task markers (Obsidian Tasks syntax)

`📅 YYYY-MM-DD` due, `🛫` start, `⏳` scheduled, `🔁 every <cadence>` recurring (pair with `📅` for the next occurrence), `🔺 🔼 🔽 ⏬` priority (medium = no marker, `🔺` rare), `✅` completion (auto-filled). Markers go at the end of the line; free-text and fuzzy dates ("Q4") become one concrete marker. A `📅` records a real-world deadline (someone expects it, something renews), never an aspiration; work gated on an external event stays undated. One flattened `## Recurring` section per file.

## Filing and naming

- **Contacts**: one file per stakeholder at `areas/network/<firstname-lastname>.md` (kebab-case, no diacritics). Relationship context at the top, `## Next actions` at the bottom, `_None currently._` when empty. A shared workstream is tracked in the primary stakeholder's file; the others carry a pointer line.
- **Dated conversation records** (meeting notes, transcripts, chat/email sequences): to the `sources/` of the owning workstream or area; `archive/meetings/YYYYMMDD Description.md` only when they span several entities.
- **Source documents**: `sources/YYYYMMDD <Who> <Description>.<ext>` - the date of the document itself (signing, issue, inspection), not the received date.
- **Brief and relationship**: the contact file is the relationship summary; the workstream folder holds the brief and execution detail. Cross-link both ways.

## Authoritative sources

Name the owning surface *before* answering. Check `triage/` before searching by date: an item waiting to be filed is usually the current one. Source documents beat hand-maintained summaries in briefs: vendor pricing and scope come from the RFP responses and the signed SOW in `sources/`, not from a comparison table typed into a brief, and when they disagree the source document wins and the brief gets corrected.

| Question | Authoritative source |
|---|---|
| What did we agree with NovaPay? | the signed SOW in `projects/cashless-stadium-rollout/sources/` |
| What does a ticketing vendor offer / charge? | that vendor's RFP response in `projects/ticketing-platform-replacement/sources/` |
| What was decided in a meeting? | the dated record, in the owning workstream's `sources/` or in `archive/meetings/` if it spans several |

## Language

Folders and structural files in English. Stakeholder notes, meeting records, and source documents may be in Dutch, French, or English, matching the source; don't translate unless asked. The operator's language is English: explain, summarize, and answer in it whatever the source document's language, quoting the original only where the exact wording is load-bearing (a contract clause, a term of art, a figure).

## Memory

This vault on disk IS the memory. Do not use the agent's built-in memory feature, and do not create a `memory/` folder or session-log files. Durable facts belong in the file they describe: conventions here, scope and stakeholders in `README.md`, everything else in the relevant workstream, idea, or contact note.

## File formats

Markdown and plain text first; `.csv`/`.docx`/`.xlsx` for material received from others. Cloud-native pointer formats (Google Docs/Sheets) sync as stubs whose bytes are often not local, so the agent frequently cannot read them; convert one to a real file when it lands.

## Integration scripts and their state

A persistent script the agent writes for this vault lives at `resources/scripts/`. Its credentials, caches, and bulk data live under `~/.paraos/`, never inside a folder that syncs. `resources/scripts/README.md` carries the state buckets and the `PARAOS_HOME` resolver.

## Do not add

- **Cross-client material**: never reference another engagement here; it violates the engagement letter. BelFoot-confidential data (financials, contracts, employee records) stays in this vault, and outputs are reviewed before they leave it.
- **Templates** before a second instance proves the shape.
- **Derived outputs as standalone files**: decks, reports, one-pager text regenerate from `README.md`.
- **Content rewrites during reorganization**: structure changes preserve copy verbatim; fix wording in a later pass.
- **Procedure and rationale in this file.** A rule governing a script lives in that script's README or docstring, the mechanics of a skill live in the skill, and the reason behind a rule lives in git history. This file states rules. 200 lines including everything the vault adds is the **target**; past it the lever is extracting procedure - to `.claude/rules/`, to the owning script or skill - never cutting the rules the vault itself needs.

## Skills wired to this vault

`/para-daily-brief` (bucketed action dashboard across every `actions.md`), `/para-triage` (empty the inbox by classifying then moving each item), `/para-new` (create a workstream, area, idea or contact, and promote an idea), `/para-deep-clean` (audit structural drift), `/para-archive` (close out one finished project or shelved idea).
