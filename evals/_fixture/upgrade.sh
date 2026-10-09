#!/usr/bin/env bash
# Extra fixture for the shell-upgrade-* cases. Builds two directory
# trees side by side under the run directory, neither nested inside the other:
#
#   vault/           a real vault root, ALREADY stamped with the clone's current revision.
#   para-os-clone/   a throwaway git clone of a fake para-os, with a bare `origin` so
#                    `origin/main` and `origin/stable` resolve offline, three commits deep.
#
# They are siblings on purpose, not one inside the other: `/para-upgrade`'s own script
# walks the whole `--vault` tree for `para-os-integration:` markers (para-shared's
# NOT_VAULT_CONTENT excludes only `.git` and `.claude/skills`), so a clone checked out
# inside the vault would plant its own master copies as second, spurious "installed" rows.
#
# The case this fixture drives is the **equal verdict** (SKILL.md Step 1), not a
# migration plan: the vault's marker already
# equals the clone's current revision, so there is nothing left in the changelog to apply.
# Asked "is this vault up to date", a bare model reads the marker, sees it match, and stops
# there. The skill does not stop there - it still diffs installed integration scripts and
# bundled skill copies, because those drift independently of the marker, and this fixture
# plants exactly two such drifts:
#
#   1. `vault/resources/scripts/logbook.py` carries the header `2026.08.03` (the clone's
#      current revision) but its body is byte-for-byte the `2026.08.01` script - someone
#      hand-edited the marker instead of syncing the file.
#   2. `vault/.claude/skills/para-notes/SKILL.md` is word-for-word the version the clone
#      shipped at `2026.08.01`. The clone's master changed in the `2026.08.02` entry and
#      has stayed at that newer version since; the vault's bundled copy never followed.
#
# The clone's CHANGELOG.md carries entries only - no statement of the legacy-label rule,
# no explanation of how a copy should be compared. An earlier version of this fixture
# spelled that out in the changelog text itself, which taught a bare model the trick it
# was supposed to lack; this version does not hand out the method.
#
# Every commit is `-c user.name=t -c user.email=t@example.invalid`, same as any other
# throwaway fixture repo in this suite. Dates: this fixture carries none, on either side
# - the marker and changelog scheme is a revision label, not a calendar date.
set -e

# --- the vault -------------------------------------------------------------------------

mkdir -p vault/projects vault/areas vault/archive vault/triage
mkdir -p vault/resources/scripts
mkdir -p vault/.claude/skills/para-notes

touch vault/triage/.gitkeep

cat > vault/CLAUDE.md <<'EOF'
# Fixture Vault Conventions

<!-- para-os-template: 2026.08.03 -->
**Type:** vault

A small fixture vault for the /para-upgrade audit eval.

## Actions

A checkbox may live in `projects/` and `areas/` only, never in `resources/`.
EOF

cat > vault/README.md <<'EOF'
# Fixture Vault

## Identity

A test vault for eval runs.
EOF

