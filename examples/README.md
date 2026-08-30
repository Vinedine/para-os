# Examples

Synthetic worked vaults. Every person, company, property, and number in here is fictional; the structure and conventions are the real thing.

- [`belfoot-vault/`](belfoot-vault/): a default (plain editable markdown) vault for a fictional consulting engagement: BelFoot FC, a Belgian football club running an IT modernisation programme. Two projects with briefs and actions, four stakeholder contact files, dated meeting records, and a vault `CLAUDE.md`. To see the skills work: copy `base/.claude/skills/` into `belfoot-vault/.claude/` (skills load from the session's own folder, not from a sibling), open a Claude Code session in the vault root, and run `/para-daily-brief` or `/para-triage`. The copied skills stay untracked (see the repo `.gitignore`), so `base/` remains their single source.

`triage/` ships with three unfiled items so `/para-triage` has real work: one badly-named call note that belongs in a project's `sources/`, one Dutch steering-group record spanning three entities (its name stays Dutch through the rename), and one item the vault's own Operating model puts outside the engagement. Run it before `/para-deep-clean`, which stops while loose files remain - that precondition firing is the product working, not a fault.

**These vaults have a frozen reference date** (BelFoot: 2026-06-24), stated at the top of each vault's `README.md`. Dates are anchored to the fiction rather than refreshed to the calendar, so a dashboard run today will read as heavily overdue. That is the example ageing, not the skill misreporting.

A **readonly-ipad** example vault is planned.
