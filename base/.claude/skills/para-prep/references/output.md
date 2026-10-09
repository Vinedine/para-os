# Render the prep (Step 4)

One prep per meeting, in time order, separated by `---`; a person in two meetings is prepped in both. A section with nothing to show is left out; the **Objective** line never is.

````
# Prep - <meeting title, or the person> - <YYYY-MM-DD> <HH:MM>

**When and where:** <time, place or call link, from the event> · <calendar, or meetings.md>
**Who:**
- <Name> - <Kind>, <role or one line from the card> - [card](<path>)
- <Name> - 🚩 no card in this vault: `/para-new` adds one

**Objective:** <Entity>: <the stage's exit criterion, as the table writes it> - sharpen it to what must be true when the meeting ends.

## Where things stand
- <Entity> · <Stage> <N>d in stage · Last touch <date, what> · Signer <name or unknown> - [brief](<path>)
- <Entity> · <N> open · next: <item> 📅 <date> - [actions](<path>)

## Open items
**On <Name>'s card**
- <item> · 📅 <date> (<N>d ago) - [<name>:<line>](<path>#L<line>)
**Naming <Name> elsewhere**
- <item> · 📅 <date> (in <N>d) - [<scope>:<line>](<path>#L<line>)

## Last time - <record title>, <date> (<N>d ago)
- <a decision, or what was left open> - [record](<path>)
**Promised to bring:** <what we owe at this meeting> - [<source>](<path>)

## Do not raise
- <item> - [<entity>](<path>)

## Not in the vault
- <a question to ask, or for the operator to answer>

**After the meeting:** file the record in <the owning entity's `sources/`>, update `Last touch` where the entity carries one, and add the next step to <the card or the entity's `actions.md`>.
````

## Who

By `status`: `no_card` is flagged with `/para-new` offered, nothing more; `ambiguous` renders the card the operator named in Step 3.

## The objective

One line per staged entity (scan `stage` not null), its stage's exit criterion as the lifecycle table writes it. No staged entity, a terminal stage or no exit criterion column gets the question, never a proposed answer: `**Objective:** not in the vault - what should be true after this meeting that is not true now?`

## Where things stand

Staged entities first: `?d` where `days_in_stage` is null, `Last touch` and `Signer` where the header carries them, and a dated fact still ahead (`prices hold to <date>, in <N>d`). A register row naming an attendee renders the same way, its register the link.

## Open items both ways

**On the card**: every item in `card.items`. **Elsewhere**: every `mention`, grouped by the person it names, a `short name` match marked `(matched on one name)`. An item in both places renders in both. Line rules are [`/para-daily-brief`'s](../../para-daily-brief/references/output.md): one line each, cut not wrapped, link text `<scope>:<line>` and a percent-encoded target.

## Last time

The newest record across the attendees, read in full; an `unfiled` triage item counts, dated by what it says, its heading saying it is not filed yet. Two to four lines of its decisions and what it left open. **Promised to bring**: its commitments still open, and the open items above that deliver something to an attendee, each with its source; nothing the vault shows as done. No record names any attendee: leave the section out.

## Not in the vault

One question per line, in this order: an attendee with no card (who they are to this vault); each header field reading `unknown` (`Signer: unknown` becomes "Who signs?") and a staged entity with no `since`; no record of a last meeting ("When did you last meet, and what was agreed?").

## When the vault knows little

No attendee matches a card, or the cards tie to nothing and nothing names them: the prep is **Who**, the objective question and `The vault holds nothing more on <names>.` Nothing from general knowledge, and no guess at the meeting beyond its title.
