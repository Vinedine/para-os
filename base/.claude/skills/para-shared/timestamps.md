# Reading a timestamp (shared across skills)

A time read from outside the vault (a calendar event, a mail's received time, a recording's start) is an instant, shown and written in the zone the vault's `**Locale:**` line declares.

- **Convert from the timestamp's own offset into the declared zone**; the wall-clock digits are not the time (`14:00Z` is `16:00` two hours ahead).
- **A day taken from a timestamp is its day in the declared zone**: an agenda's Today, a filed document's date, a row's last touch.
- **An offset contradicting the zone label beside it** is reported with both named, not resolved by picking one. **A timestamp with no offset** is read in the zone its label names; with no label either, it is shown as written and said to be no instant.
- **With no time zone declared**, convert into the session's own zone and say once that the vault declares none.
- **A comparison never takes the declared zone**: a watermark compares as an instant and a content key takes its received time in UTC ([connectors.md](connectors.md) steps 5 and 6).
