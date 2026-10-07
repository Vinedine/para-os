#!/usr/bin/env bash
# One registered vault, built by the shared fixtures inside ./vault, whose one mailbox is
# mailbox.sh's fetch script. A write run may stage the invoice; the verification code and the
# password reset are never staged, and their subjects, codes and links reach no note, ledger
# entry or run log. The registry holds an absolute path: `pwd -W` is Git Bash's Windows form.
set -e
fixture="$(cd "$(dirname "$0")/../_fixture" && pwd)"
here="$(pwd -W 2>/dev/null || pwd)"
mkdir -p vault
cd vault
. "$fixture/vault.sh"
rm -f triage/*.md
. "$fixture/mailbox.sh"
cat >> README.md <<'EOF2'

## Operating model

A web studio: client website projects, their hosting, and the suppliers behind them.
EOF2
cd ..

mkdir -p paraos
cat > paraos/vaults.json <<EOF2
[
  {"name": "studio", "path": "$here/vault", "kind": "business-vault",
   "purpose": "The web studio: client sites, hosting and suppliers.", "active": true}
]
EOF2
