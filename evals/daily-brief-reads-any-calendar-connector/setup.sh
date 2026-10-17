#!/usr/bin/env bash
# A calendar on a server the skills name nowhere (`calbox`, mocked): its events reach the
# agenda through the server's read tools, and nothing is created or answered.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
cat >> CLAUDE.md <<'EOF'

## Agenda sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
| work | connector: calbox | `owner@example.com` | Client meetings. |
EOF
