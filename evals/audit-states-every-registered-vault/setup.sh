#!/usr/bin/env bash
# A registry of four vaults for /para-audit, and no para-os clone, so no vault can be held
# against a master: the case grades the registry's rules and what reads without git.
#
#   north  active, its `**Type:**` matching its `kind`
#   south  `active: false`, still audited; `**Type:** personal-vault` against the registry's
#          `client-vault`; a CLAUDE.md of 240 lines, over the 200-line target
#   east   registered at a path that does not exist: UNREACHABLE
#   west   `retired: true`, on disk all the same: RETIRED (excluded)
#
# The registry holds absolute paths: `pwd -W` is Git Bash's Windows form, `pwd` elsewhere.
set -e
here="$(pwd -W 2>/dev/null || pwd)"

vault() {  # <name> <type> <extra rule lines>
  mkdir -p "vaults/$1/projects" "vaults/$1/areas" "vaults/$1/archive" "vaults/$1/triage"
  {
    printf '# %s Vault Conventions\n\n<!-- para-os-template: 2026.10.01 -->\n' "$1"
    printf '**Type:** %s\n\nA fixture vault for the /para-audit eval.\n\n## Actions\n\n' "$2"
    printf 'A checkbox lives in projects/ and areas/ only.\n'
    for i in $(seq 1 "$3"); do printf 'Rule %s: a standing rule of this vault.\n' "$i"; done
  } > "vaults/$1/CLAUDE.md"
}

vault north client-vault 0
vault south personal-vault 230
vault west client-vault 0

mkdir -p paraos
cat > paraos/vaults.json <<EOF
[
  {"name": "north", "path": "$here/vaults/north", "kind": "client-vault",
   "purpose": "The northern client engagement.", "active": true},
  {"name": "south", "path": "$here/vaults/south", "kind": "client-vault",
   "purpose": "The southern client engagement, paused.", "active": false},
  {"name": "east", "path": "$here/vaults/east", "kind": "client-vault",
   "purpose": "The eastern client engagement, on a shared drive.", "active": true},
  {"name": "west", "path": "$here/vaults/west", "kind": "client-vault",
   "purpose": "A finished engagement, kept for reference.", "active": false, "retired": true}
]
EOF
