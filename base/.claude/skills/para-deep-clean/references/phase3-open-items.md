# Phase 3 - Open items, action grooming, content grooming

`scripts/clean_scan.py --phase 3` implements the over-threshold, other-checkbox-file, stale-undated, aspirational-date and prose-next-steps checks below, plus the size-based half of Step 3.5's brief selection as `briefs_to_read`, and `scripts/test_clean_scan.py` pins each one to a case. Content grooming's remaining judgment (Step 3.5) and reading source documents (Step 3.1) are calls the script does not attempt.

Goal: every "Open items" section reflects real outstanding work, every action file sits at the actionable frontier, and prose has stopped accumulating for its own sake.

**Precondition:** verify pypdf is installed - `py -c "import pypdf"`. If the import fails, either `pip install pypdf` or skip Step 3.1's document reading.

## Step 3.1 - Read source documents to close items

**Skip the document reading where the vault has no such documents**, and say so rather than reporting it as done; the mail search at the end of this step still runs. An item worth reading a document for names a *value* it does not have, not a judgment nobody has made. The examples below are a property vault's.

Many "missing data" items are answerable from documents already on file:

```bash
py -X utf8 -c "from pypdf import PdfReader; r = PdfReader(r'<path>'); print(r.pages[0].extract_text())"
```

Common items closable this way: "Purchase price not on file" (read the purchase contract), "Fees not itemised" (the settlement statement or invoice), "Date X unknown" (PDF metadata or first page). Update the README with the closed facts and remove the item from Open items.

**An item waiting on a third party** (a payment confirmation, a notary's or bank's reply) is settled by mail more often than by a document. Where the vault's `## Triage sources` declares mailboxes, search them read-only for each such item, per [para-shared/connectors.md](../../para-shared/connectors.md), and cite the message that closes it.

## Step 3.2 - Archived entities: aggressive close

For sold, closed or archived entities, historical record-keeping gaps don't affect current operations. Soften Open items to `_None - <entity> fully closed; minor historical gaps acknowledged but not material._` or empty them entirely.

For active entities: keep open items that represent real work to do; only remove ones that are actually resolved.

## Step 3.3 - Surface time-sensitive items

Anything dated inside the next 30 days, plus anything already overdue. What those are is the vault's own domain: a property vault's are payments, indexation anniversaries, insurance renewals and inspection deadlines (boiler, electrical, asbestos); another vault's are renewals, filing dates and booked calls. Report them as a dated list.

**Reorder the file only where the vault declares an order.** The instruction to move these to the top of Open items assumes a file whose order carries meaning. Where `CLAUDE.md` prescribes none, moving them churns the file to duplicate what `/para-daily-brief` already does from the markers - so list them in the phase summary and leave the file alone.

## Step 3.4 - Action grooming

The repair half of the actionable-frontier rule in `CLAUDE.md` (`/para-daily-brief` flags these same conditions but never fixes them). For every `actions.md` under `projects/` and `areas/`, every contact file's `## Next actions`, **and every other file in `projects/` or `areas/` that carries open checkboxes**:

**That last group nothing else counts or grooms:** `/para-daily-brief` globs `**/actions.md`, yet the vault's "Where a checkbox may live" rule lets a log, a plan or a review file in `projects/` and `areas/` hold dozens. Such a file is **not** a filing error where it declares its own contract (its entries *propose* actions, say, and something prunes them). Read the file's own header before judging it: where it declares the shape, report the count and check that something retires what is never promoted; where it does not, the items belong in that entity's `actions.md` and the move is the proposal.

- **Over-threshold files** - 12 or more open items, the count the template's own rule bites at. Propose restoring the frontier: keep as checkboxes only the steps actionable now or on their marked date; demote everything gated on an unfinished predecessor to plain bullets under a `## Backlog` heading in the same file, **text preserved verbatim** - only the `- [ ]` syntax and any date or priority markers change. A demoted item promotes back to a checkbox when its gate opens.

  **A file can exceed the count with nothing demotable, and that is a legitimate state.** Where every open item really is actionable now, there is nothing to demote. Say so, propose any *closes* the evidence supports, and report the file as deliberately over rather than as unfixed.
- **Stale undated items** - open, undated, and untouched for 60+ days. Ask per item, never in bulk: close it (done untracked, or dead), date it (a real deadline exists), or demote it to backlog prose.

  **Measure staleness on the item's own line, not on the file**, since a template sweep resets every file's age at once. Use `git blame -L <line>,<line> --porcelain -w -- <file>` for the last commit that changed the item itself, where the vault has git and the file is tracked. Where blame's commit hash is all zero, the line is edited but not yet committed: report it as `measured_by: "uncommitted"`, an item that is unmeasurable rather than a fabricated date. **An untracked file is not stale**, only uncommitted; fall back to its mtime. Where neither measure works for a given item, say so **for that item**, never for the whole file or the whole run.
