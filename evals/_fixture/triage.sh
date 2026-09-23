#!/usr/bin/env bash
# Extra fixture for the para-triage cases, sourced after vault.sh (which defines `day()`).
# Dates are written relative to the day of the run, same rule as vault.sh.
#
# vault.sh always plants one loose note in triage/, dated off the real system clock rather
# than run-relative, so a triage-focused case would otherwise carry an extra unexplained
# item nobody asked about. Clear it first: what these cases test is the note added below.
#
# The note is staged the way /para-ingest actually writes one (references/staging.md in the
# multi-vault/para-ingest skill): the header shape, the filename convention, and the
# Content line that says it is a snippet only. It bears on the redirect-map action
# vault.sh's acme-website/actions.md already carries, so the right disposition is Update
# existing on that file, never a fresh file into sources/.
set -e

rm -f triage/*.md
mkdir -p triage
touch triage/.gitkeep

cat >> CLAUDE.md <<'EOF'

## Filing

Source documents: `YYYYMMDD <Subject> - <Description>.<ext>` into the owning entity's
`sources/`.
EOF

recv_day=$(day -1)
recv_stamp=$(printf '%s' "$recv_day" | tr -d '-')
received="${recv_day}T09:14:00+02:00"

cat > "triage/${recv_stamp} Re Redirect map for the launch 7e3b91.md" <<EOF
# Re: Redirect map for the launch

- **Source:** google-workspace (owner@example.com)
- **From:** Dana Host <dana@hostco.example>
- **Received:** ${received}
- **Routed:** rule: Fixture Vault Relevant when (workspace: client and supplier threads) - reply from the host on the acme launch.
- **Content:** Snippet only: the ~200-character preview the search returns; the body was not read.
- **Link:** https://mail.google.com/mail/u/0/#all/1a2b3c4d5e6f7890

Hi - the redirect map is checked and the 301s are live on staging. Send me the go-live window and we flip DNS the same day...
EOF
