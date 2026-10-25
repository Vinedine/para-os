#!/usr/bin/env bash
# The example vault, its Q3 budget decision moved to the day of the run so the agenda finds
# it, with no time so the hour of the run cannot put it in the past. Jan Claes has a card
# with open items, more open items naming him in two action files, and records of meetings
# with him, the newest still unfiled in triage/; Lotte Maes, from the vendor, has no card.
# Neither project his card links carries a Stage line, so the meeting's objective is not in
# the vault.
set -e
. "$(dirname "$0")/../_fixture/example.sh"
grep -v ' · Q3 budget decision · ' meetings.md > meetings.md.tmp
printf -- '- 🗓 %s · Q3 budget decision · Antwerp office · Jan Claes, Lotte Maes (NovaPay)\n' \
  "$(date +%F)" >> meetings.md.tmp
mv meetings.md.tmp meetings.md
