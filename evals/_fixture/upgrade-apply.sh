#!/usr/bin/env bash
# Fixture for shell-upgrade-applies-only-the-delta. Builds two directory trees side by side
# under the run directory, neither nested inside the other (upgrade.sh says why):
#
#   vault/           a real vault root and a git repo with every file committed, stamped
#                    2026.08.01, one revision behind the clone's origin/stable.
#   para-os-clone/   a throwaway git clone of a fake para-os, with a bare `origin` so
#                    `origin/main` and `origin/stable` resolve offline, two commits deep.
#
# The case this fixture drives is an applied migration, not an audit. The one collected
# entry, 2026.08.02, carries two items:
#
#   1. A mechanical Reaction on a file the vault has in its before state: the template's
#      `## Actions` section gains one sentence, and the entry says to take it into the
#      vault's CLAUDE.md. It is CLAUDE.md, not a file under `.claude/`, on purpose: a
#      non-interactive run cannot Edit a `.claude/` file, which Claude Code refuses as
#      sensitive with no operator to approve it, so a Reaction there would grade the
#      harness rather than the skill.
#   2. The logbook integration's master moved. The vault's `resources/scripts/logbook.py` is
#      byte for byte the 2026.08.01 master, honestly stamped 2026.08.01, so the scan calls it
#      behind. The newer master's `LEDGER_LIMIT` line is what a sync would bring in.
#
# Beside those, the vault carries two things no entry names: a `## Supplier calls` section
# in its CLAUDE.md that the template lacks, and a dangling link in
# `projects/shop-refit/brief.md` (its `sources/joiner-quote.pdf` does not exist).
#
# The clone's CHANGELOG.md carries entries only, as upgrade.sh's does: nothing in it states
# how a copy is compared or what an upgrade should leave alone.
#
# Every commit is `-c user.name=t -c user.email=t@example.invalid`. Dates: none, on either
# side; the marker and changelog scheme is a revision label, not a calendar date.
set -e

# --- the vault -------------------------------------------------------------------------

mkdir -p vault/projects/shop-refit vault/areas/supplies vault/archive vault/triage
mkdir -p vault/resources/scripts vault/.claude/rules

touch vault/triage/.gitkeep

cat > vault/CLAUDE.md <<'EOF'
# Fixture Vault Conventions

<!-- para-os-template: 2026.08.01 -->
**Type:** vault

A small fixture vault for the /para-upgrade apply eval.

## Actions

A checkbox may live in `projects/` and `areas/` only, never in `resources/`. The rule file is `.claude/rules/actions.md`.

## Supplier calls

Every call with the paper supplier is logged in `areas/supplies/calls.md`, newest first, one line per call.
EOF

cat > vault/README.md <<'EOF'
# Fixture Vault

## Identity

A test vault for eval runs.
EOF

# The before state of the file the collected entry's Reaction changes.
cat > vault/.claude/rules/actions.md <<'EOF'
---
paths:
  - "projects/*/actions.md"
---

# Actions

One open item per checkbox line, `- [ ] text`, and nothing else on that line but the item.
EOF

cat > vault/projects/shop-refit/brief.md <<'EOF'
# Shop refit

**Status:** active

New shelving and a counter for the front of the shop. The joiner's figure is in [the joiner's quote](sources/joiner-quote.pdf).
EOF

cat > vault/projects/shop-refit/actions.md <<'EOF'
# Shop refit actions

- [ ] Confirm the counter height with the joiner
EOF

cat > vault/areas/supplies/README.md <<'EOF'
# Supplies

Paper, ink and packing stock for the shop.
EOF

cat > vault/areas/supplies/actions.md <<'EOF'
# Supplies actions

- [ ] Reorder A4 paper
EOF

cat > vault/areas/supplies/calls.md <<'EOF'
# Supplier calls

- Paper supplier: the next delivery moves to the first week of the month.
EOF

# Byte for byte the 2026.08.01 master below, marker included. Never edit the two apart.
cat > vault/resources/scripts/logbook.py <<'EOF'
#!/usr/bin/env python3
"""Fixture-only stand-in for a small note-syncing integration.

para-os-integration: logbook 2026.08.01

Reads a folder of exported notes and prints each one as a JSON line. Fixture data only: this script exists so /para-upgrade has a script it can diff, and it does nothing real.
"""

import json
import sys
from pathlib import Path


def entries(path):
    """Yield each exported note in `path` as a plain dict."""
    for name in sorted(path.glob("*.txt")):
        yield {"id": name.stem, "text": name.read_text(encoding="utf-8").strip()}


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    for entry in entries(Path(root)):
        print(json.dumps(entry))


if __name__ == "__main__":
    main()
EOF

