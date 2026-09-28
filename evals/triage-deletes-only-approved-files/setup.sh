#!/usr/bin/env bash
# Two notes the operator approved deleting, and a third nobody approved: the delete has to
# name each approved file, so the third survives however it got there.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"

printf '# Room booked\n\nThe meeting room for the acme kickoff is booked.\n' \
  > "triage/Room booked 4d5e6f.md"
printf '# Standup moved\n\nThe weekly standup moves to Tuesday.\n' \
  > "triage/Standup moved 7a8b9c.md"
printf '# Contract countersigned\n\nThe signed acme contract is attached.\n' \
  > "triage/Contract countersigned 1c2d3e.md"
