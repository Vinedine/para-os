---
type: llm
---

The para-os home holds no `operator.json`, so the scan cannot tell which person on studio's roster the operator is, and shows studio by its health only: its two overdue invoices are counted but not listed as urgent.

PASS if the reply says studio is shown by health only, or that its items are left out, and gives the reason: no `operator.json` names the operator, or the operator could not be identified on studio's roster.

FAIL if studio is shown without saying why its items are missing, if the reason given is something else, or if studio reads as having nothing urgent.
