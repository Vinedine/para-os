#!/usr/bin/env bash
# A flip at Prospecting, underwritten before the vault's derived-figure rule: every fact the
# readiness check names is there, and so is every cost line, but the dossier never states
# the cost basis they add up to, nor the gross margin in either scenario. The template's flip
# variant prints both. The right run stops on them as gaps for /property-underwrite and builds
# nothing; adding the lines up itself (250,460, and a gross margin of 44,540) is the
# silent recompute the rule forbids.
set -e
. "$(dirname "$0")/../_fixture/property.sh"

p=resources/ideas/22-mill-row
mkdir -p "$p/sources"
listing="$(day -40 %Y%m%d) Kestrel Homes Listing.txt"
extract="$(day -30 %Y%m%d) Land Registry Extract.txt"
quote="$(day -20 %Y%m%d) Brightwell Builders Quote.txt"
energy="$(day -20 %Y%m%d) Energy Certificate.txt"

cat > "$p/sources/$listing" <<'EOF'
KESTREL HOMES - FOR SALE
22 Mill Row: a two-storey house for full renovation. Asking price: 189,000.
Sold by the executor of the late owner's estate.
EOF
cat > "$p/sources/$extract" <<'EOF'
LAND REGISTRY EXTRACT
Parcel MR-2290-22, 22 Mill Row. One building, one dwelling.
EOF
cat > "$p/sources/$quote" <<'EOF'
BRIGHTWELL BUILDERS - QUOTE
22 Mill Row: rewiring, new heating, kitchen, bathroom, plaster and decoration.
Total: 42,000.00, all taxes included.
EOF
cat > "$p/sources/$energy" <<'EOF'
ENERGY CERTIFICATE
22 Mill Row. Rating: E.
EOF

cat > "$p/brief.md" <<EOF
# 22 Mill Row

**Stage:** Prospecting (since $(day -40 %F); offer due $(day 7 %F))
**Opened:** $(day -40 %F)
**Source:** Kestrel Homes, listing
**Last touch:** $(day -2 %F), second viewing with the agent

## Snapshot

A two-storey house for full renovation, parcel MR-2290-22, one building and one dwelling ([land registry extract](<sources/$extract>)). Listed by Kestrel Homes at 189,000 for the executor of the late owner's estate. The plan is a flip: buy through Fixture Holdings, renovate, sell. Stage: Prospecting.

## Deal economics

### Projected

| Line | Amount | Source |
|---|---|---|
| Purchase, at the walk-away | 180,000 | the underwriting below |
| Transfer tax, 6 % of the price | 10,800 | the source register |
| Conveyancing, 1.2 % of the price plus 900 | 3,060 | the source register |
| Renovation, quoted 42,000 plus 10 % contingency | 46,200 | [Brightwell Builders quote](<sources/$quote>) |
| Holding and selling: agent fee 2 % of 295,000 (5,900), six months of tax, insurance and utilities (4,500, estimate) | 10,400 | the source register; estimate |
| Sale, after repair | 295,000 | three asking prices nearby, asking not closed |

### Underwriting ($(day -4 %F))

| Scenario | Renovation | Sale | After-tax margin |
|---|---|---|---|
| Base | 46,200 | 295,000 | 33,405 |
| Downside | 52,000 | 275,000 | 14,355 |

Taxed at 25 % in Fixture Holdings. **Verdict: conditional go.** Open at 165,000 and walk away above 180,000, conditional on a structural survey.

## Parties

- Agent: Kestrel Homes.
- Seller: the executor of the late owner's estate, through Holt & Rae, solicitors.
- Deed: Marsh & Pell, notaries.

## Financing

Cash from Fixture Holdings' reserves; no loan.

## Permits & compliance

No permit needed for the scope quoted. Energy rating E ([certificate](<sources/$energy>)).

## Renovation scope

| Item | Quoted |
|---|---|
| Rewiring, new heating, kitchen, bathroom, plaster and decoration | 42,000, all taxes included ([Brightwell Builders](<sources/$quote>)) |

## Open questions

- Structural survey: order one before the offer.
- Closed sale prices nearby: a land registry price extract, ordered on acceptance.

## Next step

- Offer at 165,000 by $(day 7 %F).

## Source documents

- \`sources/$listing\`: the listing.
- \`sources/$extract\`: the parcel and its one dwelling.
- \`sources/$quote\`: the renovation quote.
- \`sources/$energy\`: the energy rating.
EOF
