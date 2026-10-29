#!/usr/bin/env bash
# Two vaults for /para-global-brief and no operator.json in the para-os home:
#
#   home    no roster, so its one writer keeps it: an item due today
#   studio  a roster naming Ada keeper, so with no operator.json nothing says who "I" am and
#           it is shown by health only: two invoices overdue
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

vault home "- [ ] Book the boiler service 📅 $(day 0)"
vault studio "- [ ] Chase the Lumen invoice 📅 $(day -3)
- [ ] Chase the Orbit invoice 📅 $(day -1)"

cat >> vaults/studio/CLAUDE.md <<'EOF'

## Who writes this vault

| Person | Role | Lane |
|---|---|---|
| Ada | keeper | [Site](projects/site/) |
| Bram | member | Bookkeeping |
EOF

mkdir -p paraos
cat > paraos/vaults.json <<JSON
[
  {"name": "home", "path": "$here/vaults/home",
   "purpose": "The household.", "active": true},
  {"name": "studio", "path": "$here/vaults/studio",
   "purpose": "The design studio, shared with a bookkeeper.", "active": true}
]
JSON
