# Gather (Steps 2 and 3)

## Who attends

The agenda is `/para-daily-brief`'s, read by [its Step 5c](../../para-daily-brief/references/signals.md#step-5c-build-the-agenda). Leave out the operator (the calendar's own address, or the vault's principal), rooms and other resources, and anyone who declined.

- **A calendar event**: its attendees, each passed as `Name <address>`, or the address alone.
- **A `meetings.md` line, or an event listing nobody**: the people a field or the title names ("Weekly status with Jan"), as written. Naming nobody, ask who is coming.

## What the scan returns

**Null is not empty**: a null `mentions`, `records`, `unfiled` or `rows` was never searched (an `ambiguous` person, or a one-word name with no card).

## How much a match is worth

`matched_by` and `by` name how the person was found. Name the address a weak `email_name` match rests on, and weigh a `short name` (one word of the card's names that no other card carries) before quoting it.
