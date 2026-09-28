#!/usr/bin/env bash
# A first mail from a prospect that no register row, deal folder or contact file holds yet,
# staged the way /para-ingest writes one, in a vault carrying the sales module's lead
# register (deals.sh). The mail settles every cell an open row carries: the company, who
# wrote, how they found the studio, and the call they ask for. So the right disposition is
# one new row in areas/business/leads.md, shown in full, with no placeholder in it; before
# the action existed the only answer a run could give was Leave in triage.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/deals.sh"

rm -f triage/*.md
touch triage/.gitkeep

recv_day=$(day -1)
recv_stamp=$(printf '%s' "$recv_day" | tr -d '-')
received="${recv_day}T10:02:00+02:00"

cat > "triage/${recv_stamp} Online booking for our clinics 5c1d8e.md" <<EOF
# Online booking for our clinics

- **Source:** google-workspace (owner@example.com)
- **From:** Sara Lindqvist <sara@lindqvist-dental.example>
- **Received:** ${received}
- **Routed:** rule: Fixture Vault Relevant when (workspace: new enquiries) - a first enquiry from a clinic group.
- **Content:** Full body of the one message; no attachments.
- **Link:** https://mail.google.com/mail/u/0/#all/2b3c4d5e6f708192
- **Message id:** 2b3c4d5e6f708192
- **Conversation id:** 2b3c4d5e6f708192

Hi,

I found your studio through your website. We run three dental clinics in town, Lindqvist
Dental, and our patients still book every appointment by phone. We would like an online
booking page before the new year.

Could we have a 30-minute intro call next week? Tuesday or Thursday morning works for me.

Best,
Sara Lindqvist
Practice manager, Lindqvist Dental
EOF
