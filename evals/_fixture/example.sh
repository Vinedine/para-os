#!/usr/bin/env bash
# The example vault, examples/belfoot-vault/, as this checkout has it, for a case that runs a
# skill on the vault the repo ships rather than on one built for the case. tools/eval.py
# copies examples/ in beside this file, leaving out any untracked .claude/skills/ copy, so
# the run loads the skills under test.
#
# The vault is frozen at its own reference date, named at the top of its README. A case that
# needs something on the day of the run rewrites that one line itself.
set -e
EXAMPLE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/examples/belfoot-vault"
if [ ! -f "$EXAMPLE/CLAUDE.md" ]; then
  echo "evals/_fixture/examples holds no example vault: run the case through tools/eval.py." >&2
  exit 1
fi
cp -R "$EXAMPLE/." .
