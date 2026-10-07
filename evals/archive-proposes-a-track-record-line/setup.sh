#!/usr/bin/env bash
# kestrel-invoicing shipped and every action is closed, so the run has nothing to reconcile
# and reaches Step 9. The README's Track record holds one line per engagement, each linking
# its archived brief: the shape the new line should match. The brief carries a figure (days
# to payment) the line should link to rather than copy, and a Lessons section that nothing
# reads once the brief is archived, with a playbook in resources/ on the same kind of work
# as the live home for them.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"

cat > README.md <<'EOF'
# Fixture Vault

## Identity

A one-person studio building small tools for local trade businesses.

## Operating model

Fixed-price builds for small firms, each delivered in a few weeks and handed over to the
client's own team.

## Track record

One line per engagement; each brief holds the detail.

- **Template revision** for the studio's own vault kit: shipped with every action closed. [Brief](archive/projects/para-os-2026-09-03/brief.md)

## Vision

Keep the websites earning and the tooling shipping, with the least admin possible.
EOF

mkdir -p projects/kestrel-invoicing resources/playbooks

cat > projects/kestrel-invoicing/brief.md <<EOF
# kestrel-invoicing

**Status:** shipped. Kestrel Joinery sends every invoice from the hosted invoicing tool, and
the old spreadsheet is retired.

## Goal

Move Kestrel Joinery's invoicing off a shared spreadsheet, so an invoice goes out the day a
job closes instead of at month end.

## Outcome

Live since $(day -20). Average days to payment fell from 41 to 19 _(as of $(day -3))_, read
from the invoicing tool's aged-debt report.

## Lessons

- The two-week parallel run, old spreadsheet beside the new tool, caught a rounding error in
  the tax lines before any client saw it. Keep a parallel run on every billing migration.
- The bookkeeper signed off the invoice template only after it was built, and asked for
  three changes. Get her sign-off on a mock-up first.
EOF

cat > projects/kestrel-invoicing/actions.md <<EOF
# kestrel-invoicing - Actions

- [x] Configure the hosted invoicing tool with Kestrel's price list ✅ $(day -40)
- [x] Run the old spreadsheet and the new tool side by side for two weeks ✅ $(day -22)
- [x] Switch Kestrel to the new tool and retire the spreadsheet ✅ $(day -20)
EOF

cat > resources/playbooks/tool-rollouts.md <<'EOF'
# Tool rollouts

How a client's team moves onto a new tool, learned job by job.

- Train the person who will run it day to day, not only the owner who signed.
- Keep the old system readable for a month after the switch.
EOF
