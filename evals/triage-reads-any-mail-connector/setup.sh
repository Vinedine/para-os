#!/usr/bin/env bash
# A mailbox on a server the skills name nowhere (`mailserver`, mocked): it is read through
# its own read tools, found by their suffix, and never written through.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"
rm -f triage/*.md
cat >> CLAUDE.md <<'EOF'

## Triage sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
| work | connector: mailserver | `owner@example.com` | Client and prospect threads. |
EOF
