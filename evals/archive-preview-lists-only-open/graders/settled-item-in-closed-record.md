---
type: llm
---

The project's `actions.md` ends with a `## Backlog` item that already carries its outcome: a
bold "Decided" line recording that the custom bulk-import script was skipped because the hosted
importer handled the volume. The skill's rule is that a Backlog item carrying a Done, Decided
or Resolved line is settled: it stays with the archived project as part of its closed record,
and is never treated as open work.

PASS if the reply says the settled item stays with the archived project, however it refers to
it (the bulk-import decision, the Decided line, a Backlog decision note) and in any wording:
listed as settled or decided among the actions, described as a decision record that stays with
the project, or listed, even in passing, as a decision note among the contents of an
`actions.md` that the reply moves into the archive.

FAIL if the reply counts it as open or unresolved, proposes routing, dropping or deleting it,
recommends an archive that loses it, or never says what becomes of it. A reply that cites the
Decided line only as a format to copy for another item has not said.

Judge only what the reply says becomes of the item. Whether it also asks the operator about it
is a separate check.
