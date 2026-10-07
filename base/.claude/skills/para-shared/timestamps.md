# Reading a timestamp (shared across skills)

A time read from outside the vault (a calendar event, a mail's received time, a recording's start) and then shown to the operator or written into the vault is an instant. It is shown in the zone the vault's `CLAUDE.md` declares: `time zone` on its `**Locale:**` line.

- **Convert from the timestamp's own offset into the declared zone.** Never read the wall-clock digits off it: `14:00Z` is `16:00` in a zone two hours ahead, and printing `14:00` puts the operator two hours off.
- **A day taken from a timestamp is its day in the declared zone**: an agenda's Today, a filed document's date, a register row's last touch. Near midnight it is not the day the digits show.
- **An offset contradicting the zone label beside it** (an event labelled with one zone, carrying an offset that zone does not have on that date) is reported with both named, never resolved by picking one.
- **A timestamp with no offset** is read in the zone its label names. With no label either, it is not an instant: show it as written, and say so.
- **With no time zone declared**, convert into the session's own zone and say once that the vault declares none.
- **A comparison is never converted.** A watermark or a dedup key ([connectors.md](connectors.md)) compares instants as written, never days.
