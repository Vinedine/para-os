---
paths:
  - "**/actions.md"
  - "areas/network/*.md"
---

# Writing an action

Where a checkbox may live and which file an action goes in are in the core. This is how one is written.

## The actionable frontier

A checkbox is something you could act on now or on its marked date. A step behind an uncleared dependency stays prose (a `## Backlog` section or the brief) until its gate opens. A file holds at most 8 open items, waits on others aside: at 8, close or demote one first. Triage and working sessions add at most one next step per inbound item. An action's headline (its bold lead, or the whole line) stays under 120 characters, detail going to a sub-bullet or the brief; an item that moves is closed and its successor written as a new line.

## Task markers

`📅 YYYY-MM-DD` due, `🛫` start, `⏳` scheduled, `🔁 every <cadence>` recurring (with `📅` for the next occurrence), `🔺 🔼 🔽 ⏬` priority (none = medium), `✅ YYYY-MM-DD` done. Markers go at the end of the line, and a fuzzy date ("Q4") becomes one concrete marker. A `📅` is a real-world deadline; work gated on an outside event stays undated. One `## Recurring` section per file. Something owed by someone else is `- [ ] Waiting on [<person>](<card>): <what> (since YYYY-MM-DD)`, with no `📅`.

## A contact card

Relationship context, an optional `## History`, then `## Next actions` from the card's first action on, then any `## Backlog`. A shared workstream lives in the primary contact's file; the others point to it.
