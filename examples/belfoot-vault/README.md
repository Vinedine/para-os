# BelFoot engagement vault

Master document for the BelFoot IT modernisation engagement. Single source of truth for the engagement's scope, stakeholders, and track record; derived outputs (decks, status one-pagers, reports) regenerate from it.

> **Reference date: 2026-06-24.** This is a fixed synthetic vault, so every date in it is frozen at that Wednesday in late June 2026. Its dates are deliberately *not* refreshed to match the calendar: the fiction is anchored to real match days (soft launch Sunday 2026-08-02, season opener Sunday 2026-08-09), and sliding everything forward would break that anchor and re-age within weeks anyway. Read whatever `/para-daily-brief` reports as "overdue" against 2026-06-24, not against today - the further past that date you are, the redder the dashboard looks. To see the buckets spread across 🔴 / 🟠 / 🟡 the way a live vault would, shift every date in the vault forward by the gap between 2026-06-24 and today.

## Identity

External consultant engagement for **BelFoot Royal Sporting Club** ("BelFoot FC"), a Belgian Pro League football club. Engaged Q1 2026 as programme lead for the club's multi-stream IT modernisation, running through 2027. Single consultant (Bram), reporting to the Managing Director; day-to-day counterpart is [Sofie Vanhove](areas/network/sofie-vanhove.md) (IT Director).

## Operating model

One programme, multiple time-bound workstreams, each run as a project with its own brief, task list, and source documents:

- **[Cashless stadium rollout](projects/cashless-stadium-rollout/brief.md)** - replace cash at every stadium sales point with a closed-loop wallet before the 2026-27 season opener (2026-08-09). Vendor: NovaPay.
- **[Ticketing platform replacement](projects/ticketing-platform-replacement/brief.md)** - replace the 2014 legacy ticketing platform; vendor selection by 2026-09-15, phased cutover through 2027.
- **[Fan app rebuild](resources/ideas/fan-app-rebuild/brief.md)** - concept-stage idea, dependent on the ticketing replacement landing first; not yet a project.

Cross-cutting programme work (budget envelope, dependency mapping, board reporting) lives in [areas/stadium/actions.md](areas/stadium/actions.md). Stakeholder relationships live one file per person in [areas/network/](areas/network/): [Jan Claes](areas/network/jan-claes.md) (CFO), [Pieter De Ryck](areas/network/pieter-de-ryck.md) (Head of Operations), [Sofie Vanhove](areas/network/sofie-vanhove.md) (IT Director), [Thomas Vermeulen](areas/network/thomas-vermeulen.md) (Commercial Director). Dated meeting records land in [archive/meetings/](archive/meetings/).

## Track record

- **2026-04-18** - NovaPay contract signed for the cashless rollout (SOW on file in the project's `sources/`).
- **2026-05-15** - Ticketing RFP issued to four shortlisted vendors after a clean legal review; all four responses received by the 2026-06-20 deadline.
- **2026-05-22** - Q3 budget overrun (~€85k) on the cashless rollout flagged with the CFO; three cost-recovery options delivered 2026-05-29, decision pending.
- **Currently** (2026-06-24, the vault's reference date): cashless rollout on track for the 2026-08-02 soft launch, slipping on budget; ticketing in vendor selection with demo days the week of 2026-07-06.

## Working in this vault

- **Conventions for Claude:** [CLAUDE.md](CLAUDE.md).
- Run `/para-daily-brief` for a bucketed view of what's open across the vault.
