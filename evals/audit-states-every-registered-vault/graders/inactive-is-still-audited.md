---
type: llm
---

The registry marks the vault `south` as `active: false`. That flag only takes a vault out of mail ingest; an audit still reads it like any other vault.

PASS if the reply audits south: it appears among the audited vaults (a table row, or its own findings, such as its type mismatch or its CLAUDE.md size).

FAIL if south is reported as excluded, skipped or not audited because it is inactive, or is not mentioned at all.
