#!/usr/bin/env bash
# A real-estate vault for the property-* cases: the flavor's CLAUDE.md sections, its rule
# files and skeleton as this checkout has them (through kit/), a filled-in source register
# and an analyst persona. Each case writes its own dossier. Dates are written relative to
# the day of the run, same rule as vault.sh.
#
# `kit/base` and `kit/real-estate` are symlinks into the repo, so a case reads the rules and
# the deal-sheet template under review. A checkout made with symlinks off holds a one-line
# text file at each instead: stop with that reason, as kit.sh does.
#
# The register and persona fix every rate a figure needs, so no derived figure has to be
# guessed: transfer tax and conveyancing as percentages of the price, the persona's
# allowances as percentages of the rent, its yield bar, its cover bar and the rule that
# turns them into a bid zone and a walk-away.
set -e
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/kit"
if [ ! -f "$KIT/real-estate/CLAUDE.md.sections" ] || [ ! -f "$KIT/base/.claude/rules/filing.md" ]; then
  echo "evals/_fixture/kit holds no kit: this checkout has symlinks off." >&2
  echo "Enable git's core.symlinks and check out again, or run the case under WSL2." >&2
  exit 1
fi
day() { date -d "$1 days" "+$2" 2>/dev/null || { case $1 in -*) s=$1;; *) s=+$1;; esac; date -v"${s}"d "+$2"; }; }

{
  printf '# Harrow Lane Property Vault Conventions\n\n**Type:** vault\n**Flavor:** real-estate\n'
  sed '/^<!--/,/-->$/d' "$KIT/real-estate/CLAUDE.md.sections" | grep -v '{{'
} > CLAUDE.md

cat > README.md <<'EOF'
# Harrow Lane Property

## Identity

Fixture Holdings buys small residential buildings, mostly to keep them let, now and then to renovate and sell.

## Vision

A portfolio whose rents carry its loans with room to spare.
EOF

mkdir -p .claude/rules triage
touch triage/.gitkeep
cp "$KIT/base/.claude/rules/figures.md" "$KIT/base/.claude/rules/filing.md" .claude/rules/
cp "$KIT/real-estate/.claude/rules/"*.md .claude/rules/
cp -R "$KIT/real-estate/skeleton/." .

cat > resources/property-evaluation/property-data-sources.md <<'EOF'
# Property data sources

Where property facts come from in the fixture jurisdiction, what each source can and cannot answer, and what it costs. The property skills take every local fact from this file: a registry, a document, a tax or a portal it does not name is never assumed.

## What each source answers

| Question | Source | Access |
|---|---|---|
| Parcel or title identifier, buildings on the parcel | Land registry extract | paid |
| Energy rating | The seller's certificates, via the agent | free |
| Asking prices and listings | The agent's own listing | free |
| Closed sale prices | Land registry price extract | paid |

**Access** is one of three values, and the skills act on it: **free** is looked up; **login** sits behind a personal login, is never scripted, and is exported by the operator; **paid** is settled only by a paid request, named as a next step and never searched for.

## Facts no free source settles

- Closed sale prices nearby: a land registry price extract, ordered by the conveyancer once an offer is accepted.

## Transaction and holding costs

| Cost | Rate or amount | Basis |
|---|---|---|
| Transfer tax on purchase | 6 % | of the price, paid by the buyer |
| Conveyancing (the notary who executes the deed) | 1.2 % plus 900 | of the price, plus a fixed fee per deed |
| Agent fee on sale | 2 % | of the sale price |
| Annual property tax | as the dossier states it | the current assessment |

## Traps

- A listing's rents are the seller's claim until the leases are read.
EOF

mkdir -p resources/prompts/analyst/adapters resources/prompts/analyst/knowledge
cat > resources/prompts/analyst/analyst.core.md <<'EOF'
# Analyst

Underwrites a let residential building for Fixture Holdings, which buys to hold.

## How a deal is measured

- **All-in cost basis**: price, transfer tax, conveyancing, and any works before the units are let on.
- **Gross yield**: annual rent as let, over the price.
- **Net operating income**: annual rent less a vacancy allowance of 4 % of it, a maintenance allowance of 8 % of it, the property tax and the building insurance.
- **Net yield**: net operating income over the all-in cost basis. The bar is 6.0 %.
- **Debt service cover**: net operating income over a year of loan payments. The bar is 1.25.
- **Cash-on-cash**: net operating income less a year of loan payments, over the cash put in (the all-in cost basis less the loan).

## Scenarios

One base case on the rents as let, one downside with every rent 10 % lower and the vacancy allowance at 8 %.

## Bid zone and walk-away

The walk-away is the price at which the base case's net yield is exactly the bar. The opening bid is the price at which it is 6.5 %. The loan is taken at 70 % of the price, on the lender's terms in the dossier, and the cover is checked at both prices.

## Guardrails

- Never bid above the walk-away.
- A deal that clears the yield bar but not the cover bar is conditional on better loan terms.
EOF

cat > resources/prompts/analyst/adapters/claude-code.md <<'EOF'
# Analyst, in Claude Code

Read `../analyst.core.md` and every file in `../knowledge/` before the first figure. Answer as the analyst: the figures first, the verdict last, and every assumption named.
EOF

cat > resources/prompts/analyst/knowledge/tax-and-structure.md <<'EOF'
# Tax and structure

- Every purchase is made by Fixture Holdings, the company, never by its owners in person.
- The company pays 25 % on its profit: rent less running costs and loan interest, and a sale's margin. Loan principal is not deductible.
EOF
