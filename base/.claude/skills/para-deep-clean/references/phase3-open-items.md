# Phase 3 - Open items, action grooming, content grooming

Goal: every "Open items" section reflects real outstanding work, every action file sits at the actionable frontier, and prose has stopped accumulating for its own sake.

**Precondition:** verify pypdf is installed - `py -c "import pypdf"`. If the import fails, either `pip install pypdf` or skip Step 3.1 and go straight to Steps 3.2 onward, which don't need it.

## Step 3.1 - Read source PDFs to close items

Many "missing data" items are answerable from documents already on file:

```bash
py -X utf8 -c "from pypdf import PdfReader; r = PdfReader(r'<path>'); print(r.pages[0].extract_text())"
```

Common items closable this way: "Purchase price not on file" (read the purchase contract), "Fees not itemised" (the settlement statement or invoice), "Date X unknown" (PDF metadata or first page). Update the README with the closed facts and remove the item from Open items.

## Step 3.2 - Archived entities: aggressive close

For sold, closed or archived entities, historical record-keeping gaps don't affect current operations. Soften Open items to `_None - <entity> fully closed; minor historical gaps acknowledged but not material._` or empty them entirely.

For active entities: keep open items that represent real work to do; only remove ones that are actually resolved.

## Step 3.3 - Surface time-sensitive items

Payments due in the next 30 days, indexation anniversaries, insurance renewals, inspection deadlines (boiler, electrical, asbestos). Move these to the top of the Open items list with clear deadline labels.

## Step 3.4 - Action grooming

The repair half of the actionable-frontier rule in `CLAUDE.md` (`/para-daily-brief` flags these same conditions but never fixes them). For every `actions.md` under `projects/` and `areas/`, and every contact file's `## Next actions`:

- **Over-threshold files** - more than 12 open items. Propose restoring the frontier: keep as checkboxes only the steps actionable now or on their marked date; demote everything gated on an unfinished predecessor to plain bullets under a `## Backlog` heading in the same file, **text preserved verbatim** - only the `- [ ]` syntax and any date or priority markers change. A demoted item promotes back to a checkbox when its gate opens.
- **Stale undated items** - open, undated, in a file untouched for 60+ days. Propose per item, never in bulk: close it (done untracked, or dead - say which), date it (a real deadline exists), or demote it to backlog prose.
- **Aspirational dates** - items overdue by more than 30 days. A real deadline blown by a month was usually never a real date (`📅` records a real-world deadline, never an aspiration). Propose stripping the `📅` and leaving the item undated or demoted, unless the operator confirms the deadline was real and genuinely missed.

All grooming goes through the standard issues table with per-item approval for anything that closes or removes; demotions are batchable since they lose no text. Grooming never touches `resources/` or `archive/` - checkboxes there are Phase 1 filing errors, not grooming candidates.

## Step 3.5 - Content grooming

The prose half of the same problem, against the content-frontier rule in `CLAUDE.md`. Files only ever grow, and an over-grown brief looks thorough rather than bloated, so nothing surfaces it on its own. Read the `brief.md` of every entity flagged by the size or growth signals below, plus the root `README.md`. Report findings in four kinds:

- **Duplicated facts.** The same fact stated in more than one live file. Identify which file *owns* it (the rule that governs it, the brief of the entity it describes, the contact card of the person it concerns) and propose replacing the copies with links. **Never propose deleting a file as a duplicate without diffing it against the copy that survives** - matching names, sizes or opening lines are not proof, and the two often differ in exactly the sentence that mattered.
- **Superseded content in live buckets.** A reversed decision, a replaced plan, a section describing how something used to work. Propose moving it to the owning `archive/` entity, or cutting it where git already holds the text. Say which, per item - "git has it" is only true for a vault that is actually a git repo, so check before relying on it.
- **Activity-log entries.** Development-log entries that record that work happened rather than what was decided. Propose collapsing a run of them into one entry naming the decision they led to, the surviving entry's text drawn verbatim from the originals rather than re-summarised.
- **Orphans.** Files in `projects/`, `areas/` or `resources/` that nothing links to and no `CLAUDE.md` rule accounts for. **Report only.** An orphan is a question for the operator ("is this still live?"), never a deletion candidate: the commonest orphan is a file whose inbound link was lost in an earlier move, and the fix is to restore the link, not to remove the file.

Which entities to read, so this does not become a full-vault re-read every run: a `brief.md` past ~500 lines, or one that has grown by more than half since the last deep clean if the vault's git history can tell you, or any entity whose brief has more development-log entries than it has open actions. State the thresholds you used in the run summary, and name what you did **not** read, so a light pass is never mistaken for a full one.

**Approval is per item, and deletion is never batched.** Moves and link-replacements can be approved as a group since they lose no text. Anything that removes text goes one at a time, with the text shown. Three things are out of scope entirely: `triage/` (unprocessed by definition), any `sources/` folder (source documents are evidence, and a brief that contradicts its own source is Phase 2's problem, not a pruning candidate), and `archive/` (already history - archived briefs are never restructured).

## Edge case

- **Source PDF is scan-only with no text layer**: note the limitation and ask the user to open the PDF directly and report the key value.
