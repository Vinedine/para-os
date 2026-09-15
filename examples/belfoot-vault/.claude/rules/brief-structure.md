---
paths:
  - "projects/*/brief.md"
  - "areas/*/brief.md"
  - "resources/ideas/*/brief.md"
  - "archive/**/brief.md"
---

# Brief structure

**Order:** fixed for a workstream brief. An idea brief follows its own, different fixed shape. This vault has no area brief to fix an order for.

## The shape

Two shapes recur, grounded in the three briefs this vault holds.

**Workstream briefs** (`projects/cashless-stadium-rollout/brief.md`, `projects/ticketing-platform-replacement/brief.md`) agree, heading for heading, on a fixed core: a title, one mission paragraph with no heading of its own, then `## Why now`, `## Scope` (an `In:` / `Out:` pair of lists), `## Stakeholders`, `## Deadline`, and `## Status` last. Between `## Deadline` and `## Status`, a workstream adds whichever of `## Vendor` (once one is under contract) and `## Risks (live)` (once a live risk exists) apply to it - both present in `cashless-stadium-rollout`, both absent from `ticketing-platform-replacement` because it has signed neither a vendor nor logged a live risk yet. Their absence there is not a gap to fill; add either section only once the fact it would hold actually exists.

**Idea briefs** (`resources/ideas/fan-app-rebuild/brief.md`) open with a `**Stage:**` line directly under the title, then a blockquoted one- or two-line context note (why it's parked, what it depends on, when to revisit), then the concept paragraph, `## Why now`, `## Possible scope`, `## Open questions`, `## Dependencies`, and `## Stakeholders (provisional)`. The closing line states the revisit trigger as prose, not a `📅` - nothing here is a committed date yet.

## Placeholders

None declared. An optional workstream section (`## Vendor`, `## Risks (live)`) with nothing to report is omitted outright rather than marked `_n/a_` - it doesn't exist until the fact behind it does. The vault's `_None currently._` placeholder belongs to a contact file's `## Next actions` (see `CLAUDE.md`), not to a brief.
