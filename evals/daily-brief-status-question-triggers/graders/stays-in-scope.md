---
type: llm
---

The question is about one project, acme-website. Its open items are in
`projects/acme-website/actions.md`. The vault also holds a para-os release project and a
business area with their own open items; one item in a contact file mentions acme without
belonging to the project.

PASS if every item the reply presents as open work for acme comes from
`projects/acme-website/actions.md`, and the reply does not list the release project's or the
business area's items as part of the answer.

FAIL if it lists another entity's items as acme's open work, or answers with a whole-vault
overview.
