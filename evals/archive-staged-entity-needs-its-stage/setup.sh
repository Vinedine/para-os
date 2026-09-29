#!/usr/bin/env bash
# harbor-freight-labs from deals.sh sits at Qualified, a live stage, with no Lost line. Its
# terminal home is archive/ideas/, and the move there is refused until the Stage line reads
# Lost and the Lost reason the rule file requires is written.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/deals.sh"
