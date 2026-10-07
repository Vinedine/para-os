#!/usr/bin/env bash
# An insurance policy schedule, scanned into text, for a policy that renews for another year
# on the 1st of the month five months out unless cancelled with three months' notice.
# Nothing tracks it. The right disposition is File it + add action, the line dated on the
# last day to give notice (three calendar months before the renewal: the 1st of the month
# two months out), with the renewal date in its text. A line dated on the renewal itself
# comes due when the notice is three months too late.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"

rm -f triage/*.md

first() { date -d "$(date +%Y-%m-01) $1 months" +%F 2>/dev/null || date -v1d -v"$1"m +%F; }
before() { date -d "$1 -$2 days" +%F 2>/dev/null || date -j -v-"$2"d -f %F "$1" +%F; }
renewal=$(first +5)
start=$(first -7)
end=$(before "$renewal" 1)
issued=$(before "$start" 12)

cat > triage/scan0043.txt <<EOF
LARKSPUR MUTUAL - POLICY SCHEDULE

Policy number: BC-77810
Policyholder: Fixture Studio
Issued: ${issued}

Cover: office contents and professional liability
Period of insurance: ${start} to ${end}
Annual premium: 1,240.00, collected by direct debit at each renewal

Renewal
The policy renews automatically for a further year on ${renewal}. Either party may end it
at the renewal date by written notice reaching the other at least three months before the
renewal date.
EOF
