# Phase 3 - Open items, action grooming, content grooming

`scripts/clean_scan.py --phase 3` implements the over-threshold, other-checkbox-file, stale-undated, aspirational-date, demotion and prose-next-steps checks below, plus the size-based half of Step 3.5's brief selection as `briefs_to_read`. Content grooming's remaining judgment (Step 3.5) and reading source documents (Step 3.1) are calls the script does not attempt.

Goal: every "Open items" section reflects real outstanding work, every action file sits at the actionable frontier, and prose has stopped accumulating for its own sake.

**Precondition:** verify pypdf is installed - `python3 -c "import pypdf"` (Windows: `py -3`). If the import fails, ask whether to install it or skip Step 3.1's document reading; never install it unasked.

## Step 3.1 - Read source documents to close items

**Skip the document reading where the vault has no such documents**, and say so rather than reporting it as done; the mail search at the end of this step still runs. An item worth reading a document for names a *value* it does not have, not a judgment nobody has made. The examples below are a property vault's.

Many "missing data" items are answerable from documents already on file:

```bash
# Windows: py -3
python3 -X utf8 -c "from pypdf import PdfReader; r = PdfReader(r'<path>'); print(r.pages[0].extract_text())"
```

Common items closable this way: "Purchase price not on file" (read the purchase contract), "Fees not itemised" (the settlement statement or invoice), "Date X unknown" (PDF metadata or first page). Update the README with the closed facts and remove the item from Open items.

**An item waiting on a third party** (a payment confirmation, a notary's or bank's reply) is settled by mail more often than by a document. Where the vault's `## Triage sources` declares mailboxes, search them read-only for each such item, per [para-shared/connectors.md](../../para-shared/connectors.md), and cite the message that closes it.

## Step 3.2 - Archived entities: aggressive close

For sold, closed or archived entities, soften Open items to `_None - <entity> fully closed; minor historical gaps acknowledged but not material._` or empty them entirely.

For active entities: keep open items that represent real work to do; only remove ones that are actually resolved.

## Step 3.3 - Surface time-sensitive items

Anything dated inside the next 30 days, a last day to give notice inside the next 90, plus anything already overdue. What those are is the vault's own domain: payments, renewals, inspection or filing deadlines, booked calls. Report them as a dated list.

