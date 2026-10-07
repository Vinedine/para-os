#!/usr/bin/env bash
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/shared.sh"

# The template's ## Memory paragraph word for word, para-shared installed beside it, and six
# of the operator's sent mails exported to sent-export/. Every mail ends in the same
# auto-signature, which opens on "Best regards," above her name block; the closing she types
# herself is "Cheers," in five and "Thanks," in one. Two carry the other side's quoted reply
# (closing "Warm regards" and "Kind regards"), and one is a forward. Asked to build her voice
# profile and show it unsaved, the run shows the file with her typed closing as the sign-off,
# neither the signature's nor a correspondent's, and the CLAUDE.md paragraph pointing at it.
# Unsaved because a run with no one present cannot write under .claude/: Claude Code asks
# before every such write, and a non-interactive run takes the ask as a refusal.
cat >> CLAUDE.md <<'EOF'

## Memory

This vault on disk IS the memory. Do not use the agent's built-in memory feature, and do not create a `memory/` folder or session-log files. Durable facts belong in the file they describe: conventions here, identity and operating model in `README.md`, everything else in the relevant project, idea, or contact note. How the operator likes to work (tone, format, what to lead with or leave out) is kept apart from those files: it is in [.claude/rules/working-preferences.md](.claude/rules/working-preferences.md), which loads on its own when any vault file is read; read it explicitly before drafting anything for the operator. It changes only with the operator's approval. A draft the operator will send also follows `para-shared/drafting.md`, installed beside the `/para-*` skills. How someone sending from this vault writes is kept apart too, once they ask: a voice profile per person in `.claude/rules/`, built per `para-shared/voice-profile.md` and pointed at in its own paragraph below.
EOF

mkdir -p .claude/rules sent-export
cat > .claude/rules/working-preferences.md <<'EOF'
---
paths:
  - "**"
---

# Working preferences

## Preferences

_None yet._
EOF

signature() {
  printf '\n-- \n'
  cat <<'EOF'
Best regards,
Noor Visser | Founder
Visser Web Studio | visserweb.example | +32 470 12 34 56

This message may contain confidential information and is intended only for the addressee. If you received it in error, please delete it and notify the sender.
EOF
}

mail() {   # mail <file> <to> <subject> <days ago>, body on stdin
  {
    printf 'From: Noor Visser <owner@example.com>\nTo: %s\nDate: %s\nSubject: %s\n\n' \
      "$2" "$(day "-$4")" "$3"
    cat
  } > "sent-export/$1"
}

mail 01-dns-records.eml "Dana Host <dana@hostco.example>" "Re: Launch checklist" 40 <<EOF
Hey Dana,

Could you send me the DNS records for the acme launch by Thursday? I'll set up the redirects the same day.

Cheers,
Noor
$(signature)

On $(day -41), Dana Host <dana@hostco.example> wrote:
> Hi Noor,
> Hope you're keeping well! Just checking in on where we are with the launch, no pressure at all.
> Warm regards,
> Dana
EOF

mail 02-launch-call.eml "Jan Janssen <jan@installer.example>" "Launch call" 33 <<EOF
Hey Jan,

Can we move Tuesday's call to Friday? Nothing's wrong, I just want the redirect map checked first.

Cheers,
Noor
$(signature)
EOF

mail 03-pricing-brief.eml "Sam Writer <sam@copy.example>" "Pricing page brief" 27 <<EOF
Hey Sam,

The pricing page brief is below. Keep it short: the client reads everything on a phone.

Three tiers, one sentence each, and no "contact us for a quote" anywhere.

Cheers,
Noor
$(signature)
EOF

mail 04-spring-invoice.eml "Lies Boek <lies@accounts.example>" "Spring invoice" 20 <<EOF
Hey Lies,

Did the spring invoice ever get paid? I can't find it in the statements.

Thanks,
Noor
$(signature)
EOF

mail 05-quote.eml "Marta Orchard <marta@orchardlabs.example>" "Re: Quoting flow" 12 <<EOF
Hey Marta,

Thanks for the call. I'll send the quote for the new quoting flow by Monday, and it won't run past two pages.

Cheers,
Noor
$(signature)

On $(day -13), Marta Orchard <marta@orchardlabs.example> wrote:
> Dear Noor,
> Thank you for your time today. I look forward to hearing from you at your earliest convenience.
> Kind regards,
> Marta
EOF

mail 06-fwd-hosting.eml "Lee Park <lee@hostco.example>" "Fwd: Hosting renewal" 5 <<EOF
Hey Lee,

See below. Can you check the renewal date before Friday? I'd rather not find out the hard way.

Cheers,
Noor
$(signature)

---------- Forwarded message ---------
From: Billing <billing@hostco.example>
Date: $(day -6)
Subject: Hosting renewal

Dear customer,

We are delighted to inform you that your hosting plan renews soon. Should you have any questions, please do not hesitate to contact us.

Best wishes,
The HostCo Billing Team
EOF
