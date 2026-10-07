#!/usr/bin/env bash
# A recorder note of a call on northwind-quoting, the Proposal-stage deal deals.sh builds,
# two days after its Last touch. The call names the signer, who has read the proposal, and
# dates the next meeting: the Proposal stage's exit criterion. It gives the studio two
# commitments and the client two of its own, as checkboxes in the recorder's summary.
#
# So filing it carries the meeting follow-ons: Last touch moved to the call's date, shown
# beside the current value; Signer named; one next step, the studio's earliest commitment,
# on the champion's card (the vault declares no areas/network/ row, so the card takes any
# action); a stage question, never a Stage edit; and a draft carrying the champion's address
# from her card, on To or Cc. The signer's address is only ever spoken in the transcript, so
# it is no recipient.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/deals.sh"

rm -f triage/*.md
touch triage/.gitkeep

cat >> CLAUDE.md <<'EOF'

## Filing

Source documents: `YYYYMMDD <Subject> - <Description>.<ext>` into the owning entity's
`sources/`.
EOF

cat > areas/network/pia-vermeer.md <<EOF
# Pia Vermeer

**Kind:** buyer

Ops lead at northwind-quoting, the champion pushing the rebuild internally. Email: pia.vermeer@northwind-quoting.example

## Next actions

- [ ] Confirm the signer with Pia before the price hold lapses 📅 $(day 7)
EOF

call_day=$(day -1)
call_stamp=$(printf '%s' "$call_day" | tr -d '-')

cat > "triage/${call_stamp} northwind-quoting proposal walkthrough.md" <<EOF
---
title: "northwind-quoting proposal walkthrough"
date: ${call_day}
plaud_id: 7f3c9a1e52b04d6e
source: plaud
duration_min: 34
---

# northwind-quoting proposal walkthrough
_${call_day} 14:00 · 34 min_

## Summary

### Decisions

- Henrik Aalto, northwind-quoting's finance director, holds the budget and signs the order. He read the proposal before the call and joined for the second half.
- Phase one covers the trade-counter product line only; the second line waits for a later phase.

### Action items

- [ ] Studio: send Henrik a one-page summary of the phase one scope and price by $(day 1).
- [ ] Studio: send a revised timeline that starts with the trade-counter line by $(day 4).
- [ ] Pia: send the trade-counter price list export by $(day 2).
- [ ] Henrik: confirm how purchase orders are raised before the next call.

### Next meeting

- Follow-up call with Pia and Henrik on $(day 6) at 10:00 to agree the order.

## Transcript

[00:00] **Pia Vermeer:** Thanks for walking us through it. Most of the team liked the proposal, the open question was which product line goes first.

[04:12] **Me:** We would start with the trade counter. It has the most quotes per week, so it pays back first.

[17:40] **Henrik Aalto:** I read it last night. The budget is mine and I sign the order, so put the phase one scope and the price on one page for me.

[18:05] **Me:** I will have that to you by $(day 1), and a revised timeline by $(day 4).

[18:31] **Henrik Aalto:** Send it straight to me, henrik dot aalto at northwind-quoting dot example.

[22:10] **Pia Vermeer:** I will export the trade-counter price list for you by $(day 2).

[31:55] **Henrik Aalto:** Let us meet again on $(day 6) at ten, and I will have checked how we raise the purchase order by then.
EOF
