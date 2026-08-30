# Phase 4 - Rule-driven content violations

Find the content that breaks the *new* rules. This is where the destructive work is.

Derive the checks from the changelog entries rather than a fixed list. For the 2026.08.01 revision that means: checkboxes under `resources/`, open checkboxes in `archive/`, `projects/` entries whose own brief describes a maintained area, aspirational `📅` dates, contact files with an empty actions heading.

**Approval discipline follows [operating-discipline.md](../../para-shared/operating-discipline.md), strictly.** Everything in this phase is destructive or reclassifying: deleting an `actions.md`, moving a folder between PARA buckets, demoting a project to an idea. Those are approved **one at a time**, never batched, and each needs the routing decision made first: an open item that survives the move goes somewhere explicit (into the brief, into the owning area, onto a contact file). Items dropped in a migration are gone; only git history remembers them.

Two things that are never automatic:

- **Reclassification is proposed, not applied.** Bucket moves reshape how the operator thinks about their own work. Present the evidence (what the brief's own status line says) and let them rule.
- **Retiring anything is the user's call.** No sweep for stale entities, no automatic archiving.

**Every move repoints inbound links in the same pass.** A migration that skips this leaves references pointing at nothing, and the rot only surfaces months later in whatever reads them.

## Edge case

- **Counting characters in a normalization pass.** `grep -c` counts matching *lines*, not occurrences, and byte-wise matching in a non-UTF-8 locale makes multi-byte patterns match fragments of unrelated characters. Use a UTF-8-aware codepoint scan for any before/after count, and re-verify with one after applying.
