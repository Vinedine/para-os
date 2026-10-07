#!/usr/bin/env bash
# A scanned letter from the tax office, read into text, asking for documents by a reply-by
# date that no open line tracks. The right disposition is File it + add action: the letter
# into areas/business, and one line in areas/business/actions.md dated on the reply-by day,
# linking the filed letter. The letter is dated the 1st of this month and asks for a reply
# by the 28th of next month, so a line dated on the letter's own day is told apart from
# the right one whenever the case runs.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"

rm -f triage/*.md

issued=$(date +%Y-%m-01)
reply_by=$(date -d "$issued +1 month" +%Y-%m-28 2>/dev/null || date -v1d -v+1m +%Y-%m-28)

cat > triage/scan0042.txt <<EOF
TAX OFFICE - BUSINESS TAXES
Reference: TX-2219-0457
Date: ${issued}

To: Fixture Studio

Request for information: tax return for the last quarter

We are reviewing the tax return your business filed for the last quarter. Please send us
copies of the purchase invoices behind the expenses you deducted, with a short explanation
of the hardware purchase recorded in that period.

Reply by: ${reply_by}

If we have not received your reply by that date, we will assess the return on the
information we hold. Quote the reference above on every page you send.

Business Taxes Team
EOF
