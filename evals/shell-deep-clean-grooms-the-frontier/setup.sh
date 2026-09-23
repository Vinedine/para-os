#!/usr/bin/env bash
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/clean.sh"

# Push projects/acme-website/actions.md over the twelve-open-item grooming threshold: eight
# more open, undated items appended after the existing seven, so the file holds fifteen. One
# of the eight is a verbatim duplicate of an already-dated line above it - the clear "close"
# grooming has evidence for without asking the operator anything it does not already know.
# The rest split between items gated on an unfinished predecessor (demotable to a ## Backlog
# heading, per phase3-open-items.md's over-threshold rule) and items nothing gates (stay as
# checkboxes).
cat >> projects/acme-website/actions.md <<'EOF'
- [ ] Send the launch announcement to the client
- [ ] Update the sitemap once the new pages are live
- [ ] Draft the follow-up email once the launch announcement goes out
- [ ] Order the launch-day merchandise once the design is approved
- [ ] Confirm the SSL certificate renewal date with the host
- [ ] Add the client's logo to the case studies page once the case study is written
- [ ] Schedule the post-launch retrospective once the dust settles
- [ ] Chase the missing testimonial photo from the client
EOF
