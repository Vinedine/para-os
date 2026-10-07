---
type: llm
---

The mailbox holds one thread. Rosa asked for a price on a Thursday; the operator answered
the next day, a Friday, "price to you Wednesday"; Rosa's reply that same Friday afternoon
thanks them and is otherwise about a talk at a meetup. Nothing shows the price was sent. The
Wednesday the operator promised is five days after their Friday message.

PASS if the reply proposes, for this thread, one action (Add action or Update existing) to
send Rosa or Orchard Labs the price, carrying `📅` on the promised Wednesday: five days after
the date the reply gives for the operator's message, or, where it gives none, a date it
names as that Wednesday. Quoting "price to you Wednesday" is expected but not required.

FAIL if the thread is dismissed or left with no action, if the only action is to answer
Rosa's remark about the talk, if the action carries no `📅`, or if its `📅` is the date of
any message in the thread or any day other than that Wednesday.
