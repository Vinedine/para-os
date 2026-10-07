#!/usr/bin/env bash
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"

# The host's whole message is staged, a colleague on copy, and the vault holds the go-live
# window it asks for, so a reply is owed and every fact it needs is on file. Asked for that
# reply, the run drafts one addressed to the thread's own addresses, To and Cc, in plain
# text with each paragraph on one line. The note's own paragraphs are single lines, so a
# hard wrap in the answer is the draft's and never a quote of the mail.
cat > "triage/${recv_stamp} Re Redirect map for the launch 7e3b91.md" <<EOF
# Re: Redirect map for the launch

- **Source:** google-workspace (owner@example.com)
- **From:** Dana Host <dana@hostco.example>
- **Received:** ${received}
- **Routed:** rule: Fixture Vault Relevant when (workspace: client and supplier threads) - reply from the host on the acme launch.
- **Content:** Full body of the one message, its Cc line included; no attachments.
- **Link:** https://mail.google.com/mail/u/0/#all/1a2b3c4d5e6f7890
- **Message id:** 1a2b3c4d5e6f7890
- **Conversation id:** 1a2b3c4d5e6f7890

Cc: Lee Park <lee@hostco.example>

Hi,

The redirect map is checked and the 301s are live on staging, so nothing on our side is holding up the launch any more. Send me the go-live window and we flip DNS within it the same day.

I have copied Lee, who runs the DNS change on our side, so please keep him on your reply.

Thanks,
Dana
EOF

cat > projects/acme-website/brief.md <<EOF
# acme-website

**Status:** launch week.

## Launch

The go-live window is $(day 3), 07:00 to 09:00, agreed with the client; the staging banner is swapped for the live one in the same window.
EOF
