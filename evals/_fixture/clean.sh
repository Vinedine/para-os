#!/usr/bin/env bash
# Extra defects for the para-deep-clean cases, sourced after vault.sh (and independent of
# deals.sh: the sales module adds nothing these cases need). Dates in the filenames below
# follow the vault's own YYYYMMDD source convention and are fixed rather than run-relative,
# because they are the literal strings the graders match against the transcript.
set -e

# Deep-clean's own precondition 4 refuses to start while triage/ holds a loose file, and
# vault.sh always plants one note there. Clear it so a deep-clean run can reach Phase 1 at
# all - the other cases that source vault.sh never check that precondition and don't care.
rm -f triage/*.md
touch triage/.gitkeep

mkdir -p areas/business/sources archive/meetings

# One dangling link, and one link whose target has both a space and a parenthesis and does
# exist, so a link checker that stops at the first ")" gets the second one wrong even though
# it is fine. Both spellings are unencoded, as a vault writes them by hand.
cat > areas/business/brief.md <<'EOF'
# business

Running narrative for Fixture Studio's own operations.

## Sources

- [Meeting notes](sources/20260101 Meeting - Notes.md)
- [Vendor quote](sources/20260201 Vendor Quote (Draft).md)
EOF

cat > "areas/business/sources/20260201 Vendor Quote (Draft).md" <<'EOF'
# Vendor Quote (Draft)

A placeholder source so the parenthesised, space-bearing link above resolves.
EOF

# A checkbox where the vault's own Actions rule forbids one: resources/ never carries one.
cat >> resources/ideas/orchard-labs/brief.md <<'EOF'

## Open questions

- [ ] Ask Orchard for their quoting spreadsheet
EOF

# Documentation, not work: a fenced sample checkbox inside an entity whose brief already says
# every item across its action files is closed.
cat >> archive/projects/para-os-2026-09-03/brief.md <<'EOF'

## What an actions file looked like

```
- [ ] Sample task inside a fence
```
EOF

# A third-party call transcript, already carrying the frozen-record marker phase1-structural.md
# asks for, with the two open checkboxes the transcription tool extracted under "Next steps".
# Correct behaviour is to leave both exactly as found.
cat > "archive/meetings/20260105 Orchard call - Transcript.md" <<'EOF'
Third-party verbatim record, kept as generated; its checkboxes are the call tool's own
extracted next steps and are never ticked.

# Orchard call - Transcript

## Next steps

- [ ] Send the deck to Orchard
- [ ] Confirm the installer's day rate with Orchard
EOF
