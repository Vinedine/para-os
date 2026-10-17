#!/usr/bin/env bash
# Meeting recordings on a server the skills name nowhere (`notetaker`, mocked): each one is
# listed and read through the server's read tools and judged as a note, never deleted.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"
rm -f triage/*.md
cat >> CLAUDE.md <<'EOF'

## Triage sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
| calls | connector: notetaker recording | `owner@example.com` | Client calls. |
EOF
