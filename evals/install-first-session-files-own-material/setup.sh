#!/usr/bin/env bash
# The bootstrap run to its Finish on the operator's own material. base/ is copied in, and two
# items wait in triage/ as the operator dropped them: a scanned letter asking for a reply by
# a date, and a saved mail whose warranty holds only if a service is done by a date. The
# prompt carries every bootstrap answer, a five-line list and the approval, so the run goes
# from the questions to the brief, both items filed under the naming convention and at
# least one dated action written. Dates are relative to the day of the run.
set -e
. "$(dirname "$0")/../_fixture/kit.sh"
copy_base .

day() { date -d "$1 days" +%F 2>/dev/null || { case $1 in -*) s=$1;; *) s=+$1;; esac; date -v"${s}"d +%F; }; }

cat > triage/scan0117.txt <<EOF
NORTHGATE LETTINGS
Property management

Date: $(day -4)
Our ref: NL/T-4471
Tenancy: Flat 2, 9 Mill Lane

Dear tenant,

Rent review

Your tenancy renews on $(day 60). From that date the monthly rent rises from 1,150.00 to
1,210.00, in line with the review clause of your agreement.

To accept, sign the enclosed renewal form and return it by $(day 24). If you would like to
discuss the new rent, contact us before that date. If we have not heard from you by then,
the tenancy renews at the new rent.

Northgate Lettings, tenancy team
EOF

cat > "triage/Boiler warranty registered.eml" <<EOF
From: Marco Bellini <marco@bellini-heating.example>
To: home@example.com
Subject: Your boiler warranty is registered
Date: $(day -2)
Content-Type: text/plain; charset=utf-8

Hello,

Thanks again for having us in on $(day -9) to fit the new boiler.

The five-year warranty is now registered in your name:

Warranty number: BW-552-0918
Installed: $(day -9)
Valid until: $(day 1816)

The warranty stays valid only if the boiler has its first annual service by $(day 356).
Book it with us or any registered engineer, and keep the service record.

Best,
Marco Bellini
Bellini Plumbing and Heating
EOF
