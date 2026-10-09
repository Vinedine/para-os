# Voice profile (shared across skills)

How a vault keeps the way one person writes, so a draft in their name reads as theirs. [drafting.md](drafting.md) reads it before a draft; this file governs building, rebuilding and correcting one, only ever on that person's ask.

## Where it lives

One per person who sends from the vault, `.claude/rules/voice-<firstname-lastname>.md`, named like their contact card, with frontmatter scoping it to its own path so it loads only when read:

```yaml
---
paths:
  - ".claude/rules/voice-<firstname-lastname>.md"
---
```

A draft uses the profile whose `**Accounts:**` line names the account it goes out from, never the profile of whoever asked; no match, no profile. `CLAUDE.md` points at each in its own paragraph under `## Memory`: "Drafts from <Name>'s account are written in their voice. The full convention (<Name>'s voice) is in [.claude/rules/voice-<firstname-lastname>.md](.claude/rules/voice-<firstname-lastname>.md), which loads only when read; read it explicitly before drafting anything in <Name>'s name."

## What it holds

A `# <Name>'s voice` title, the `**Accounts:**` line, one line saying it is built per `para-shared/voice-profile.md` with <Name>'s approval from N samples over which dates, then `## Fixed traits` per language where they differ (greeting, sign-off, sentence length, contractions, where the ask lands, what they call their own company), `## Tone by recipient` (one line per case the vault can tell apart: a card's `**Kind:**`, the entity's stage, the thread's language), `## Never uses` (phrases a generic draft reaches for that no sample contains) and `## Sample` (one mail verbatim in a fence, every other person's name, address and figure replaced by a bracketed role). Every line ends in its evidence, `_inferred (n/N samples)_` or `_operator (YYYY-MM-DD, "the correction, quoted")_`: an inferred trait needs three samples showing it, a never-uses entry is absent from all N, and a split is no trait. Positioning, scores and strictness settings are out of scope.

## Building it

1. **Samples**: the sending account's sent mail over the last 12 months per [connectors.md](connectors.md), or mails the person hands over; with neither, ask for three they were happy with and stop. Fewer than three, or what the vault says about them, builds nothing.
2. **Keep only their words**: cut each mail at its quoted history and drop forwarded content, the auto-signature and legal footers. The sign-off is the closing they typed above the signature, never a name block inside it; a correspondent's phrasing in a quote is never a trait, and a mail that is mostly someone else's text is not a sample.
3. **Count, then write**, each trait with its count per language, and report the file, the pointer, N and the dates, and each trait left out for want of three samples.

A rebuild replaces inferred lines only; an `operator` line stays, and an inferred line contradicting it is dropped.

## Corrections

A correction stating a standing trait ("I never write Dear") is proposed as a profile line the first time, quoting it, and added on a yes; a one-off ("formal, this is for the notary") is not. A line contradicting an existing one replaces it once the person confirms which holds; one contradicting a working preference is put to them with both quoted.
