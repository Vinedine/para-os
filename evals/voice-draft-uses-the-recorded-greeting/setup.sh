#!/usr/bin/env bash
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"

# The host's whole message is staged and the vault holds the go-live window it asks for, so a
# reply is owed and every fact it needs is on file. The account it came to has a voice
# profile, pointed at from CLAUDE.md: "Hey <first name>," and "Cheers," then the first name,
# and a never-uses list of the closings and fillers a generic reply reaches for. Asked for
# that reply, the run drafts it in that voice.
cat > "triage/${recv_stamp} Re Redirect map for the launch 7e3b91.md" <<EOF
# Re: Redirect map for the launch

- **Source:** google-workspace (owner@example.com)
- **From:** Dana Host <dana@hostco.example>
- **Received:** ${received}
- **Routed:** rule: Fixture Vault Relevant when (workspace: client and supplier threads) - reply from the host on the acme launch.
- **Content:** Full body of the one message; no attachments.
- **Link:** https://mail.google.com/mail/u/0/#all/1a2b3c4d5e6f7890
- **Message id:** 1a2b3c4d5e6f7890
- **Conversation id:** 1a2b3c4d5e6f7890

Hi Noor,

The redirect map is checked and the 301s are live on staging, so nothing on our side is holding up the launch any more. Send me the go-live window and we flip DNS within it the same day.

Thanks,
Dana
EOF

cat > projects/acme-website/brief.md <<EOF
# acme-website

**Status:** launch week.

## Launch

The go-live window is $(day 3), 07:00 to 09:00, agreed with the client; the staging banner is swapped for the live one in the same window.
EOF

cat >> CLAUDE.md <<'EOF'

## Memory

A draft the operator will send also follows `para-shared/drafting.md`, installed beside the `/para-*` skills. How someone sending from this vault writes is kept apart too, once they ask: a voice profile per person in `.claude/rules/`, built per `para-shared/voice-profile.md` and pointed at in its own paragraph below.

Drafts from Noor's account are written in her voice. The full convention (Noor Visser's voice) is in [.claude/rules/voice-noor-visser.md](.claude/rules/voice-noor-visser.md), which loads only when read; read it explicitly before drafting anything in Noor's name.
EOF

mkdir -p .claude/rules
cat > .claude/rules/voice-noor-visser.md <<'EOF'
---
paths:
  - ".claude/rules/voice-noor-visser.md"
---

# Noor Visser's voice

**Accounts:** owner@example.com

How Noor writes, for any draft that goes out from the account above. Built and changed per `para-shared/voice-profile.md`, and only with Noor's approval. Built from 24 sent mails over the last 12 months, all in English.

## Fixed traits

- **Greeting:** "Hey <first name>," _inferred (23/24 samples)_
- **Sign-off:** "Cheers," then "Noor" on its own line. _inferred (20/24 samples)_
- **Sentence length:** short, rarely past 15 words; two paragraphs at most. _inferred (21/24 samples)_
- **Contractions:** always: "I'll", "we'll", "don't". _inferred (22/24 samples)_
- **Where the ask lands:** the first line, as a question. _inferred (18/24 samples)_
- **Her own service:** "the studio", never "our team". _inferred (11/24 samples)_

## Tone by recipient

- **A supplier** (hosting, DNS, copy): first names, no pleasantries, the date or time in the sentence that needs it. _inferred (9/9 samples)_

## Never uses

- "I hope this finds you well" _inferred (0/24 samples)_
- "Please don't hesitate to reach out" _inferred (0/24 samples)_
- "Thanks in advance" _inferred (0/24 samples)_
- "Looking forward to hearing from you" _inferred (0/24 samples)_
- "Let me know if you have any questions" _inferred (0/24 samples)_
- "Best regards", "Kind regards" _inferred (0/24 samples)_
- "Great news" _operator (2026-01-12, "I never open with great news, just say the thing")_

## Sample

```text
Hey [supplier contact],

Can you renew the certificate before Friday? It lapses on the 14th and the launch is the week after.

Cheers,
Noor
```
EOF
