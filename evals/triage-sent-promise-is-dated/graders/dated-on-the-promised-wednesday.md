---
type: llm
---

The run read a mailbox thread in which the owner, on a Friday, promised Rosa a price
"Wednesday". The promise is due the first Wednesday after the day that message was sent,
five days later.

PASS if the reply proposes an action to send Rosa the price, dated `📅` five days after the
date the reply gives for the owner's message.

FAIL if the price action carries another date or none, if the reply gives no date for the
owner's message, or if it proposes no such action.
