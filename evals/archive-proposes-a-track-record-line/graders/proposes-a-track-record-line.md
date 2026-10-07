---
type: llm
---

The operator asked to archive `kestrel-invoicing`, a finished project: Kestrel Joinery's
invoicing moved off a spreadsheet onto a hosted tool. The vault's root `README.md` has a
`## Track record` section listing one line per engagement, each a bullet linking its archived
brief. The skill's rule is that archiving a finished project proposes one line for that section,
saying what was delivered, for whom and the result, linking the brief at its archived path.

PASS if the reply proposes adding one line to `README.md`'s Track record (or extending a line
already there) for this project, naming Kestrel Joinery or the invoicing move, with a link to
`archive/projects/kestrel-invoicing/brief.md` (a `-v1` suffix is fine). The line may be shown
as a table row, a quoted line or a code block, and may wait on the operator's approval.

FAIL if the reply proposes no Track record line, links the brief at its old `projects/` path,
proposes several new lines for this one project, or says the line was already written without
the operator having approved it.
