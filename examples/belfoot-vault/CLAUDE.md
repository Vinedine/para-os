# BelFoot Vault Conventions

**Type:** vault

The consulting vault for BelFoot Royal Sporting Club ("BelFoot FC", Belgian Pro League) and its multi-stream IT modernisation programme - an external consultant engagement, started Q1 2026, running through 2027.

The fixed para-os rules are in `.claude/para-os/core.md`, imported below: read it in full before anything else. It is the same in every vault and an upgrade replaces it whole. This file holds what is true of this vault only, and wins wherever it differs from the core.

@.claude/para-os/core.md

## Context

BelFoot internal data (financials, employee records, contracts) is confidential to this engagement. This vault is the consultant's working copy; outputs that leave it (decks, reports, emails) are reviewed before send. Never reference another client engagement here - cross-client context violates the engagement letter.

**This is a synthetic example vault with a frozen reference date of 2026-06-24** (see the top of `README.md`). Every date in it is internally consistent as of that day and anchored to match days. Do not "refresh" dates to the current calendar and do not treat the gap as drift to clean up. A brief reporting them overdue against today is correct, not a misread: judge the vault's *content* against 2026-06-24.

## PARA layout

- **projects/** - a project here is a time-bound IT workstream.
- **areas/** - `business/` is the area for work tied to no single entity: the stadium modernisation programme, its vendor register included. The wallet, the ticketing platform and the stadium network they share would form one area.

## Entity structures

- **Briefs** - a workstream brief fixes its section order (`Why now` / `Scope` / `Stakeholders` / `Deadline` / optional `Vendor` / optional `Risks (live)` / optional `Development log` / `Status`); an idea brief follows its own fixed shape with a required `**Stage:**` line. Read [.claude/rules/brief-structure.md](.claude/rules/brief-structure.md) before creating one.

## Vendor lifecycle

A vendor in selection is one row in [areas/business/vendors.md](areas/business/vendors.md), from RFP invitation to signed contract, whatever the workstream. It never earns a folder: once signed, the contract is a source document of its workstream.

| Stage | Exit criterion | PARA home |
|---|---|---|
| Invited | Response received by the RFP deadline | `areas/business/vendors.md` (row) |
| Responded | Scored against the workstream's evaluation matrix, and shortlisted | `areas/business/vendors.md` (row) |
| Shortlisted | Demo held, two reference calls made, best-and-final price in | `areas/business/vendors.md` (row) |
| Contracted | Contract signed | `areas/business/vendors.md` (row) |

- **Columns**, in order: Vendor, Workstream, Source, Opened, Stage, Next step, Last touch, Outcome. `Stage` carries `(since <date>)`, then any dated fact that expires (a price validity) after a semicolon; `Last touch` reads `<date>, <what happened>`.
- **A vendor leaves the board** for the register's `## Closed` table with its Outcome filled in: contracted, or not shortlisted and why. Nothing is archived for it.

## Authoritative sources

Here the RFP responses and the signed SOW in `sources/` are the record for vendor pricing and scope, never a brief's comparison table.

| Question | Authoritative source |
|---|---|
| What did we agree with NovaPay? | the signed SOW in `projects/cashless-stadium-rollout/sources/` |
| What does a ticketing vendor offer / charge? | that vendor's RFP response in `projects/ticketing-platform-replacement/sources/` |
| What was decided in a meeting? | the dated record, in the owning workstream's `sources/` or in `archive/meetings/` if it spans several |

## Language

**Locale:** country Belgium · currency EUR (€) · financial year ends 31 December · numbers 1,234.56 · dates day-month-year · time zone Europe/Brussels.

## Triage sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
| engagement mail | connector: mailserver | `bram@lemmens-advisory.example` | Threads with the BelFoot project team or its vendors. |
| steering calls | connector: notetaker recording | `bram@lemmens-advisory.example` | Calls whose title carries `BF`. |

## Agenda sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
| engagement calendar | connector: calendar | `bram@lemmens-advisory.example` | Meetings with a BelFoot attendee. |

## Pages

| Skill | Script |
|---|---|
| para-pipeline | `resources/scripts/vendor-board.py` |

## Do not add

- **Cross-client material**: never reference another engagement here; it violates the engagement letter. BelFoot-confidential data (financials, contracts, employee records) stays in this vault, and outputs are reviewed before they leave it.
