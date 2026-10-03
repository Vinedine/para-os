#!/usr/bin/env bash
# deals.sh with northwind-quoting's price hold removed and its champion's step four days
# overdue. Nothing is about to expire, so the close weighs that overdue step against
# orchard-labs (Proposal) and harbor-freight-labs (Qualified), which have no next step: the
# overdue step wins.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/deals.sh"

sed "s/; prices hold to [0-9-]*//" resources/ideas/northwind-quoting/brief.md > brief.tmp
mv brief.tmp resources/ideas/northwind-quoting/brief.md

cat > areas/network/pia-vermeer.md <<EOF
# Pia Vermeer

**Kind:** buyer

Ops lead at northwind-quoting, the champion pushing the rebuild internally.

## Next actions

- [ ] Confirm the signer with Pia 📅 $(day -4)
EOF
