# BelFoot Vault Conventions

**Type:** vault (default flavor: plain editable markdown)

The consulting vault for BelFoot FC (Belgian Pro League) and its multi-stream IT modernisation programme - an external consultant engagement, started Q1 2026, running through 2027. Per-vault guidance for Claude Code sessions.

## Context

BelFoot internal data (financials, employee records, contracts) is confidential to this engagement. This vault is the consultant's working copy; outputs that leave it (decks, reports, emails) are reviewed before send. Never reference another client engagement here - cross-client context violates the engagement letter.

## PARA layout

- **triage/** - capture area for unprocessed artifacts before they get filed (call notes, screenshots, meeting transcripts, scanned docs, ad-hoc thoughts). Process via `/para-triage`.
- **projects/** - time-bound IT workstreams with a committed deliverable and deadline, one folder per workstream. Each holds a `brief.md` (what it is, who it's for, scope, stakeholders, deadline), an `actions.md` (task list with Obsidian Tasks markers, see below), and a `sources/` subfolder for raw material (RFP PDFs, vendor decks, scanned contracts).
- **areas/** - ongoing responsibilities. `stadium/` = the stadium modernisation programme as a standing responsibility: cross-cutting strategic actions not tied to a single workstream. `network/` = one file per BelFoot stakeholder.
- **resources/** - reusable reference (procurement templates, vendor evaluations, regulatory notes). `prompts/` = reusable specs and drafts; `ideas/` = concept-stage workstreams with no committed outcome, same `brief.md` shape as a project for easy promotion.
- **archive/** - inactive artifacts. `meetings/` = dated meeting/chat/email records.

Promote `resources/ideas/<x>` to `projects/` when one of: someone is waiting on a deliverable by a date; money or a formal engagement is committed; a go/no-go review is on the calendar. Ideas with no traction at 6+ months retire to `archive/`.

Root `README.md` is the master document, single source of truth for the engagement's scope, stakeholders, and track record. Derived outputs regenerate from it.

## Filing rules

- **Contacts**: one file per stakeholder at `areas/network/<firstname-lastname>.md` (kebab-case, no diacritics). Relationship context at the top, `## Next actions` appended at the bottom.
- **Actions**: co-locate with the project or area they belong to. Per-project actions live in `projects/<workstream>/actions.md`; cross-cutting programme actions in `areas/stadium/actions.md`. Never create a monolithic root `actions.md`.
- **Dated meeting/chat/email artifacts**: `archive/meetings/YYYYMMDD Description.md`.
- **Source documents**: `sources/YYYYMMDD <Who> <Description>.<ext>` - the date of the document itself (signing, issue, inspection), not the received date.
- **Shared workstreams across stakeholders**: track actions in the primary stakeholder's file; the others get a pointer line.
- **Project brief + relationship**: the contact file is the relationship summary; the project folder holds the brief and execution detail. Cross-link both ways.

## Obsidian Tasks markers for actions.md files

Any `actions.md` file in this vault uses Obsidian Tasks plugin markers. The `/para-daily-brief` skill parses these with regex:

- `📅 YYYY-MM-DD` - due date (hard deadline)
- `🛫 YYYY-MM-DD` - start date (item not actionable until then)
- `⏳ YYYY-MM-DD` - scheduled (planned work date)
- `🔁 every <cadence>` - recurring (pair with `📅` for the next occurrence)
- `🔺 🔼 🔽 ⏬` - priority, highest to lowest. Medium = no marker. Use 🔺 sparingly.
- `✅ YYYY-MM-DD` - completion (auto-filled when ticked)

Rules when writing or editing tasks:

- Put markers at the end of the line: `- [ ] Review vendor scoring matrix 📅 2026-06-10`
- Replace free-text dates with markers (no "before Jun 10 📅 2026-06-10", just the marker)
- Convert fuzzy dates ("Q4", "summer") to concrete dates (usually end-of-quarter or end-of-season)
- For items gated on external events, leave undated. Do not invent dates.
- One flattened `## Recurring` section per file, not separate "quarterly" / "annually" headings.

Never archive an `actions.md` file: it must stay outside `archive/` to be picked up by `/para-daily-brief`.

## Language

Folders and structural files in English. Stakeholder notes, meeting records, and source documents may be in Dutch, French, or English, matching the source. Don't translate unless asked.

## Memory

This vault on disk IS the memory. Do not use the agent's built-in memory feature, and do not create a `memory/` folder or session-log files (`/AI/sessions/` and the like). The agent reads the vault fresh each session; the git history is the audit log. Durable facts belong in the file they describe: conventions in this `CLAUDE.md`, scope and stakeholders in `README.md`, and everything else in the relevant project or contact note. If you would otherwise save a memory, write the fact into the vault file it belongs to instead.

## File formats

The substrate is real, readable files. The agent works over what exists on disk as bytes, so prefer formats it can read and move directly: Markdown and plain text first (read and edited in place, and they diff cleanly in git), with `.csv`/`.docx`/`.xlsx` as the fallback for material received from others. Avoid cloud-native pointer formats (e.g. Google Docs/Sheets): they sync as stubs linking to content held on a server, so the bytes aren't local, tooling can't move or rename them, and the agent often can't read them at all. When one lands in the vault, convert it to a real file. A format the tooling can't touch is dead weight, the same way a junk folder is.

## Do not add

- **Cross-client material** - never reference another engagement here; it violates the engagement letter. BelFoot-confidential data (financials, contracts, employee records) stays in this vault, and outputs are reviewed before they leave it.
- **Templates** - don't create per-stakeholder or per-project templates preemptively. Wait until a second instance proves the shape, then document it here.
- **Derived outputs as standalone files** - decks, reports, one-pager text regenerate from `README.md`. Don't let them drift into separate sources of truth.
- **Content rewrites during reorganization** - structure changes preserve copy verbatim. Fix wording in a later, dedicated pass.

## Skills and MCPs wired to this vault

- Skills: `/para-daily-brief` (bucketed action dashboard across every `actions.md`), `/para-triage` (empty the inbox by classifying then moving each item), `/para-deep-clean` (audit structural drift), `/para-archive` (close out one finished project or shelved idea).
- MCPs: Atlassian (Jira + Confluence) for the programme board; Google Workspace for the shared engagement Drive; Odoo (read-only) for invoice cross-reference.
