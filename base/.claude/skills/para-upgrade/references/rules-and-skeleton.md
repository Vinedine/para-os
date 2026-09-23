# Phases 1 and 2 - CLAUDE.md structure, then skeleton files

## Phase 1 - CLAUDE.md structure

Diff the vault's `CLAUDE.md` against the template at the ref ([resolved per delta.md](delta.md#resolving-the-master)), plus `addons/<name>/CLAUDE.md.sections` for the declared flavor and each declared module, diffed the same way. **A module's sections are merged beside the base, delivery and flavor ones, never over one**: where a module and the vault both state a rule for the same section, the vault's own wording stands and the module's addition joins it. For each changelog entry, check whether the vault's file states the new rule, states the old one, or is silent.

**Read the template at the vault's own marker too, as a baseline.** Where the vault departs from its *own* baseline, that departure is a decision: carry it forward rather than flattening it back to the template. The scan's `baseline` block resolves the commit - [scan.md](scan.md) states the walk, always from commits even where the master itself is read from the working tree. A vault with no marker, or one never committed, has no baseline (`baseline.commit` null): diff against the new template alone and say so. Normalise line endings on both sides of both diffs.

**The marker line is never part of the text you carry over.** It is line 3 of the template, so a section-by-section replacement picks it up. Hold the vault's existing marker through every phase and let Phase 5 write the new one.

**Contradictions rank first.** A vault carrying the superseded version of a rule fights its own skills until fixed. Report those separately from the merely-missing.

**The template is a floor, not a ceiling.** Never delete a section, rule, or marker just because the template doesn't have it. Vaults legitimately carry their own: extra area definitions, per-vault operating rules, cross-vault references, a `**Type:**` label, triage-source tables. When the template restructures a section the vault has extended, keep the vault's content and move it under the new heading.

**Restructure, don't rewrite.** Match the vault's existing voice and language, including a non-English one. Condensing prose to match the master's tightened wording is a *separate* pass: offer it, don't fold it in. The one exception is a changelog entry that names the condensing as its change: then the vault's copy of each section the entry lists is replaced by the template's shorter text, and only the vault's own departures from its baseline are carried forward into it.

## Phase 2 - Skeleton files

The scan's `skeleton` block already enumerates each file the resolved master ships at the ref (base plus the declared flavor's and each declared module's `.claude/rules/` and `skeleton/**`, the delivery's `skeleton/` overlaid) against what the vault has - [scan.md](scan.md) states the field table. Create only what's genuinely missing (`present: false`), and only after checking whether the vault already gets the same effect another way.

**Adding a rule file**, grep the vault's `CLAUDE.md` for sentences stating the rule the file states, and propose trimming them to the pointer.

**A rule file the vault already has is verified, never re-copied.** The scan's `rules` block already carries the three checks a rule file has to pass - `paths_missing`/`paths_extra` against what the changelog entry states, `doubled.missing_twins` where the vault is on a collected delivery, and `anchors` for the kind it claims - plus `pointer` for its wording and where it sits in `CLAUDE.md`. Change only what fails a check.

**Copying a shipped convention file into a vault whose `CLAUDE.md` already states its rule.** A *richer version* is a fuller statement of that same rule (figure-specific wording, the source-document naming), and it moves into the copy verbatim under the base file's headings; a broader principle the file merely specialises (a general say-it-once bullet) stays inline, as the template keeps it. A vault whose default differs from the file's (another naming pattern) changes the default in its copy and in its `CLAUDE.md` one-liner together, so the two never name different defaults. A vault may extend a convention file's `paths:` to its own document kinds governed by the same rule; a rule for a kind outside every file's `paths:` stays inline in `CLAUDE.md`.

**`.claude/settings.json` - check effective settings before creating.** The skeleton ships it for adopters with no user-level Claude settings. The scan's `settings` block already compares the master's keys against the user level and the vault level, key by key ([scan.md](scan.md)): create or extend the vault-level file only for `missing_effective` keys. If the vault already has one for its own reasons (project-specific hooks, for instance), merge the missing keys into it rather than overwriting.

**`triage/README.md` - never create one.** Every file in `triage/` reads as an unprocessed item. Use `.gitkeep` to hold the empty folder in git. If the vault has a `triage/README.md` from an older skeleton, propose deleting it.

Other skeleton files (`resources/scripts/README.md`, folder placeholders) are created when absent, populated from what's actually on disk in that vault. Never invent inventory. A placeholder whose own text says to delete it once content lands is satisfied by a folder that already has content.

**A skeleton file the vault already has is still in scope when a changelog entry says so.** Where an entry names a rule the file must now carry, add that to the vault's existing copy in the vault's own words. Only what the entry names: re-flowing the whole file to match the skeleton is the rewrite Phase 1 already forbids.
