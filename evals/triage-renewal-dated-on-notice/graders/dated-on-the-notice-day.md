---
type: llm
---

The triage folder holds one insurance policy schedule. The policy renews automatically for a
further year on the date it gives, the 1st of a month about five months away, unless either
party gives written notice at least three months before that date. No open action tracks
it, and the business's actions live in `areas/business/actions.md`.

PASS if the reply proposes filing the schedule under `areas/business/` and shows one action
line for it whose `📅` is exactly three calendar months before the renewal date (the 1st of
the month three months earlier), and whose text names the renewal date, in any format. A
`🔁 every year` marker on the line is fine.

FAIL if no action line is proposed, if the line's `📅` is the renewal date itself or any
other day, if it carries no `📅`, or if the renewal date is missing from the line's text.
