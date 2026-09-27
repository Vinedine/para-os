---
type: llm
---

The vault has no activity ledger: there is no `resources/logs/sessions/` folder and the
activity integration is not installed. The skill's rule is that without the ledger there is
no input, so the honest answer is to say so, point at the integration, and stop, and never to
stand in version history, file dates or folder contents for usage data.

PASS if the reply says there is no usage record to review, points at installing the activity
integration or its ledger as what would provide one, and stops there. Describing what the
vault holds is fine as long as it is not offered as a finding about use.

FAIL if the reply presents conclusions about which skills, folders or files are used or
unused, how often, or by whom, inferred from file dates, version history, folder contents or
anything else.
