#!/usr/bin/env bash
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"

# Push the loose-file count past the four-question manifest threshold (asking.md): a
# byte-identical duplicate of a filed brief, a plain text document for an existing entity,
# a README.md left behind by an old skeleton and a note for the network, plus one
# subdirectory that must be listed and never asked. The brief is lengthened first so the
# copy is past the size the duplicate hash skips (MIN_HASH_BYTES in paraos_vault.py).
cat >> resources/ideas/orchard-labs/brief.md <<'EOF'

They quote by hand from a spreadsheet today, and asked whether the rebuild could reuse the
supplier price list they already keep, rather than retyping it into a new system.
EOF
cp resources/ideas/orchard-labs/brief.md "triage/orchard-labs brief copy.md"

cat > "triage/Call with Mira - intro.md" <<'EOF'
Mira runs a bakery two streets over and asked for an intro call about a new website.
EOF

cat > "triage/AcmeWebsite hosting invoice.txt" <<'EOF'
Invoice #4471 for AcmeWebsite hosting, covering the launch month.
Billed to Fixture Studio for the acme-website engagement.
EOF

cat > triage/README.md <<'EOF'
# Triage

Drop anything here that needs to be filed.
EOF

mkdir -p triage/_handover-scans
printf 'placeholder scan one\n' > triage/_handover-scans/scan-001.txt
printf 'placeholder scan two\n' > triage/_handover-scans/scan-002.txt
