#!/usr/bin/env bash
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"

# Two writers. triage.sh's staged note bears on projects/acme-website, Robin's lane, so a run
# by Sam lists it as left for Robin. The renewal notice bears on areas/business, Sam's own.
cat >> CLAUDE.md <<'EOF'

## Who writes this vault

| Person | Lane |
|---|---|
| Sam | [Business](areas/business/), [para-os](projects/para-os-2026-09-04/) |
| Robin | [Acme website](projects/acme-website/) |

- **The roster is here; which one you are is not.** Identity comes from outside the vault.
- **An area is the ownership unit.**
EOF

cat > "triage/Ledgerly renewal notice.txt" <<EOF
Your Ledgerly accounting subscription renews automatically on $(day 12).
Cancel or change plan before then from the billing page.
EOF
