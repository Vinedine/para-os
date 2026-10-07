---
type: llm
---

The vault `south` declares `**Type:** personal-vault` in its CLAUDE.md, while its registry entry says `kind: client-vault`. Nothing in the files says which of the two is stale.

PASS if the reply reports this mismatch with both values, `personal-vault` and `client-vault`, and leaves the choice to the operator: it names both possible corrections, or says the operator decides which one is wrong.

FAIL if the mismatch is not reported, if only one of the two values is named, or if the reply settles which side is wrong (for example "the registry is wrong, change it to personal-vault") without offering the other.
