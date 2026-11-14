# para-os activity module

The fixed rules of the activity module, the same in every vault that declares it. `/para-upgrade` replaces this file whole: never edit it. The vault's own `CLAUDE.md` **wins wherever the two differ**.

## Activity ledger

This vault records how it is used. A hook runs `resources/scripts/activity.py` on each Claude Code event and appends one line per event to `resources/logs/sessions/`: what was asked, which tools and skills ran, what failed. Never file contents, never the conversation. `/para-activity-review` reads it and reports what to change.

The ledger is pruned only through `/para-activity-review`, one file at a time, once a report has used it. No other skill and no hand edit moves, rewrites or deletes a ledger file.
