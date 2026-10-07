---
type: llm
---

The triage folder holds one scanned letter from the tax office, dated the 1st of this
month, asking for purchase invoices and an explanation by a reply-by date on the 28th of
next month. No open action in the vault tracks it. The business's own actions live in
`areas/business/actions.md`.

PASS if the reply proposes filing the letter under `areas/business/` and, for the same item,
shows in full the one action line it would add to `areas/business/actions.md`: a checkbox
about replying to the tax office or sending the documents, carrying `📅` on the reply-by date
the reply gives for the letter, and a link to the letter at the path it would be filed to.

FAIL if no action line is shown, if the line carries no `📅` or one on the letter's own date,
if it has no link to the filed letter, or if the letter gets more than one new checkbox.
