#!/usr/bin/env bash
# The sales module's deal lifecycle (deals.sh), whose first non-row stage is Qualified. A
# deal named with the lifecycle noun is created there, with its Stage line and the seven
# header lines deal-brief.md declares, not as an ordinary idea.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/deals.sh"
