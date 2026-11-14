#!/usr/bin/env bash
# A vault on two files whose own CLAUDE.md holds three lines beside the core: a core rule
# reworded, a general way of working, and a fact true of this vault only. The core is the
# checkout's own, through kit/, so the case reads the rule under review.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
KIT="$(cd "$(dirname "$0")/../_fixture" && pwd)/kit"
if [ ! -f "$KIT/base/.claude/para-os/core.md" ]; then
  echo "evals/_fixture/kit holds no kit: this checkout has symlinks off." >&2
  exit 1
fi
mkdir -p .claude/para-os areas/print-shop/proofs
cp "$KIT/base/.claude/para-os/core.md" .claude/para-os/core.md

cat > CLAUDE.md <<'EOF'
# Fixture Vault Conventions

**Type:** vault

@.claude/para-os/core.md

## Working here

- A finished project is archived whole through `/para-archive`, and its open items are routed first to the area that owns them, a successor project or a contact file.
- Lead every answer with the decision, and keep it under ten lines.
- The print shop's proofs are filed in `areas/print-shop/proofs/`, one folder per job number.
EOF
