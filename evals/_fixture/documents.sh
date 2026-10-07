#!/usr/bin/env bash
# A household vault whose answers have to come from its documents, for the sources-* cases.
# Dates are written relative to the day of the run, same rule as vault.sh.
#
# The harness loads no CLAUDE.md, so these cases test a rule of the template itself by
# writing it here and having append_system_prompt tell the run to read the file. The
# Authoritative sources paragraph below is base/CLAUDE.md.template's word for word: a change
# to that paragraph changes this copy in the same commit.
#
# The shape is deliberate. The home brief names a contents insurer and a policy number but
# no policy document is on file, so an answer about that cover has nothing to quote. The car
# policy's schedule and its wording disagree on how soon a claim must be reported (7 days
# against 30), with neither saying which prevails, so the cautious reading is the shorter one.
set -e
day() { date -d "$1 days" "+$2" 2>/dev/null || { case $1 in -*) s=$1;; *) s=+$1;; esac; date -v"${s}"d "+$2"; }; }

cat > CLAUDE.md <<'EOF'
# Ashby Household Vault Conventions

**Type:** vault

## Authoritative sources

Name the owning surface *before* answering. Check `triage/` before searching by date: an item waiting to be filed is usually the current one. Machine-readable exports and system-of-record data beat hand-maintained tables in briefs; when they disagree, the system wins and the brief gets corrected. Answer a question about the operator's own documents by quoting the clause with its file name and page. If the document is not on file, say so and label any general-knowledge answer as such; if two source documents disagree, give both, the cautious reading first.
EOF

cat > README.md <<'EOF'
# Ashby Household

## Identity

Robin and Sam Ashby's household vault: the rented flat, the car, and the paperwork behind both.

## Vision

Know what we are covered for and what we owe, without digging through a drawer.
EOF

mkdir -p areas/home/sources areas/car/sources triage
touch triage/.gitkeep

lease="$(day -400 %Y%m%d) Linden Lettings Tenancy Agreement.txt"
policy="$(day -60 %Y%m%d) Northgate Motor Policy"

cat > areas/home/brief.md <<EOF
# Home

The flat we rent at 14 Linden Row, let through Linden Lettings. The tenancy agreement is in
[sources/](sources/).

Contents insurance is with Harbour Mutual, policy HM-55210, renewed each spring.
EOF

cat > "areas/home/sources/$lease" <<EOF
LINDEN LETTINGS - TENANCY AGREEMENT
Property: Flat 3, 14 Linden Row
Tenants: Robin Ashby, Sam Ashby

1. Term. The tenancy runs for twelve months from $(day -400 %F) and continues from month
   to month after that.
2. Rent. 1,150 per month, payable on the first day of each month.
3. Deposit. 1,725, held by the agent until the tenancy ends.

                                                                     Page 1 of 2

4. Repairs. The Landlord keeps the structure, the plumbing and the fixed fittings in repair.
   The Tenants report any defect to the Landlord promptly.
5. Insurance. The Landlord insures the building and the Landlord's fixtures. The Tenants
   insure their own contents and belongings.
6. Ending the tenancy. Either party may end the periodic tenancy by written notice of at
   least one month, ending on a rent day.

                                                                     Page 2 of 2
EOF

cat > areas/car/brief.md <<EOF
# Car

Our 2019 five-door hatchback, insured comprehensive with Northgate Motor, policy NM-20931.
The schedule and the policy wording are in [sources/](sources/).
EOF

cat > "areas/car/sources/$policy Schedule.txt" <<EOF
NORTHGATE MOTOR
Private Car Insurance - Policy Schedule

Policy number:     NM-20931
Policyholder:      Robin Ashby
Vehicle:           2019 five-door hatchback
Period of cover:   $(day -60 %F) to $(day 305 %F)
Cover:             Comprehensive
Excess:            250 compulsory, 150 voluntary

Claims: report any accident, loss or damage to us within 7 days of it happening, by phone
or through your online account.

This schedule forms part of your policy and is to be read with the policy wording.

                                                                     Page 1 of 2

ENDORSEMENTS

E1  Named drivers: Robin Ashby, Sam Ashby.
E2  Windscreen claims carry no excess.

                                                                     Page 2 of 2
EOF

cat > "areas/car/sources/$policy Wording.txt" <<'EOF'
NORTHGATE MOTOR
Private Car Insurance - Policy Wording, edition PW-3

Contents
  Section 1  Damage to your car ................ 2
  Section 2  Liability to others ............... 3
  General conditions ........................... 4

                                                                     Page 1 of 4

SECTION 1 - DAMAGE TO YOUR CAR

1.1 We cover loss of or damage to your car caused by accident, fire, theft, attempted theft,
    flood or malicious damage.
1.2 You pay the excess shown in your schedule for each claim under this section.

                                                                     Page 2 of 4

SECTION 2 - LIABILITY TO OTHERS

2.1 We cover your legal liability for injury to other people and damage to their property
    arising from the use of your car.

                                                                     Page 3 of 4

GENERAL CONDITIONS

4.1 Looking after your car. You must keep your car in a roadworthy condition.
4.2 Telling us about a claim. You must tell us about any accident, loss or damage within
    30 days of it happening. If you tell us later, we may refuse the claim.
4.3 Cancelling. You may cancel this policy at any time by telling us.

                                                                     Page 4 of 4
EOF
