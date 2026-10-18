# The skills

| Skill | What it does |
|---|---|
| [`/para-triage`](../base/.claude/skills/para-triage/SKILL.md) | Empties `triage/`: identifies each loose file, proposes a destination and a convention-conform rename, executes after your approval. |
| [`/para-daily-brief`](../base/.claude/skills/para-daily-brief/SKILL.md) | Where the vault stands: vault state, what is due now (capped at five), health flags, ideas, agenda and triage, closing on one next action. |
| [`/para-prep`](../base/.claude/skills/para-prep/SKILL.md) | Prepares a meeting from the vault's own files: who is coming and what their contact cards say, the work each one is tied to, what is open in both directions, the record of the last meeting and what was promised, and what the vault does not know, as questions to ask. Reads the same agenda as the daily brief, and writes nothing. |
| [`/para-deep-clean`](../base/.claude/skills/para-deep-clean/SKILL.md) | Periodic maintenance: structural audit, README normalisation, closing documented open items by reading the source files. |
| [`/para-new`](../base/.claude/skills/para-new/SKILL.md) | Starts one project, area, idea, or contact: sorts it first, so committed work becomes a project, a maintained responsibility becomes an area, and a concept stays an idea, asks the two or three questions that shape needs, and scaffolds it. Also promotes an idea. |
| [`/para-archive`](../base/.claude/skills/para-archive/SKILL.md) | Closes out one finished project, shelved idea, or an area the vault names an archive destination for: reconciles open actions, validates its records, moves it to `archive/`, and repoints links in both directions - references to it, and the relative links written inside it, which change depth on the move. Then proposes its Track record line and routes its lessons. |
| [`/para-pipeline`](../base/.claude/skills/para-pipeline/SKILL.md) | The board for anything that moves through stages (deals, properties, applications): each one at its stage, its next dated step, what has stopped moving, and what the quarter did. Reads the stages a vault declares for them in its `CLAUDE.md` ([the format](../base/.claude/skills/para-shared/lifecycles.md)); a vault that declares none needs nothing here. |
| [`/para-upgrade`](../base/.claude/skills/para-upgrade/SKILL.md) | Migrates a vault to a newer template revision: reads the marker in its `CLAUDE.md`, applies the intervening [`CHANGELOG.md`](../CHANGELOG.md) entries, and re-stamps it. Run before a deep clean, which otherwise audits against a stale contract. |

[Add-ons](../addons/README.md#available) and [`multi-vault/`](../multi-vault/README.md) bring skills of their own.

**Your own skills.** A vault can grow skills of its own, and three rules keep them supportable. A request starts as a prompt in `resources/prompts/` and becomes a skill after its third use, the same wait-until-proven rule the vault applies to templates. It is built with Anthropic's `skill-creator` skill, so it stays well-formed. And it never takes the `para-` prefix, which belongs to para-os: `/para-upgrade` treats a skill with a name para-os ships as its own copy and replaces it.

`/para-daily-brief` against the example vault (fragment):

````
# Daily Brief - 2026-06-24 - BelFoot

## 🎯 Now (5 of 26)
1. 🔺 Get Jan's decision on the three Q3 cost-recovery options - [network/jan-claes:26] · 📅 2026-06-22 (2d ago)
2. 🔼 Pre-brief Pieter on the Q3 cost issues before the walk-through - [network/pieter-de-ryck:19] · 📅 2026-06-23 (1d ago)
**Later:** 3 this week · 6 next 30 days · 5 later · 5 recurring · 1 waiting · 1 undated

---
**Next action:** Open Jan's May 29 cost-recovery mail and pick the option you would defend - [network/jan-claes:26]
````
