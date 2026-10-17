---
type: llm
focus: trace
---

The run read a mailbox holding a thread with Rosa. In message `<p2@mail.example>`, sent on a
Friday, the owner promised her a price "Wednesday". The promise is due the first Wednesday
after that message's own date: five days after the date in its `received` field.

PASS if the run's final reply proposes an action to send Rosa the price dated `📅` on that
Wednesday.

FAIL if the price action carries another date, carries none, or the final reply proposes no
such action.
