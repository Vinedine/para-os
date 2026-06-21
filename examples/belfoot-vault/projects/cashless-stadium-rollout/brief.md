# Cashless stadium rollout

Replace cash at every food, drink, and merchandise point in the BelFoot stadium with a closed-loop cashless system before the 2026-27 season opener.

## Why now

- **Match-day cash handling cost** in 2024-25 was €640k (security, counting, banking, theft loss). Removing it is the headline saving.
- **Queue times** at concessions average 8 min at half-time. Cashless median is sub-90 seconds per transaction at comparable venues.
- **Data.** Cash transactions are invisible; cashless gives per-stall, per-match SKU-level data we currently buy from a third-party panel.
- **Regulator pressure.** New Belgian anti-money-laundering reporting (effective Jan 2027) adds onerous cash-handling audit duties.

## Scope

In:

- Closed-loop wallet on the existing season-ticket NFC chip + a top-up app for non-members.
- Replacement of all 47 concession terminals + 12 merchandise terminals.
- Stadium-wide payment network (LAN + 4G fallback).
- Top-up kiosks at each gate + an online top-up route.
- Refund/dispute flow.

Out:

- Outside-the-stadium retail (club shops, online merch). Those stay on existing payment processors.
- Replacement of the loyalty programme itself (separate workstream).

## Stakeholders

- **[Jan Claes](../../areas/network/jan-claes.md)** (CFO) - budget owner, weekly check-ins.
- **[Pieter De Ryck](../../areas/network/pieter-de-ryck.md)** (Head of Operations) - match-day delivery owner.
- **[Sofie Vanhove](../../areas/network/sofie-vanhove.md)** (IT Director) - integration owner.
- **[Thomas Vermeulen](../../areas/network/thomas-vermeulen.md)** (Commercial Director) - sponsor / partner alignment.

## Deadline

- Hardware install complete: 2026-07-15.
- Soft-launch friendly match: 2026-08-02.
- Full season opener live: 2026-08-09.

## Vendor

NovaPay (Antwerp). Contract signed 2026-04-18. SOW on file at `sources/20260418 NovaPay Statement of Work.md`.

## Risks (live)

- **Network coverage** at the south stand is unreliable; 4G fallback hardware still on order.
- **Q3 budget overrun** flagged by Jan Claes at the 2026-05-22 meeting (~€85k over). Cost-recovery option due to him by Friday.
- **Season-ticket NFC chip** firmware refresh has a 6-week lead time and we haven't started.

## Status

On track for soft launch, slipping on budget. See [actions.md](actions.md) for the live task list.
