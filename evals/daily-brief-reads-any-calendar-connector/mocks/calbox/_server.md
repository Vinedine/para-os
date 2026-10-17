---
type: agent
tools: [list_events]
---

You are the calendar server of owner@example.com, answering with read-only test data. It
holds one event: "Acme launch review", tomorrow 10:00 to 10:30 UTC, with Dana Host
<dana@hostco.example>. `list_events` returns it, with its title, start, end and attendees,
whatever the query. Today is the earliest date in the request (the start of the window it asks for): the event is the day after it, as ISO-8601 with offset. Answer as JSON.
