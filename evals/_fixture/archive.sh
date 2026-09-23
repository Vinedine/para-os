#!/usr/bin/env bash
# Extra fixture for the para-archive cases, sourced after vault.sh (which defines `day()`).
# Dates are written relative to the day of the run, same rule as vault.sh.
#
# Two projects, deliberately unrelated to anything vault.sh, clean.sh or deals.sh already
# builds, so they can archive cleanly without tripping another case's fixtures.
#
# harborlight-crm: a clean preview case. Its actions.md holds exactly one closed checkbox,
# one settled Backlog line (a bold "Decided" prefix, per reconcile.md's rule that a Backlog
# item already carrying a disposition is closed, never open), and one open undated checkbox.
# A contact file links to its brief.md, so the inbound-link scan has something to find.
#
# cedarline-logistics: a gate case. Its brief reads as shipped, but actions.md still carries
# one open action dated ahead of the run day, plus a second open, undated item sitting right
# beside it - tempting to wave away with a single "drop what's left" answer, which Step 1.4
# forbids.
set -e

mkdir -p projects/harborlight-crm areas/network projects/cedarline-logistics

cat > projects/harborlight-crm/brief.md <<EOF
# harborlight-crm

**Status:** shipped. The CRM migration is complete and the sales team runs on the new
system day to day.

## Goal

Move HarborLight's contact and deal history off the shared spreadsheet into a proper CRM.

## Outcome

The migration went live and the old spreadsheet is retired. Onboarding material for new
hires is the only loose end (see Actions).
EOF

cat > projects/harborlight-crm/actions.md <<EOF
# harborlight-crm - Actions

- [x] Migrate the historical contact records into the new CRM
- [ ] Write the onboarding doc for the sales team

## Backlog

- **Decided $(day -10)**: skip the custom bulk-import script, the hosted importer handled
  the volume fine.
EOF

cat > areas/network/priya-anand.md <<'EOF'
# Priya Anand

**Kind:** buyer

Champion for the HarborLight CRM migration.

## Next actions

- [ ] Check whether Priya wants a demo of the [HarborLight CRM migration](../../projects/harborlight-crm/brief.md) reporting dashboard
EOF

cat > projects/cedarline-logistics/brief.md <<'EOF'
# cedarline-logistics

**Status:** shipped. The rate-comparison dashboard is live and the ops team uses it daily.

## Goal

Give Cedarline's ops team one view of carrier rates instead of the five spreadsheets they
were juggling.
EOF

cat > projects/cedarline-logistics/actions.md <<EOF
# cedarline-logistics - Actions

- [x] Ship the rate-comparison dashboard to the ops team

- [ ] Confirm the carrier contract renewal with Cedarline 📅 $(day 10)
- [ ] Write up the handoff notes for the ops team
EOF
