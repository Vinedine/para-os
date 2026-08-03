# Changelog

Template revisions. Each vault's `CLAUDE.md` carries the revision it was last aligned to, as an HTML comment on line 3:

```
<!-- para-os-template: 2026.08 -->
```

`/para-upgrade` reads that marker, compares it against the master's, and applies the entries below that fall between the two. A vault with **no marker** predates the scheme: treat it as pre-2026.08 and run the full 2026.08 entry against it.

Revisions are dated `YYYY.MM`, not semver. They mark "the template changed in a way an existing vault has to react to". Wording tweaks that change no rule don't get a revision.

---

## 2026.08

The largest structural revision so far. Six changes need a reaction from an existing vault; the first is the one that moves the most files.

**Where a checkbox may live.** New `## Actions` section carrying the bucket table: `projects/` and `areas/` hold open and closed items, `archive/` holds closed ones only, and **`resources/` may never hold a checkbox** - one there is always a filing error. `/para-daily-brief` now discards `resources/` paths outright. Vaults that kept `actions.md` files under `resources/ideas/` must fold those items into each `brief.md` before the work goes invisible.

**An `actions.md` archives with its entity.** Replaces the old "never archive an `actions.md`" rule, which contradicted what `/para-archive` actually does. It archives fully closed; one open `- [ ]` means the entity was archived too early.

**The PARA sorting test, and `### Lifecycle`.** *Committed and dated → project. Maintained, no end date → area. Only thinking about it → idea. Over → archive.* A rolling improvement backlog on something you own is an area wearing a project name. Expect existing `projects/` folders to fail this test: a brief whose own status line reads "Active" or "Ongoing maintenance" is describing an area.

**`📅` means a real-world deadline, never an aspiration.** A decision with an invented date is still a deliberation, and the fake date only makes it surface as falsely overdue.

**Skeleton files an older vault may lack.** `resources/scripts/README.md` (the `PARAOS_HOME` resolver snippet plus a table of installed scripts) and `.claude/settings.json` (`autoMemoryEnabled: false`). The settings file is for adopters with no user-level Claude settings; a vault whose user-level settings already set the same keys should not carry a redundant copy.

**Section renames and de-bloat.** `## Filing rules` → `## Filing and naming`, with task markers folded in under `## Actions`. Memory and File formats condensed. `## Integration scripts and their state` shrinks to a pointer: its state buckets, `PARAOS_HOME` resolver, and language preference now live in `resources/scripts/README.md` (above), read when a script is touched rather than every session. Only the secret-never-inside-the-vault rule stays in `CLAUDE.md`.

Also in this revision, both housekeeping rather than migration work:

- **`triage/` never holds a `README.md`.** Every file there is by definition unprocessed, so a permanent one is indistinguishable from a real item and inflates the loose-file count forever. The skeleton ships `.gitkeep` instead. Delete any `triage/README.md` an earlier skeleton left behind.
- **Two machine-read markers at the top of `CLAUDE.md`**: the `<!-- para-os-template: -->` comment above, and a `**Type:**` line for your own tooling to key off. Both must survive every upgrade.