(
  cd vault
  git init -q -b main .
  # No auto maintenance in any fixture repository: its detached run writes into .git mid-run.
  git config gc.auto 0
  git config maintenance.auto false
  git add -A -f  # -f: a global gitignore of .claude/ must not drop the rule file
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

  # Commit 1: revision 2026.08.01, the revision the vault is stamped at.
  mkdir -p base/.claude/rules base/triage integrations/logbook
  touch base/triage/.gitkeep

  cat > CHANGELOG.md <<'EOF'
# Changelog

## 2026.08.01

**`triage/` ships a placeholder so an empty vault keeps the folder.** A fresh checkout with nothing triaged yet lost the folder entirely, which broke the first triage run. Reaction: add `triage/.gitkeep` to a vault that lacks it.
EOF

  cat > base/CLAUDE.md.template <<'EOF'
# {{Vault Name}} Vault Conventions

<!-- para-os-template: 2026.08.01 -->
**Type:** {{vault-type}}

{{One-line description of what this vault covers.}}

## Actions

A checkbox may live in `projects/` and `areas/` only, never in `resources/`. The rule file is `.claude/rules/actions.md`.
EOF

  cat > base/README.md.template <<'EOF'
# {{Vault Name}}

## Identity

{{One-line description of what this vault covers.}}
EOF

  cat > base/.claude/rules/actions.md <<'EOF'
---
paths:
  - "projects/*/actions.md"
---

# Actions

One open item per checkbox line, `- [ ] text`, and nothing else on that line but the item.
EOF

  cat > integrations/logbook/logbook.py <<'EOF'
#!/usr/bin/env python3
"""Fixture-only stand-in for a small note-syncing integration.

para-os-integration: logbook 2026.08.01

Reads a folder of exported notes and prints each one as a JSON line. Fixture data only: this script exists so /para-upgrade has a script it can diff, and it does nothing real.
"""

import json
import sys
from pathlib import Path


def entries(path):
    """Yield each exported note in `path` as a plain dict."""
    for name in sorted(path.glob("*.txt")):
        yield {"id": name.stem, "text": name.read_text(encoding="utf-8").strip()}


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    for entry in entries(Path(root)):
        print(json.dumps(entry))


if __name__ == "__main__":
    main()
EOF

  git add -A -f  # -f: a global gitignore of .claude/ must not drop the rule file
  git -c user.name=t -c user.email=t@example.invalid commit -q -m "2026.08.01"
  git push -q origin main

  # Commit 2: revision 2026.08.02, the one entry the vault has not had. The actions rule
  # widens its paths, and logbook.py gains its dedupe ledger.
  cat > CHANGELOG.md <<'EOF'
# Changelog

## 2026.08.02

**An area's action file is an action file too.** An area's `actions.md` holds open items the same way a project's does, and `CLAUDE.md` never said so. The template's `## Actions` section gains one sentence. Reaction: take that sentence into the vault's `## Actions` section.

**The logbook integration skips a note it has already printed.** `logbook.py` now remembers the last fifty note ids it printed in a small ledger file next to the export folder, and skips one already printed instead of repeating it. Reaction: re-sync installed `logbook.py` copies; a vault with no logbook installed has nothing to do.

---

## 2026.08.01

**`triage/` ships a placeholder so an empty vault keeps the folder.** A fresh checkout with nothing triaged yet lost the folder entirely, which broke the first triage run. Reaction: add `triage/.gitkeep` to a vault that lacks it.
EOF

  cat > base/CLAUDE.md.template <<'EOF'
# {{Vault Name}} Vault Conventions

<!-- para-os-template: 2026.08.02 -->
**Type:** {{vault-type}}

{{One-line description of what this vault covers.}}

## Actions

A checkbox may live in `projects/` and `areas/` only, never in `resources/`. The rule file is `.claude/rules/actions.md`.

An area's `actions.md` is an action file too: it follows the same checkbox rule as a project's.
EOF

  cat > base/.claude/rules/actions.md <<'EOF'
---
paths:
  - "projects/*/actions.md"
---

# Actions

One open item per checkbox line, `- [ ] text`, and nothing else on that line but the item.
EOF

  cat > integrations/logbook/logbook.py <<'EOF'
#!/usr/bin/env python3
"""Fixture-only stand-in for a small note-syncing integration.

para-os-integration: logbook 2026.08.02

Reads a folder of exported notes and prints each one as a JSON line, skipping an id it has already printed. Fixture data only: this script exists so /para-upgrade has a script it can diff, and it does nothing real.
"""

import json
import sys
from pathlib import Path

LEDGER_LIMIT = 50


def entries(path):
    """Yield each exported note in `path` as a plain dict."""
    for name in sorted(path.glob("*.txt")):
        yield {"id": name.stem, "text": name.read_text(encoding="utf-8").strip()}


def load_ledger(ledger_path):
    if not ledger_path.exists():
        return []
    return ledger_path.read_text(encoding="utf-8").splitlines()[-LEDGER_LIMIT:]


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    seen = load_ledger(Path(root) / ".logbook-seen")
    for entry in entries(Path(root)):
        if entry["id"] in seen:
            continue
        print(json.dumps(entry))


if __name__ == "__main__":
    main()
EOF

  git add -A -f  # -f: a global gitignore of .claude/ must not drop the rule file
  git -c user.name=t -c user.email=t@example.invalid commit -q -m "2026.08.02"
  git push -q origin main main:stable
  git fetch -q origin
)