# The hand-bumped copy: header claims the clone's current revision (2026.08.03), body is
# word-for-word the 2026.08.01 script below. Never edit the two together.
cat > vault/resources/scripts/logbook.py <<'EOF'
#!/usr/bin/env python3
"""Fixture-only stand-in for a small note-syncing integration.

para-os-integration: logbook 2026.08.03

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

# The stale bundled skill copy: word-for-word the 2026.08.01 version, never followed the
# 2026.08.02 change below.
cat > vault/.claude/skills/para-notes/SKILL.md <<'EOF'
---
name: para-notes
description: Fixture-only stand-in skill for the /para-upgrade eval. Reads a folder of exported notes and lists them.
allowed-tools: Read, Glob
---

# Para notes

Reads a folder of exported notes and lists them by id. Fixture data only: this skill exists so /para-upgrade has a bundled skill copy it can diff, and it does nothing real.
EOF

# --- the clone ---------------------------------------------------------------------------

mkdir -p .clone-origin.git
git init -q --bare .clone-origin.git
# No auto maintenance in any fixture repository: its detached run writes into .git mid-run.
git -C .clone-origin.git config gc.auto 0
git -C .clone-origin.git config maintenance.auto false

mkdir -p para-os-clone
(
  cd para-os-clone
  git init -q -b main .
  git config gc.auto 0
  git config maintenance.auto false
  git remote add origin "$(cd ../.clone-origin.git && pwd)"

  # Commit 1 - revision 2026.08.01, the baseline every drifted copy in the vault matches.
  mkdir -p base/.claude/skills/para-notes integrations/logbook

  cat > CHANGELOG.md <<'EOF'
# Changelog

## 2026.08.01

**`triage/` ships a placeholder so an empty vault keeps the folder.** A fresh checkout with nothing triaged yet lost the folder entirely, which broke the first triage run. Reaction: add `triage/.gitkeep` to a vault that lacks it.
EOF

  cat > base/CLAUDE.md.template <<'EOF'
# {{Vault Name}} Vault Conventions

<!-- para-os-template: 2026.08.01 -->
**Type:** {{vault-type}}

{{One-line description of what this vault covers.}} Per-vault guidance for Claude Code sessions.
EOF

  cat > base/README.md.template <<'EOF'
# {{Vault Name}}

## Identity

{{One-line description of what this vault covers.}}
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

  cat > base/.claude/skills/para-notes/SKILL.md <<'EOF'
---
name: para-notes
description: Fixture-only stand-in skill for the /para-upgrade eval. Reads a folder of exported notes and lists them.
allowed-tools: Read, Glob
---

# Para notes

Reads a folder of exported notes and lists them by id. Fixture data only: this skill exists so /para-upgrade has a bundled skill copy it can diff, and it does nothing real.
EOF

  git add -A -f  # -f: a global gitignore of .claude/ must not drop the skill
  git -c user.name=t -c user.email=t@example.invalid commit -q -m "2026.08.01"
  git push -q origin main

  # Commit 2 - revision 2026.08.02, para-notes gains its one behavior change. logbook.py
  # carries forward unchanged.
  cat > CHANGELOG.md <<'EOF'
# Changelog

## 2026.08.02

**`/para-notes` drops a note whose text is blank instead of listing it as empty.** Reaction: re-sync installed `para-notes` copies.

---

## 2026.08.01

**`triage/` ships a placeholder so an empty vault keeps the folder.** A fresh checkout with nothing triaged yet lost the folder entirely, which broke the first triage run. Reaction: add `triage/.gitkeep` to a vault that lacks it.
EOF

  cat > base/CLAUDE.md.template <<'EOF'
# {{Vault Name}} Vault Conventions

<!-- para-os-template: 2026.08.02 -->
**Type:** {{vault-type}}

{{One-line description of what this vault covers.}} Per-vault guidance for Claude Code sessions.
EOF

  cat > base/.claude/skills/para-notes/SKILL.md <<'EOF'
---
name: para-notes
description: Fixture-only stand-in skill for the /para-upgrade eval. Reads a folder of exported notes, lists them, and drops a blank one.
allowed-tools: Read, Glob
---

# Para notes

Reads a folder of exported notes and lists them by id, and drops a note whose text is blank instead of listing it as empty. Fixture data only: this skill exists so /para-upgrade has a bundled skill copy it can diff, and it does nothing real.
EOF

  git add -A -f  # -f: a global gitignore of .claude/ must not drop the skill
  git -c user.name=t -c user.email=t@example.invalid commit -q -m "2026.08.02"
  git push -q origin main

  # Commit 3 - revision 2026.08.03, logbook.py gains its dedupe ledger. para-notes carries
  # forward unchanged from commit 2.
  cat > CHANGELOG.md <<'EOF'
# Changelog

## 2026.08.03

**The logbook integration gains a dedupe window so a rerun stops repeating old notes.** `logbook.py` now remembers the last fifty note ids it printed in a small ledger file next to the export folder, and skips one already printed instead of repeating it. Reaction: re-sync installed `logbook.py` copies; a vault with no logbook installed has nothing to do.

---

## 2026.08.02

**`/para-notes` drops a note whose text is blank instead of listing it as empty.** Reaction: re-sync installed `para-notes` copies.

---

## 2026.08.01

**`triage/` ships a placeholder so an empty vault keeps the folder.** A fresh checkout with nothing triaged yet lost the folder entirely, which broke the first triage run. Reaction: add `triage/.gitkeep` to a vault that lacks it.
EOF

  cat > base/CLAUDE.md.template <<'EOF'
# {{Vault Name}} Vault Conventions

<!-- para-os-template: 2026.08.03 -->
**Type:** {{vault-type}}

{{One-line description of what this vault covers.}} Per-vault guidance for Claude Code sessions.
EOF

  cat > integrations/logbook/logbook.py <<'EOF'
#!/usr/bin/env python3
"""Fixture-only stand-in for a small note-syncing integration.

para-os-integration: logbook 2026.08.03

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

  git add -A -f  # -f: a global gitignore of .claude/ must not drop the skill
  git -c user.name=t -c user.email=t@example.invalid commit -q -m "2026.08.03"
  git push -q origin main main:stable
  git fetch -q origin
)
