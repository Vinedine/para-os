# Phase 4 - Rule-driven content violations

Find the content that breaks the *new* rules. This is where the destructive work is.

Derive the checks from the changelog entries rather than a fixed list. For the 2026.08.01 revision that means: checkboxes under `resources/`, open checkboxes in `archive/`, `projects/` entries whose own brief describes a maintained area, aspirational `📅` dates, contact files with an empty actions heading.

**Approval discipline follows [operating-discipline.md](../../para-shared/operating-discipline.md), strictly.** Everything in this phase is destructive or reclassifying: deleting an `actions.md`, moving a folder between PARA buckets, demoting a project to an idea. Those are approved **one at a time**, never batched, and each needs the routing decision made first: an open item that survives the move goes somewhere explicit (into the brief, into the owning area, onto a contact file). Items dropped in a migration are gone; only git history remembers them.

Two things that are never automatic:

- **Reclassification is proposed, not applied.** Bucket moves reshape how the operator thinks about their own work. Present the evidence (what the brief's own status line says) and let them rule.
- **Retiring anything is the user's call.** No sweep for stale entities, no automatic archiving.

**Every move repoints inbound links in the same pass.** A migration that skips this leaves references pointing at nothing, and the rot only surfaces months later in whatever reads them.

## A CLAUDE.md over the 200-line target

Check the line count at the end of every run. A condensing revision can leave a vault over target and **Phase 1 is not allowed to close the gap**: the template's sections are the only ones it may rewrite, and a mature vault's own sections are usually most of the file. Left there, the migration installs a target the vault fails on arrival, with no phase permitted to reach it - which teaches the operator the number is decorative.

So when the file is over target after Phase 1, **propose extraction, one candidate at a time, and apply nothing without a yes.** The candidates, in the order they usually pay:

- **Procedure** - an ordered list of steps, a section structure, a naming scheme with more than about five rules. It moves to `.claude/rules/<topic>.md`, which the agent loads when it opens the file that needs it, leaving a one-line pointer behind. This is the highest-yield move and the least lossy: nothing is deleted and the rule still reaches the session that needs it.
- **Rationale** - the paragraph explaining why a rule exists. It belongs to git history, and the rule survives without it.
- **A description of a script's behaviour** - it belongs in that script's README or docstring, which is also where it will actually be kept true.

Never propose cutting a vault's own operating rules to reach the number, and never cut a rule that exists because something once went wrong. **Being over target is a finding, not a failure**: report the count, name the candidates with their line savings, and let the operator rule. A vault that stays at 240 lines because every line earns its place is correct, and saying so is a better outcome than a file trimmed to 199 by deleting something load-bearing.

## Edge case

- **Counting characters in a normalization pass.** `grep -c` counts matching *lines*, not occurrences, and byte-wise matching in a non-UTF-8 locale makes multi-byte patterns match fragments of unrelated characters. Use a UTF-8-aware codepoint scan for any before/after count, and re-verify with one after applying.
