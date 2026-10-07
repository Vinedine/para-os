#!/usr/bin/env bash
# para-shared as this checkout ships it, installed in the vault's own .claude/skills/ the way
# a vault-level install puts it, for a case where the vault's CLAUDE.md names a para-shared
# file and no skill fires to say where that file is. tools/eval.py assembles the skills under
# test beside evals/, so the copy is of the text under review, never a stale one.
set -e
SHARED="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/skills/para-shared"
if [ ! -f "$SHARED/drafting.md" ]; then
  echo "no skills/para-shared beside evals/: run the case through tools/eval.py." >&2
  exit 1
fi
mkdir -p .claude/skills
cp -R "$SHARED" .claude/skills/para-shared
find .claude/skills -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
