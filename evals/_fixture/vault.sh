#!/usr/bin/env bash
# Build a small vault in the run's empty workspace. Dates are written relative to the day
# the run happens, so a case scores the same whenever it runs. GNU date (Git Bash, Linux);
# a BSD date needs its own -v form.
#
# The shape is deliberate. Six items fall due inside the week, which is more than a brief
# may list, so the five-item cap has something to bite on. Nine of the sixteen open items
# carry no date, so the undated-majority flag fires. One item in a contact file names a
# project without belonging to it, so a scope has something to mistake for its own work.
set -e
day() { date -d "$1 days" +%F 2>/dev/null || { case $1 in -*) s=$1;; *) s=+$1;; esac; date -v"${s}"d +%F; }; }

cat > CLAUDE.md <<'EOF'
# Fixture Vault Conventions

**Type:** vault

## Actions

A checkbox may live in `projects/` and `areas/` only, never in `resources/`, and every
checkbox under `archive/` must be closed. Before appending to a file that already holds
12 or more open items, say so and propose grooming instead of adding.
EOF

cat > README.md <<'EOF'
# Fixture Vault

## Identity

A test vault for eval runs.

## Vision

Keep the websites earning and the tooling shipping, with the least admin possible.
EOF

mkdir -p projects/acme-website projects/para-os-2026-09-04 areas/business areas/network
mkdir -p archive/projects/para-os-2026-09-03 resources/ideas/orchard-labs triage

cat > projects/acme-website/actions.md <<EOF
# acme-website - Actions

## Launch

- [ ] Renew the acme.example domain before it lapses 🔺 📅 $(day -5)
- [ ] Send the launch announcement to the client 📅 $(day 0)
- [ ] Brief the copywriter on the pricing page 📅 $(day 1)
- [ ] Check the redirect map with the host 📅 $(day 2)
- [ ] Swap the staging banner for the live one 📅 $(day 3)
- [ ] Write the case study once traffic settles
- [ ] Ask the client for a testimonial
EOF

cat > projects/para-os-2026-09-04/actions.md <<'EOF'
# para-os-2026-09-04 - Actions

- [ ] Bootstrap the one-prompt quickstart so an empty folder becomes a working vault
- [ ] Drop the credential negation from the template gitignore
- [ ] Align what every mail source treats as a candidate message
- [ ] Plan the revision after this one, some time in Q4 2026
EOF

cat > areas/business/actions.md <<EOF
# business - Actions

## Next actions

- [ ] Chase the unpaid invoice from the spring engagement 📅 $(day -40)
- [ ] Decide whether to renew the accounting subscription

## Recurring

- [ ] Review the pipeline 🔁 every week 📅 $(day 2)
EOF

cat > areas/network/jan-janssen.md <<'EOF'
# Jan Janssen

**Kind:** buyer

Met at a meetup. Runs a mid-size installer.

## Next actions

- [ ] Ask Jan whether he wants a walkthrough of the para-os-2026-09-04 quickstart
- [ ] Send Jan the acme launch date
EOF

cat > archive/projects/para-os-2026-09-03/brief.md <<'EOF'
# para-os-2026-09-03

**Status:** shipped and archived. Every item across its four action files is closed.

## Goal

The template revision before the current one.
EOF

cat > resources/ideas/orchard-labs/brief.md <<'EOF'
# orchard-labs

**Stage:** Proposal

A boiler installer who wants their quoting flow rebuilt.
EOF

printf 'A note waiting to be filed.\n' > "triage/$(date +%Y%m%d) Meetup - Follow-ups.md"
