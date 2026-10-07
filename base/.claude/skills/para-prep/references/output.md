# Render the prep (Step 4)

One prep per meeting, in time order, separated by `---`. A person in two meetings is prepped in both. Sections with nothing to show are left out; the **Objective** line never is.

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

One line per attendee, from the scan's `status`: a matched card gives its `**Kind:**` where the vault uses one, and its role or first header line; `no_card` is flagged with `/para-new` offered, never more; `ambiguous` was asked about in Step 3 and renders the card the operator named. The operator is left out.

## The objective

**A staged entity**, one whose scan `stage` is not null: the stage's exit criterion column as the lifecycle table writes it, attributed to its entity, closed by the invitation to sharpen it. Where a lifecycle table carries no exit criterion column, or the stage is terminal, it is the question below.

**A meeting touching no staged entity**: `**Objective:** not in the vault - what should be true after this meeting that is not true now?` Never a proposed answer. Several staged entities each get their criterion, on one line each.

## Where things stand

One line per entity the scan ties to an attendee, staged ones first. A staged entity reads its stage, days in stage (`?d` where `days_in_stage` is null), the `Last touch` and `Signer` header fields where its header carries them, and a dated fact still ahead (`prices hold to <date>, in <N>d`). Any other entity reads its open count and next item. A register row naming an attendee renders the same way, its register as the link.

## Open items both ways

**On the card**: every open item from the scan's `card.items`. **Elsewhere**: every `mention`, grouped by the person it names, a `short name` match marked `(matched on one name)`. The same item in both renders in both, never merged. Line rules are `/para-daily-brief`'s ([its output.md](../../para-daily-brief/references/output.md)): one line each, cut not wrapped, link text `<scope>:<line>` and a percent-encoded target.

## Last time

The newest record across the meeting's attendees, read in full. An `unfiled` triage item counts, dated by what it says, and its heading says it is not filed yet. Give its decisions and what it left open, two to four lines, each traceable to the record. **Promised to bring** is what the operator owes at this meeting, from that record's commitments still open and the open items above that deliver something to an attendee (a draft, a decision, a document), each with its source. A commitment the vault shows as done is not repeated.

Where no record names any attendee, the section is left out and **Not in the vault** asks for it.

## Do not raise

Every item of every `do_not_raise` list the meeting's entities carry, verbatim, with its brief linked. Never reworded into something to say.

## Not in the vault

Questions, one line each, from what the scan found missing, in this order:

1. An attendee with no card: who they are and what they are to this vault.
2. Header fields reading `unknown` (`Signer: unknown` becomes "Who signs?"), and a staged entity with no `since`.
3. No record of a last meeting with these people: "When did you last meet, and what was agreed?"

## When the vault knows little

When no attendee matches a card, or the matched cards tie to no entity and nothing names them, the prep is **Who**, the objective question and one line: `The vault holds nothing more on <names>.` No talking points, no background from general knowledge, no guess at what the meeting is about beyond its title.
