#!/usr/bin/env bash
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"

# The staged note holds the host's full message but none of the operator's own, so whether
# the go-live window was already sent cannot be read from it, and no mailbox is connected
# to re-read the thread. The note must not be read as a mail waiting on the operator.
sed -i.bak 's/^- \*\*Content:\*\* .*/- **Content:** Full body of the host'"'"'s message; own messages not fetched./' \
  triage/*7e3b91.md
rm -f triage/*.bak
