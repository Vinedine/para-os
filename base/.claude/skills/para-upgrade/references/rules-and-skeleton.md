# Phases 1 and 2 - CLAUDE.md structure, then skeleton files

## Phase 1 - CLAUDE.md structure

Diff the vault's `CLAUDE.md` against the template at the ref (`base/CLAUDE.md.template`, or the flavor's skeleton template if the vault declares a flavor). For each changelog entry, check whether the vault's file states the new rule, states the old one, or is silent.

**Read the template at the vault's own marker too, as a baseline.** Diffing against the new template alone cannot tell a section the vault never had from one it deliberately rewrote. Diffing against both can: where the vault departs from its *own* baseline, that departure is a decision. Carry it forward rather than flattening it back to the template. A vault with no marker has no baseline: diff against the new template alone and say so, rather than treating the oldest changelog revision as one.

**Contradictions rank first.** A vault carrying the superseded version of a rule is worse than one that's merely silent: the agent reads it at runtime and acts on it, so the vault actively fights its own skills until fixed. Report those separately from the merely-missing.

**The template is a floor, not a ceiling.** Never delete a section, rule, or marker just because the template doesn't have it. Vaults legitimately carry their own: extra area definitions, per-vault operating rules, cross-vault references, a `**Type:**` label, triage-source tables. When the template restructures a section the vault has extended, keep the vault's content and move it under the new heading.

**Restructure, don't rewrite.** Match the vault's existing voice and language, including a non-English one. Condensing prose to match the master's tightened wording is a *separate* pass: offer it, don't fold it in. The one exception is a changelog entry that names the condensing as its change: then the vault's copy of each section the entry lists is replaced by the template's shorter text, and only the vault's own departures from its baseline are carried forward into it.

## Phase 2 - Skeleton files

For each file the skeleton ships at the ref, check whether the vault has an equivalent. Create only what's genuinely missing, and only after checking whether the vault already gets the same effect another way.

**`.claude/settings.json` - check effective settings before creating.** The skeleton ships it for adopters with no user-level Claude settings. If the user's `~/.claude/settings.json` already sets every key the skeleton would set, **do not create a vault-level file**: it is a redundant copy of a setting that is already in force, and it drifts the moment the user changes their global. Read the user-level file first, compare key by key, and create or extend the vault-level file only for keys not already effective there. If the vault already has one for its own reasons (project-specific hooks, for instance), merge the missing keys into it rather than overwriting.

**`triage/README.md` - never create one.** Every file in `triage/` is by definition unprocessed, so a permanent README is indistinguishable from a real item: it inflates `/para-daily-brief`'s loose-file count forever and trips `/para-deep-clean`'s "triage must be empty" precondition on every run. Use `.gitkeep` to hold the empty folder in git. If the vault has a `triage/README.md` from an older skeleton, propose deleting it.

Other skeleton files (`resources/scripts/README.md`, folder placeholders) are created when absent, populated from what's actually on disk in that vault. Never invent inventory.

**A skeleton file the vault already has is still in scope when a changelog entry says so.** Where an entry names a rule the file must now carry, add that to the vault's existing copy in the vault's own words. Only what the entry names: re-flowing the whole file to match the skeleton is the rewrite Phase 1 already forbids.
