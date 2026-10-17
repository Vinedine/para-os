#!/usr/bin/env bash
# A shop's payment overview for an order paid and delivered last week, saved into triage/ as
# a loose file. No copy is in the vault and no open line tracks the order. Its outcome is kept
# in the shop's own account, where the order and its invoice stay, so the right disposition
# is Delete (no lasting value) naming that account, never Leave in triage for want of a
# survivor inside the vault.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"
rm -f triage/*.md

cat > "triage/Payment overview order 58213.txt" <<EOF
INKWELL OFFICE SUPPLIES - PAYMENT OVERVIEW

Order: 58213
Ordered: $(day -6)
Customer: Fixture Studio

2 x Black toner cartridge LX-410      78.00
Delivery                               0.00
Total paid                            78.00

Payment: card ending 4417, charged $(day -6). Status: paid in full.
Delivered: $(day -3).

This overview is not an invoice. The order and its invoice stay under Orders in your
Inkwell account.
EOF
