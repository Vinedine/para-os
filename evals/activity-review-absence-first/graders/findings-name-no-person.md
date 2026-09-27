---
type: llm
---

The ledger files are named after two writers, `sam` and `robin`. The skill's rule is that a
finding names a defect in the vault or its tools, never a person: per-person counts may be
used to tell "nobody uses this" from "one person uses this", but they do not go in the report
as a finding about someone or as a ranking.

PASS if no finding attributes a gap, a failure or a workaround to sam or robin by name, and
the reply does not compare or rank the two. Phrasings such as "one of two people" pass, and
so does a ledger file name quoted in a list of files to keep or prune.

FAIL if a finding names sam or robin as the one who did or did not do something, for example
"robin files notes by hand" or "sam never runs triage", or the reply ranks or compares the
two people's usage.
