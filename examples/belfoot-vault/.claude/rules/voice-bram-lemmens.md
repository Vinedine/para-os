---
paths:
  - ".claude/rules/voice-bram-lemmens.md"
---

# Bram Lemmens's voice

**Accounts:** bram@lemmens-advisory.example

How Bram writes, for any draft that goes out from the account above. Built and changed per `para-shared/voice-profile.md`, installed beside the `/para-*` skills, and only with Bram's approval. Built from 23 sent mails, 2025-06-30 to 2026-06-19: 15 in English, 8 in Dutch.

## Fixed traits

- **Greeting, English:** "Hi <first name>," _inferred (13/15 samples)_
- **Greeting, Dutch:** "Hoi <first name>," _inferred (7/8 samples)_
- **Sign-off, English:** "Thanks, Bram" when the mail asks for something, "Best, Bram" otherwise. _inferred (14/15 samples)_
- **Sign-off, Dutch:** "Groeten, Bram" _operator (2026-05-19, "Groetjes is for friends; to the club it is Groeten")_
- **Sentence length:** short, rarely past 20 words; one point per paragraph, three paragraphs at most. _inferred (19/23 samples)_
- **Contractions:** yes in English: "I'll", "we're", "don't". _inferred (12/15 samples)_
- **Where the ask lands:** the first paragraph, as a question carrying its date; context after it. _inferred (17/23 samples)_
- **His own service:** "the programme", never the name of his firm; "I" for his own work, "the club" for BelFoot. _inferred (20/23 samples)_

## Tone by recipient

- **A club stakeholder** (a card in `areas/network/`): first names, `je` and never `u` in Dutch, the decision needed in the opening line, a technical term only with a one-clause gloss. _inferred (8/8 samples)_
- **A vendor at Invited or Responded** (`areas/stadium/vendors.md`): neutral and exact, the question that decides its next stage first and any others numbered below it, nothing about another vendor's position. _inferred (5/5 samples)_
- **A vendor at Contracted**: first names and direct, the SOW clause cited by number when it settles the point. _inferred (3/3 samples)_

## Never uses

- "I hope this email finds you well" _inferred (0/23 samples)_
- "Please do not hesitate to contact me" _inferred (0/23 samples)_
- "Kind regards", "Met vriendelijke groeten" _inferred (0/23 samples)_
- "Circling back" _inferred (0/23 samples)_
- An exclamation mark in anything to a vendor _operator (2026-04-02, "no exclamation marks to vendors, ever")_

## Sample

```text
Hi [vendor contact],

Can you confirm by Friday 26 June whether the Salesforce connector is supported by you or by a partner? It decides whether your response goes forward.

Two smaller points, no rush:
1. Which Pro League clubs can I call as references?
2. Does the price in section 4 include the reader firmware?

Thanks,
Bram
```
