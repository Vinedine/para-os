#!/usr/bin/env bash
set -e
. "$(dirname "$0")/../_fixture/vault.sh"

# Deep clean refuses to start on a loose triage file, and vault.sh plants one.
rm -f triage/*.md
touch triage/.gitkeep

# A three-page PDF, one argument per page, written byte for byte so its xref offsets are
# right without a PDF tool. ASCII only: a byte count is a character count.
pdf() {
  local out=$1 body offsets=() n=0 page lines line
  shift
  export LC_ALL=C
  obj() { offsets+=("${#body}"); n=$((n + 1)); body+="$n 0 obj"$'\n'"$1"$'\n'"endobj"$'\n'; }
  body="%PDF-1.4"$'\n'
  obj "<< /Type /Catalog /Pages 2 0 R >>"
  obj "<< /Type /Pages /Kids [4 0 R 6 0 R 8 0 R] /Count 3 >>"
  obj "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
  for page in "$@"; do
    lines="BT /F1 12 Tf 16 TL 72 740 Td"
    while IFS= read -r line; do lines+=" ($line) Tj T*"; done <<< "$page"
    lines+=" ET"
    obj "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents $((n + 2)) 0 R >>"
    obj "<< /Length ${#lines} >>"$'\n'"stream"$'\n'"$lines"$'\n'"endstream"
  done
  local xref=${#body}
  body+="xref"$'\n'"0 $((n + 1))"$'\n'"0000000000 65535 f "$'\n'
  for o in "${offsets[@]}"; do body+="$(printf '%010d 00000 n ' "$o")"$'\n'; done
  body+="trailer"$'\n'"<< /Size $((n + 1)) /Root 1 0 R >>"$'\n'"startxref"$'\n'"$xref"$'\n'"%%EOF"$'\n'
  printf '%s' "$body" > "$out"
}

mkdir -p projects/harbour-flat/sources

cat > projects/harbour-flat/brief.md <<'EOF'
# harbour-flat

Buying the flat on Quay Street as Fixture Studio's second office.

## Status

| Detail | Value |
|---|---|
| Stage | Deed signed |

## Open items

- Purchase price not on file.
- Notary fee not itemised.

## Sources

- [Deed of sale](sources/20260301 Deed of sale.pdf)
EOF

pdf "projects/harbour-flat/sources/20260301 Deed of sale.pdf" \
"DEED OF SALE
Between Harbour Holdings, the seller, and Fixture Studio, the buyer.
Object: the flat on the fourth floor of 12 Quay Street, with one cellar." \
"Article 2 - Condition
The flat is sold in its present state, without warranty for hidden defects.
Article 3 - Entry
The buyer takes possession on the day of signing." \
"Article 7 - Price
The sale is agreed at a price of EUR 287,400, paid in full at signing.
Signed in two copies, one for each party."