**Every live contract, lease or policy with a renewal term** filed in a `sources/` folder under `projects/` or `areas/` has its next notice date as a `📅` in a live file, [dated so](../../para-shared/operating-discipline.md#dating-a-renewing-agreement). Read each one's term and notice clause; where no line carries that date, propose one for the owning entity's `actions.md` on the issues table, linking the document. One that has ended or been replaced needs none.

**Reorder the file only where the vault declares an order**, moving these to the top of Open items. Where `CLAUDE.md` prescribes none, list them in the phase summary and leave the file alone.

## Step 3.4 - Action grooming

The repair half of the actionable-frontier rule in `CLAUDE.md`. For every `actions.md` under `projects/` and `areas/`, every contact file's `## Next actions`, **and every other file in `projects/` or `areas/` that carries open checkboxes**:

**That last group nothing else counts or grooms:** the vault's "Where a checkbox may live" rule lets a log, a plan or a review file in `projects/` and `areas/` hold dozens. Such a file is **not** a filing error where it declares its own contract (its entries *propose* actions, say, and something prunes them). Read the file's own header before judging it: where it declares the shape, report the count and check that something retires what is never promoted; where it does not, the items belong in that entity's `actions.md` and the move is the proposal.

- **Over-threshold files** - 12 or more open items. Propose restoring the frontier: keep as checkboxes only the steps actionable now or on their marked date; demote everything gated on an unfinished predecessor to plain bullets under a `## Backlog` heading in the same file, **text preserved verbatim** - only the `- [ ]` syntax and any date or priority markers change. A demoted item promotes back to a checkbox when its gate opens.

  **A file can exceed the count with nothing demotable, and that is a legitimate state.** Say so, propose any *closes* the evidence supports, and report the file as deliberately over rather than as unfixed.
- **Stale undated items** - open, undated, and untouched for 60+ days. Ask per item, never in bulk: close it (done untracked, or dead), date it (a real deadline exists), or demote it to backlog prose.

  **Measure staleness on the item's own line, not on the file**. Use `git blame -L <line>,<line> --porcelain -w -- <file>` for the last commit that changed the item itself, where the vault has git and the file is tracked. Where blame's commit hash is all zero, the line is edited but not yet committed: report it as `measured_by: "uncommitted"`, never a fabricated date. **An untracked file is not stale**, only uncommitted; fall back to its mtime. Where neither measure works for a given item, say so **for that item**, never for the whole file or the whole run.
- **Aspirational dates** - items overdue by more than 30 days. Offer stripping the `📅` and leaving the item undated or demoted, against keeping it because the deadline was real and genuinely missed.
- **Recently overdue** - items overdue by 30 days or less: done, re-dated, or left.
- **Projects that lost their deadline** - the scan's `demotion_candidates`: a project whose newest dated action, open or ticked, is six months or more old, and that sits in no declared lifecycle. Propose its demotion to an area in the phase summary, one line per project naming the date; the operator decides, and this pass never performs the move.

**All three open on a question of fact, which carries no `(Recommended)`.** Whether a dormant item was quietly finished or abandoned, and whether a blown date was ever real, are things only the operator knows. Per the recommendation carve-out in [para-shared/asking.md](../../para-shared/asking.md), ask the fact first with no option labelled, ordered by what the file's own evidence suggests, and say in each description what that answer does to the item; the disposition that follows (close, date or demote; strip or keep; close, re-date or leave) is the skill's to propose and takes a recommendation as usual. Where each answer maps to exactly one disposition, fold the two into one question per item, each option naming the fact and its effect ("Finished untracked: close it"), still with no `(Recommended)`.

**Anything that closes or removes is one question per item**, per [para-shared/asking.md](../../para-shared/asking.md). **Demotions stay batchable** and go on the issues table. **Order the questions by file**, so consecutive questions concern the same `actions.md`.

**A vault with no `actions.md` keeps its next steps as prose** under headings its `CLAUDE.md` names, or, where it names none, as the brief's own next-steps or open-items sections. Run the same tests over each bullet under those headings: over-threshold per file, stale undated, blown dates, and duplicates across files, where demoting means moving the bullet out of the heading into the body, text verbatim. Add one disposition checkboxes never need, **Not an action**: analysis or status parked under a next-steps heading, moved into the body the same way. A list generated from those headings is fixed at its sources (Phase 1).

Grooming never touches `resources/` or `archive/` - checkboxes there are Phase 1 filing errors, not grooming candidates.

## Step 3.5 - Content grooming

The prose half of the same problem, against the content-frontier rule in `CLAUDE.md`. Read the root `README.md`, every contact card and area README, plus the `brief.md` of every entity flagged by the size or growth signals below. The small files are in the set unconditionally. Report findings in five kinds:

- **Duplicated facts.** The same fact stated in more than one live file. Identify which file *owns* it (the rule that governs it, the brief of the entity it describes, the contact card of the person it concerns) and propose replacing the copies with links. **Never propose deleting a file as a duplicate without diffing it against the copy that survives**.
- **Superseded content in live buckets.** A reversed decision, a replaced plan, a section describing how something used to work. Propose moving it to the owning `archive/` entity, or cutting it where git already holds the text. Say which, per item: "git has it" holds only in a git repo.
- **Activity-log entries.** Development-log entries that record that work happened rather than what was decided. Propose collapsing a run of them into one entry naming the decision they led to, the surviving entry's text drawn verbatim from the originals rather than re-summarised.
- **Contradictions.** Two live files stating the same fact with different values - a stake, a date, an amount, a status. Never resolve one by trusting the more recently edited file: name the file that *owns* the fact, check it against a source document where one exists, and propose the correction in the copies. A contradiction no source can settle is an open item for the owning entity, not an edit.
- **Orphans.** Files in `projects/`, `areas/` or `resources/` that nothing links to (links percent-decoded, as in Step 1.2) and no `CLAUDE.md` rule accounts for. **Report only.** An orphan is a question for the operator ("is this still live?"), never a deletion candidate; where an earlier move lost its inbound link, propose restoring it.

Which entities to read: a `brief.md` past ~500 lines, or one that has grown by more than half since the last deep clean if the vault's git history can tell you, or any entity whose brief has more development-log entries than it has open actions. The scan's `briefs_to_read` covers the line cap; the growth and development-log comparisons are judgment on top. State the thresholds you used in the run summary, and name what you did **not** read. Too large for one conversation: split the read across read-only subagents by bucket, and re-verify each delegated finding before asking.

**Out of scope entirely for Step 3.5:** `triage/` (unprocessed by definition), any `sources/` folder (a brief is checked against its sources in Step 3.1), and `archive/`.

## Edge case

- **Source PDF is scan-only with no text layer**: note the limitation and ask the user to open the PDF directly and report the key value.
