#!/usr/bin/env bash
# The owner sent Ivo a site-care proposal seven days ago, asking whether to go ahead, and
# nobody has answered. It lives only in Sent, so it is found only by the sent pass. Seven
# days hold five working days whatever the weekday, so the right proposal is a Waiting on
# line for Ivo's answer, since the day the proposal went out, with no due date.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"
rm -f triage/*.md
SENT_THREADS=proposal
. "$(dirname "$0")/../_fixture/sentmail.sh"
