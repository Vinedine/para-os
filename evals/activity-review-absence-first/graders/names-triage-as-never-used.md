---
type: llm
---

The vault's `CLAUDE.md` names four skills: `/para-triage`, `/para-new`, `/para-archive` and
`/para-daily-brief`. Its activity ledger covers thirteen days: `/para-daily-brief` is invoked
in five sessions, `/para-new` once, and `/para-triage` and `/para-archive` never, while
`triage/` holds six unfiled notes and one session filed a note by hand.

PASS if the reply reports `/para-triage` as never invoked in the window and ties that to the
notes piling up in `triage/`, with a change to make about it.

FAIL if the reply does not mention `/para-triage` as unused, reports it as used, or mentions
it only in a list of skills with no finding or change attached.