- **Aspirational dates** - items overdue by more than 30 days. A real deadline blown by a month was usually never a real date (`📅` records a real-world deadline, never an aspiration). Offer stripping the `📅` and leaving the item undated or demoted, against keeping it because the deadline was real and genuinely missed.

**Both open on a question of fact, which carries no `(Recommended)`.** Whether a dormant item was quietly finished or abandoned, and whether a blown date was ever real, are things only the operator knows: the file looks identical either way, and the age that surfaced the item says nothing about which happened. Per the recommendation carve-out in [para-shared/asking.md](../../para-shared/asking.md), ask the fact first with no option labelled, ordered by what the file's own evidence suggests, and say in each description what that answer does to the item; the disposition that follows (close, date or demote; strip or keep) is the skill's to propose and takes a recommendation as usual.

**Anything that closes or removes is one question per item**, per [para-shared/asking.md](../../para-shared/asking.md): a close and a stripped `📅` both lose the text that said what the item was. **Demotions stay batchable** and go on the issues table - a demotion preserves every word and only changes `- [ ]` to `- `.

**This is the skill where the 20-item gate earns its place**: a vault that has never been groomed can produce dozens of closes across a dozen files. Order the questions by file, so consecutive questions concern the same `actions.md` and the operator judges a file's frontier rather than a shuffled list.

**A vault with no `actions.md` keeps its next steps as prose** under headings its `CLAUDE.md` names, or, where it names none, as the brief's own next-steps or open-items sections, which the read-only iPad delivery always has. Run the same tests over each bullet under those headings: over-threshold per file, stale undated, blown dates, and duplicates across files, where demoting means moving the bullet out of the heading into the body, text verbatim. Add one disposition checkboxes never need, **Not an action**: analysis or status parked under a next-steps heading, moved into the body the same way. A list generated from those headings is fixed at its sources (Phase 1).

Grooming never touches `resources/` or `archive/` - checkboxes there are Phase 1 filing errors, not grooming candidates.

## Step 3.5 - Content grooming

The prose half of the same problem, against the content-frontier rule in `CLAUDE.md`. Files only ever grow, and an over-grown brief looks thorough rather than bloated, so nothing surfaces it on its own. Read the root `README.md`, every contact card and area README, plus the `brief.md` of every entity flagged by the size or growth signals below. The small files are in the set unconditionally: a fact copied out of the root README goes stale on a contact card, whose size trips no growth signal ever. Report findings in five kinds:

- **Duplicated facts.** The same fact stated in more than one live file. Identify which file *owns* it (the rule that governs it, the brief of the entity it describes, the contact card of the person it concerns) and propose replacing the copies with links. **Never propose deleting a file as a duplicate without diffing it against the copy that survives** - matching names, sizes or opening lines are not proof, and the two often differ in exactly the sentence that mattered.
- **Superseded content in live buckets.** A reversed decision, a replaced plan, a section describing how something used to work. Propose moving it to the owning `archive/` entity, or cutting it where git already holds the text. Say which, per item - "git has it" is only true for a vault that is actually a git repo, so check before relying on it.
- **Activity-log entries.** Development-log entries that record that work happened rather than what was decided. Propose collapsing a run of them into one entry naming the decision they led to, the surviving entry's text drawn verbatim from the originals rather than re-summarised.
- **Contradictions.** Two live files stating the same fact with different values - a stake, a date, an amount, a status. This is the duplication map above with the values compared, so build it once and read it twice. Never resolve one by trusting the more recently edited file: name the file that *owns* the fact, check it against a source document where one exists, and propose the correction in the copies. A contradiction no source can settle is an open item for the owning entity, not an edit.
- **Orphans.** Files in `projects/`, `areas/` or `resources/` that nothing links to and no `CLAUDE.md` rule accounts for. **Report only.** An orphan is a question for the operator ("is this still live?"), never a deletion candidate: the commonest orphan is a file whose inbound link was lost in an earlier move, and the fix is to restore the link, not to remove the file.

Which entities to read, so this does not become a full-vault re-read every run: a `brief.md` past ~500 lines, or one that has grown by more than half since the last deep clean if the vault's git history can tell you, or any entity whose brief has more development-log entries than it has open actions. `clean_scan.py --phase 3` computes the line-cap part of this mechanically as `briefs_to_read`; the growth-since-last-clean and development-log comparisons stay a judgment call on top of that list. State the thresholds you used in the run summary, and name what you did **not** read, so a light pass is never mistaken for a full one.

**Out of scope entirely for Step 3.5:** `triage/` (unprocessed by definition), any `sources/` folder (source documents are evidence, and a brief that contradicts its own source is Phase 2's problem, not a pruning candidate), and `archive/` (already history - archived briefs are never restructured).

## Edge case

- **Source PDF is scan-only with no text layer**: note the limitation and ask the user to open the PDF directly and report the key value.
