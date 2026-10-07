# Voice profile (shared across skills)

How a vault keeps the way one person writes, so a draft in their name reads as theirs. [drafting.md](drafting.md) reads the profile before a draft; this file is followed when someone asks to build, rebuild or correct their own. A vault has none until someone asks.

## Where it lives

- **One per person who sends from the vault**: `.claude/rules/voice-<firstname-lastname>.md`, named like their contact card. A draft uses the profile of the account it goes out from, matched on the profile's `**Accounts:**` line, never the profile of whoever asked for the draft. No match: draft without one.
- **It loads only when read.** Its frontmatter scopes it to its own path, so a turn that drafts nothing never pays for it:

  ```yaml
  ---
  paths:
    - ".claude/rules/voice-<firstname-lastname>.md"
  ---
  ```

- **`CLAUDE.md` points at it** in a paragraph of its own under `## Memory`, one per profile: "Drafts from <Name>'s account are written in their voice. The full convention (<Name>'s voice) is in [.claude/rules/voice-<firstname-lastname>.md](.claude/rules/voice-<firstname-lastname>.md), which loads only when read; read it explicitly before drafting anything in <Name>'s name."

## What it holds

A `# <Name>'s voice` title, the `**Accounts:**` line, a paragraph saying it is built and changed per `para-shared/voice-profile.md` with <Name>'s approval and from how many samples over which dates, then:

1. **`## Fixed traits`**, per language where they differ: the greeting, the sign-off, sentence length, contractions, where the ask lands, what they call their own service or company.
2. **`## Tone by recipient`**, one line per case the vault can already tell apart: a contact card's `**Kind:**`, the stage of the entity the thread is about, the thread's language. Only cases the samples show.
3. **`## Never uses`**: phrases a generic draft reaches for that no sample contains.
4. **`## Sample`**: one mail verbatim in a fence, every other person's name, address and figure replaced by a bracketed role.

**Every line ends in its evidence**: `_inferred (n/N samples)_` or `_operator (YYYY-MM-DD, "the correction, quoted")_`. An inferred trait needs at least three samples showing it, and a never-uses entry is absent from all N (`0/N`). Where the samples split, it is no trait: leave it out, or make it a tone row when the split follows the recipient.

Out of scope: company positioning (the root `README.md` holds it), scores, strictness settings.

## Building it

Only on its person's ask, which is the approval to write the profile and its pointer.

1. **Samples**: the sending account's sent mail over the last 12 months, read per [connectors.md](connectors.md), or mails the person hands over. With neither, ask for three mails they were happy with, and stop. Never build from fewer than three, or from what the vault says about them.
2. **Keep only their words.** Cut each mail at its quoted history (an `On ... wrote:` line, an `Original Message` or `From:`/`Sent:` header block, `>` lines) and drop forwarded content, the auto-signature (the block that repeats at the foot of most mails, often after a `-- ` line) and legal footers. The sign-off is the closing they typed above the signature, never a closing or name block inside it; a correspondent's phrasing in a quoted reply is never a trait. A mail that is mostly someone else's text is not a sample.
3. **Count, then write.** Number the samples, group them by language, and give each trait its count.
4. **Report** the file and the pointer written, N and the dates the samples span, and each trait left out for want of three samples.

**A rebuild replaces inferred lines only.** An `operator` line stays as written, and an inferred line contradicting it is dropped.

## Corrections

A correction to a draft that states a standing trait ("I never write Dear", "I sign off with my first name") is proposed as a profile line the first time it is made, quoting it, and added only on a yes: the second-correction rule in `working-preferences.md` does not apply here. A change for one mail ("formal, this is for the notary") is not proposed. A line contradicting an existing one replaces it once the person confirms which holds, and a profile line contradicting a working preference is put to them with both quoted, never settled silently.
