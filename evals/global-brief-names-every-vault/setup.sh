#!/usr/bin/env bash
# A registry of three vaults for /para-global-brief, with dates relative to the day of the run.
#
#   north  an item two days overdue and one due today
#   south  one item due today, the highest priority of the three
#   east   registered at a path that does not exist: UNREACHABLE
#
# The registry holds absolute paths: `pwd -W` is Git Bash's Windows form, `pwd` elsewhere.
set -e
here="$(pwd -W 2>/dev/null || pwd)"
day() { date -d "$1 days" +%F 2>/dev/null || { case $1 in -*) s=$1;; *) s=+$1;; esac; date -v"${s}"d +%F; }; }

vault() {  # <name> <actions>
  mkdir -p "vaults/$1/projects/site" "vaults/$1/areas" "vaults/$1/archive" "vaults/$1/triage"
  printf '# %s Vault Conventions\n\n**Type:** vault\n' "$1" > "vaults/$1/CLAUDE.md"
  printf '# site - Actions\n\n%s\n' "$2" > "vaults/$1/projects/site/actions.md"
}

vault north "- [ ] Renew the north.example domain 📅 $(day -2)
- [ ] Send the north launch note 📅 $(day 0)
- [ ] Write the north case study"
vault south "- [ ] Pay the south host invoice 🔺 📅 $(day 0)"

mkdir -p paraos
cat > paraos/vaults.json <<JSON
[
  {"name": "north", "path": "$here/vaults/north", "kind": "client-vault",
   "purpose": "The northern client engagement.", "active": true},
  {"name": "south", "path": "$here/vaults/south", "kind": "client-vault",
   "purpose": "The southern client engagement.", "active": true},
  {"name": "east", "path": "$here/vaults/east", "kind": "client-vault",
   "purpose": "The eastern client engagement, on a shared drive.", "active": true}
]
JSON
