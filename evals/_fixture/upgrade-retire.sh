#!/usr/bin/env bash
# Fixture for shell-upgrade-retired-integration-is-removed. Builds two trees side by side under
# the run directory, as upgrade-apply.sh does (upgrade.sh says why neither nests in the other):
#
#   vault/           a vault root and a git repo with every file committed, stamped 2026.08.01,
#                    holding `resources/scripts/logbook.py` with its 2026.08.01 marker.
#   para-os-clone/   a throwaway clone of a fake para-os with a bare `origin`, two commits deep.
#
# The one collected entry, 2026.08.02, retires the logbook integration: `integrations/logbook/`
# is gone at the ref, so the installed copy's marker resolves to no master, and the entry's
# `Retired:` line names every copy, wherever it sits. Nothing else changes between the revisions.
#
# Every commit is `-c user.name=t -c user.email=t@example.invalid`. Dates: none.
set -e

LOGBOOK='#!/usr/bin/env python3
"""Fixture-only stand-in for a small note-syncing integration.

para-os-integration: logbook 2026.08.01

Reads a folder of exported notes and prints each one as a JSON line. Fixture data only.
"""

import json
import sys
from pathlib import Path


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    for name in sorted(root.glob("*.txt")):
        print(json.dumps({"id": name.stem, "text": name.read_text(encoding="utf-8").strip()}))


if __name__ == "__main__":
    main()
'

# --- the vault -------------------------------------------------------------------------

mkdir -p vault/projects/shop-refit vault/areas vault/archive vault/triage vault/resources/scripts
touch vault/triage/.gitkeep

cat > vault/CLAUDE.md <<'EOF'
# Fixture Vault Conventions

<!-- para-os-template: 2026.08.01 -->
**Type:** vault

A small fixture vault for the /para-upgrade retirement eval.

## Actions

A checkbox may live in `projects/` and `areas/` only, never in `resources/`.
EOF

cat > vault/README.md <<'EOF'
# Fixture Vault

## Identity

A test vault for eval runs.
EOF

cat > vault/projects/shop-refit/actions.md <<'EOF'
# Shop refit actions

- [ ] Confirm the counter height with the joiner
EOF

printf '%s' "$LOGBOOK" > vault/resources/scripts/logbook.py

(
  cd vault
  git init -q -b main .
  git config gc.auto 0
  git config maintenance.auto false
  git add -A -f
  git -c user.name=t -c user.email=t@example.invalid commit -q -m "vault"
)

# --- the clone ---------------------------------------------------------------------------

mkdir -p .clone-origin.git
git init -q --bare .clone-origin.git
git -C .clone-origin.git config gc.auto 0
git -C .clone-origin.git config maintenance.auto false

mkdir -p para-os-clone
(
  cd para-os-clone
  git init -q -b main .
  git config gc.auto 0
  git config maintenance.auto false
  git remote add origin "$(cd ../.clone-origin.git && pwd)"

  # Commit 1: revision 2026.08.01, the vault's.
  mkdir -p base/triage integrations/logbook
  touch base/triage/.gitkeep
  printf '%s' "$LOGBOOK" > integrations/logbook/logbook.py

  cat > CHANGELOG.md <<'EOF'
# Changelog

## 2026.08.01
EOF

  template() {
    cat > base/CLAUDE.md.template <<EOF
# {{Vault Name}} Vault Conventions

<!-- para-os-template: $1 -->
**Type:** {{vault-type}}

{{One-line description of what this vault covers.}}

## Actions

A checkbox may live in \`projects/\` and \`areas/\` only, never in \`resources/\`.
EOF
  }
  template 2026.08.01

  cat > base/README.md.template <<'EOF'
# {{Vault Name}}

## Identity

{{One-line description of what this vault covers.}}
EOF

  git add -A -f
  git -c user.name=t -c user.email=t@example.invalid commit -q -m "2026.08.01"
  git push -q origin main

  # Commit 2: revision 2026.08.02 retires the logbook integration.
  git rm -q -r integrations/logbook
  template 2026.08.02
  cat > CHANGELOG.md <<'EOF'
# Changelog

## 2026.08.02

Retired: `**/logbook.py`

## 2026.08.01
EOF

  git add -A -f
  git -c user.name=t -c user.email=t@example.invalid commit -q -m "2026.08.02"
  git push -q origin main main:stable
  git fetch -q origin
)
