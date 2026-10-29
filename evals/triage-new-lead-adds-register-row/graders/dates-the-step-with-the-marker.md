---
type: llm
---

The triage folder holds one staged mail: Sara Lindqvist of Lindqvist Dental asks for a
30-minute intro call on a given date. The run should propose a new row for the lead register
`areas/business/leads.md`, whose columns are Company, Contact, Source, Opened, Stage,
Next step, Last touch, Outcome.

PASS if the proposed row's Next step cell carries its date as the `📅` marker followed by a
`YYYY-MM-DD` date.

FAIL if the row is not shown, if its Next step carries no date, or if it carries the date
only in another form: `on <date>`, `by <date>`, a weekday, or a bare date with no `📅`.
