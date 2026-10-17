#!/usr/bin/env bash
# An export of another tool's history, the studio's task board, saved into triage/. Its four
# entries carry facts about two entities: what was agreed with orchard-labs on the quoting
# rebuild, and two steps done for the acme-website launch. The board keeps the history, so
# the file is no record of its own: the right disposition folds its facts into both briefs as
# follow-on edits, each citing the export, then asks to delete it as Delete (no lasting
# value), never files it into a sources/ folder.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"
rm -f triage/*.md

cat > projects/acme-website/brief.md <<'EOF'
# acme-website

**Status:** launch week.

## Launch

The client's site moves to the new build at launch; the host runs the DNS change.
EOF

cat > triage/taskboard-export.csv <<EOF
board,card,date,author,event,text
Studio clients,orchard-labs quoting rebuild,$(day -9),owner,comment,"Scoped with the client: they quote by hand from one spreadsheet of about 1,400 supplier prices and want a quote out in under five minutes."
Studio clients,orchard-labs quoting rebuild,$(day -6),owner,comment,"Agreed with the client: the supplier price list is imported as a CSV each month, never retyped."
Studio clients,acme-website launch,$(day -5),owner,comment,"DNS cutover rehearsed on staging with the host; a rollback takes ten minutes."
Studio clients,acme-website launch,$(day -3),owner,checklist,"Goal tracking set up for the contact form and the pricing page."
EOF
