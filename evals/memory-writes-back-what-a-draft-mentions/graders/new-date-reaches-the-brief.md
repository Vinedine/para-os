---
type: llm
---

The operator asked for a draft and, in passing, said the first corporate hospitality match on
the new ticketing platform moved to 2027-03-01, then signed off for the day. The ticketing
project's `brief.md` still gives 2027-02-01 under its Deadline section.

PASS if the reply writes 2027-03-01 into the ticketing brief, or asks the operator directly
whether to write it now, naming the brief and the new date.

FAIL if the reply leaves the brief unchanged and only flags that it is out of date, offers
the edit for later ("say the word", "if you want", "I can", "next session"), or records the
date somewhere other than the brief.
