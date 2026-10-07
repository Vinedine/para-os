#!/usr/bin/env bash
# The shared vault plus a week to look back on: three closes inside it, one before it and two
# with no completion date, a deal that entered a stage inside it, and two development-log
# entries, one inside the week and one before it. The domain renewal the shared vault dates
# five days ago is the deadline the week let slip.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"

cat >> CLAUDE.md <<'EOF'

## Deal lifecycle

| Stage | PARA home |
|---|---|
| Qualified, Proposal | `resources/ideas/<company>/` |
| Lost | `archive/ideas/<company>/` |
EOF

cat > resources/ideas/orchard-labs/brief.md <<EOF
# orchard-labs

**Stage:** Proposal (since $(day -2))

A boiler installer who wants their quoting flow rebuilt.
EOF

cat >> projects/acme-website/actions.md <<EOF

## Done

- [x] Sign off the homepage design with the client ✅ $(day -2)
- [x] Move the DNS to the new host ✅ $(day -4)
- [x] Migrate the old newsletter list ✅ $(day -20)
- [x] Set up the staging server
EOF

cat >> areas/business/actions.md <<EOF

## Done

- [x] File the quarterly VAT return ✅ $(day -1)
- [x] Order new business cards
EOF

cat > projects/acme-website/brief.md <<EOF
# acme-website

Relaunch the client's website on a hosted shop platform.

## Development log

- **$(day -30)** Kept the old URL structure, so the blog needs no redirect map.
- **$(day -3)** Chose the hosted checkout over a custom cart: the client's order volume does not justify the card-data compliance work.
EOF
