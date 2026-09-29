#!/usr/bin/env bash
# A run that stopped after its shortlist, left in triage/ for the <path> argument to
# resume. Three ideas are ranked and one is approved to land, so the other two must stay
# in the session record and get no folder under resources/ideas/.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"

cat > "triage/Brainstorm client admin (partial).md" <<'REC'
# Brainstorm: client admin (partial)

Stopped after Step 6: the shortlist is ranked, nothing has landed yet.

**Kind:** improvement · **Time:** two hours a week · **Budget:** nothing · **No-go:** none

## Problems
1. For me, chasing late client payments is painful because every invoice needs two or three reminder emails, leading to about three hours a month and slow cash. (picked)
2. For me, collecting website content from clients is painful because it arrives in pieces over email, leading to launches slipping by a week. (picked)
3. For me, small text-change requests are painful because each one arrives as its own email, leading to constant interruptions. (picked)

## Ideas
### Late payments
- A fixed reminder schedule, sent by hand from three templates
- Reminders sent automatically by the invoicing tool (agent)
### Website content
- A shared checklist per project that the client fills in
- A content intake form sent at kickoff (agent)
### Text changes
- One batch of text changes a month, agreed with each client
- A short edit-request form (agent)

## Shortlist
1. Payment reminders - pain: removes most of the chasing; worth: about three hours a month and faster cash; four weeks: yes, the invoicing tool has reminders built in
2. Content intake form - pain: content arrives in one place; worth: a week of slip per launch; four weeks: yes
3. Monthly text-change batch - pain: fewer interruptions; worth: an hour or two a month; four weeks: yes, it needs only an email to each client
REC
