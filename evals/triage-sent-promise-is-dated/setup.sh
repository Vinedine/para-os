#!/usr/bin/env bash
# The owner promised Rosa a price "Wednesday" in mail, and Rosa's later reply is about
# something else. Judged on its newest message the thread asks nothing; read for the owner's
# own messages, it holds a dated promise. The right proposal is one action to send Rosa the
# price, dated the Wednesday after the owner's message: five days after that Friday.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"
rm -f triage/*.md
SENT_THREADS=promise
. "$(dirname "$0")/../_fixture/sentmail.sh"
