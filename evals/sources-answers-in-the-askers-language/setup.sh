#!/usr/bin/env bash
# A vault whose declared language is Dutch, with Dutch content, asked a question in English.
# The Language paragraph is base/CLAUDE.md.template's word for word, its placeholder filled:
# a change to that paragraph changes this copy in the same commit.
set -e
day() { date -d "$1 days" "+$2" 2>/dev/null || { case $1 in -*) s=$1;; *) s=+$1;; esac; date -v"${s}"d "+$2"; }; }

cat > CLAUDE.md <<'EOF'
# Huis Peeters Vault Conventions

**Type:** vault

## Language

Folders and structural files in English; content in its source's language, untranslated unless asked. The operator's language is Dutch, the default; answer a request in the language it is written in, whatever the source's language, quoting the original only where the exact wording matters.
EOF

cat > README.md <<'EOF'
# Huis Peeters

## Identity

Het gezinsvault van An en Bart Peeters: het huis, de auto en de papieren erachter.

## Vision

Weten wat er aan het huis moet gebeuren, en wanneer.
EOF

mkdir -p projects/dakherstelling triage
touch triage/.gitkeep

cat > projects/dakherstelling/brief.md <<'EOF'
# Dakherstelling

Lekkage boven de badkamer na de storm. Dakwerker Willems heeft een offerte gestuurd.
EOF

cat > projects/dakherstelling/actions.md <<EOF
# Dakherstelling: acties

- [ ] Offerte van Willems vergelijken met een tweede dakwerker 📅 $(day 5 %F)
- [ ] Verzekeraar bellen over de waterschade in de badkamer 📅 $(day -2 %F)
- [ ] Datum voor de werken afspreken zodra de offerte goedgekeurd is
- [x] Foto's van de lekkage maken ✅ $(day -9 %F)
EOF
