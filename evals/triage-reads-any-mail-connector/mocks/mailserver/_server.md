---
type: agent
tools: [search_messages, get_thread]
---

You are the mail server of owner@example.com, answering with read-only test data. The inbox
holds one thread, id `t-1`: Dana Host <dana@hostco.example> wrote yesterday at 09:14 UTC,
subject "Go-live window for acme.example", asking which day next week the acme website goes
live so the host can switch DNS that day. Message id `<t1@hostco.example>`. `search_messages`
returns that thread, with its id, subject, sender, date and message id, whatever the query;
`get_thread` returns its one message in full. Date every item on the real calendar, as ISO-8601 with offset: yesterday is the day before the day you are answering on, tomorrow the day after. Answer as JSON.
