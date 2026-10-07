#!/usr/bin/env bash
# A two-unit let house at Prospecting, with every input its underwriting needs and none of
# the figures: the asking price, the rents as let, the running costs, a quoted roof repair
# and the lender's terms, each citing its source, against the register's transaction costs
# and the persona's allowances, bars and bid rule. The right run computes the cost basis,
# both yields, the cover, cash-on-cash, the downside, the bid zone and the walk-away in code
# it executes, and writes each into the dossier with its inputs beside it. At the asking
# price the deal misses the yield bar and the cover bar, so the bid lands below it.
set -e
. "$(dirname "$0")/../_fixture/property.sh"

p=resources/ideas/7-harrow-street
mkdir -p "$p/sources"
listing="$(day -14 %Y%m%d) Kestrel Homes Listing.txt"
quote="$(day -9 %Y%m%d) Alder Roofing Quote.txt"
loan="$(day -5 %Y%m%d) Fernbank Lending Loan Indication.txt"

cat > "$p/sources/$listing" <<EOF
KESTREL HOMES - FOR SALE
7 Harrow Street: a terraced house in two let units
Asking price: 240,000

Ground-floor flat, 62 m2, let at 850 per month
Upper maisonette, 48 m2, let at 700 per month
Property tax: 1,100 per year. Building insurance: 450 per year (current owner's premium).
EOF

cat > "$p/sources/$quote" <<EOF
ALDER ROOFING - QUOTE
7 Harrow Street: replace the rear roof slope and its flashing.
Total: 6,000.00, all taxes included. Valid 60 days.
EOF

cat > "$p/sources/$loan" <<EOF
From: Fernbank Lending
Subject: 7 Harrow Street, loan indication

We can lend 70 % of the purchase price over 20 years at 4.20 % fixed, repaid as a monthly
annuity. Subject to valuation.
EOF

cat > "$p/brief.md" <<EOF
# 7 Harrow Street

**Stage:** Prospecting (since $(day -14 %F))
**Opened:** $(day -14 %F)
**Source:** Kestrel Homes, listing
**Last touch:** $(day -2 %F), viewing held with the agent

## Snapshot

A terraced house in two let units, a ground-floor flat and an upper maisonette, listed by Kestrel Homes at 240,000. The plan is to buy it through Fixture Holdings and keep both units let. Stage: Prospecting.

## Deal economics

### Inputs

| Item | Amount | Source |
|---|---|---|
| Asking price | 240,000 | [listing](<sources/$listing>) |
| Rent, ground-floor flat | 850 per month | [listing](<sources/$listing>) |
| Rent, upper maisonette | 700 per month | [listing](<sources/$listing>) |
| Property tax | 1,100 per year | [listing](<sources/$listing>) |
| Building insurance | 450 per year | [listing](<sources/$listing>) |
| Roof repair before letting on | 6,000, all taxes included, quoted | [Alder Roofing quote](<sources/$quote>) |
| Loan | 70 % of the price, 20 years, 4.20 % fixed, monthly annuity | [Fernbank Lending indication](<sources/$loan>) |

_Not yet underwritten._

## Units & sale status

| Unit | Area | Status |
|---|---|---|
| Ground-floor flat | 62 m2 | let |
| Upper maisonette | 48 m2 | let |

## Open questions

- The leases themselves: ask Kestrel Homes for both, to confirm the rents the listing states.
- Energy rating per unit: ask Kestrel Homes for the certificates.

## Next step

- Underwrite, then decide on an offer.

## Source documents

- \`sources/$listing\`: the agent's listing, asking price, rents and running costs.
- \`sources/$quote\`: the roofer's quote for the rear slope.
- \`sources/$loan\`: the lender's loan indication.
EOF
