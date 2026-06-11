# BelFoot engagement vault

**Type:** vault (default flavor: plain editable markdown)

BelFoot FC (Belgian Pro League). Vincent's external consultant vault for the multi-stream IT modernisation programme. Started Q1 2026; runs through 2027.

## PARA layout

- **triage/** - capture area for unprocessed artifacts before they get filed (call notes, screenshots, meeting transcripts, scanned docs, ad-hoc thoughts). Process via `/triage`.
- **projects/** - time-bound IT workstreams with a committed deliverable and deadline. One folder per workstream.
- **areas/stadium/** - the stadium modernisation programme as an ongoing responsibility: cross-cutting strategic actions not tied to a single project workstream.
- **areas/network/** - one file per BelFoot stakeholder. Relationship context at top, `## Next actions` at the bottom.
- **resources/** - reusable reference (procurement templates, vendor evaluations, regulatory notes).
- **archive/meetings/** - dated meeting records, named `YYYYMMDD Description.md`.

## Project folder shape

Every project folder under `projects/` follows the same anatomy:

- `brief.md` - what the project is, who it's for, scope, stakeholders, deadline.
- `actions.md` - the task list, with Obsidian Tasks markers (see below).
- `sources/` - raw source material: RFP PDFs, vendor decks, scanned contracts.

## Obsidian Tasks markers

`actions.md` files use these markers (parsed by `/daily-brief`):

- `📅 YYYY-MM-DD` - due date (hard deadline)
- `🛫 YYYY-MM-DD` - start date (not actionable until then)
- `⏳ YYYY-MM-DD` - scheduled work date
- `🔁 every <cadence>` - recurring (pair with `📅`)
- `🔺 🔼 🔽 ⏬` - priority (highest to lowest)
- `✅ YYYY-MM-DD` - completion

Place markers at the end of the line: `- [ ] Review vendor scoring matrix 📅 2026-06-10`

## Stakeholder filing

- **Per-stakeholder notes**: `areas/network/<firstname-lastname>.md`, kebab-case, no diacritics.
- **Shared workstreams**: track actions in the primary stakeholder's file; cross-link from the others.
- **Meetings with multiple stakeholders**: file as `archive/meetings/YYYYMMDD <description>.md`, append a one-liner to each attendee's contact file.

## Privacy guardrails

- BelFoot internal data (financials, employee records, contracts) stays in this vault.
- Never reference other client engagements in this vault. Cross-client context is a violation of the engagement letter.
- Outputs leaving the vault (decks, reports, emails) get reviewed before send.

## Skills available

- `/daily-brief` - bucketed action dashboard across every `actions.md`.
- `/triage` - empty the inbox by classifying then moving each item.
- `/deep-clean` - audit structural drift.

## MCPs configured for this engagement

- Atlassian (JIRA + Confluence) for the BelFoot programme board.
- Google Workspace for the shared engagement Drive.
- ODOO (read-only) for invoice cross-reference.
