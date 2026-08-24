# BelFoot engagement vault

Master document for the BelFoot IT modernisation engagement. Single source of truth for the engagement's scope, stakeholders, and track record; derived outputs (decks, status one-pagers, reports) regenerate from it.

> **Reference date: 2026-06-24.** This is a fixed synthetic vault, so every date in it is frozen at that Wednesday in late June 2026. Its dates are deliberately *not* refreshed to match the calendar: the fiction is anchored to real match days (soft launch Sunday 2026-08-02, season opener Sunday 2026-08-09), and sliding everything forward would break that anchor and re-age within weeks anyway. Read whatever `/para-daily-brief` reports as "overdue" against 2026-06-24, not against today - the further past that date you are, the redder the dashboard looks. To see the buckets spread across 🔴 / 🟠 / 🟡 the way a live vault would, shift every date in the vault forward by the gap between 2026-06-24 and today.

## Identity

External consultant engagement for **BelFoot Royal Sporting Club** ("BelFoot FC"), a Belgian Pro League football club. Engaged Q1 2026 as programme lead for the club's multi-stream IT modernisation, running through 2027. Single consultant (Bram), reporting to the Managing Director; day-to-day counterpart is [Sofie Vanhove](areas/network/sofie-vanhove.md) (IT Director).

## Operating model

One programme of time-bound IT workstreams, each run as a project with its own brief, task list, and source documents, across three domains: [stadium payments](projects/cashless-stadium-rollout/brief.md) (a closed-loop cashless wallet on the season-ticket NFC chip, replacing cash at every sales point), [ticketing](projects/ticketing-platform-replacement/brief.md) (an API-first platform replacing the 2014 system, integrated with the Salesforce CRM and the wallet), and [fan-facing digital](resources/ideas/fan-app-rebuild/brief.md) (the fan app rebuilt on the new ticketing API once it exists). Each workstream is vendor-delivered and consultant-led: the consultant runs selection, contracting, integration design, and cutover; the club's IT department operates the result.

Governance is a standing responsibility rather than a workstream: the budget envelope, cross-workstream dependencies, and board reporting are tracked in [areas/stadium/actions.md](areas/stadium/actions.md). Stakeholder relationships live one file per person in [areas/network/](areas/network/): [Jan Claes](areas/network/jan-claes.md) (CFO), [Pieter De Ryck](areas/network/pieter-de-ryck.md) (Head of Operations), [Sofie Vanhove](areas/network/sofie-vanhove.md) (IT Director), [Thomas Vermeulen](areas/network/thomas-vermeulen.md) (Commercial Director). A dated meeting record lands in its owning workstream's `sources/`, or in [archive/meetings/](archive/meetings/) when it spans several.

Out of scope, and living elsewhere: retail outside the stadium (club shops, online merchandise) stays on the club's existing payment processors, and the loyalty programme is a separate workstream outside this engagement.

## Track record

- **2026-04-18** - NovaPay contract signed for the cashless rollout (SOW on file in the project's `sources/`).
- **2026-05-15** - Ticketing RFP issued to four shortlisted vendors after a clean legal review; all four responses received by the 2026-06-20 deadline.
- **2026-05-22** - Q3 budget overrun (~€85k) on the cashless rollout flagged with the CFO; three cost-recovery options delivered 2026-05-29.

## Vision

By the end of 2027 the club runs a cashless stadium and a modern ticketing platform, with the fan app rebuilt on the new ticketing data, and the IT department operates all three without the consultant. The engagement ends when the last ticketing cutover is signed off and the programme is handed to [Sofie Vanhove](areas/network/sofie-vanhove.md)'s team.

Conventions in [CLAUDE.md](CLAUDE.md); `/para-daily-brief` for what is open.
