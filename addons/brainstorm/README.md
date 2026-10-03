# Module: brainstorm

For an operator who wants a route from "this keeps costing me time" to a short list of ideas worth testing. A module is a **function a vault adds beside whatever it is about**, so this adds one skill, `/para-brainstorm`, and the one section that tells the vault where its session records live.

Onboarding's phase 2 inventories work that already exists; `/para-new idea` records a concept already formed. This sits between the two: it harvests the operator's frustrations, turns them into problem statements, generates ideas with the operator's first, and lands at most three through `/para-new`. It runs as often as the operator wants, in one sitting or across several.

It sits beside any flavor.

## What it adds

1. **A `CLAUDE.md` section** ([`CLAUDE.md.sections`](CLAUDE.md.sections)): `## Brainstorms`, saying where a session record files and that an idea nobody picked lives there and nowhere else.
2. **The skill** ([`.claude/skills/para-brainstorm/`](.claude/skills/para-brainstorm/SKILL.md)), installed beside the base skills. It reads `para-shared/` and hands every approved idea to `/para-new`.

No rule file and no skeleton: an idea's brief follows the vault's own shape, and the records file under the vault's own filing rule.

## Setup

A new vault is offered the module once its phase 2 plan is approved, and the onboarding runs these steps itself. An existing vault adopts it by hand:

1. Add `**Modules:** brainstorm` under the `**Type:**` line of the vault's `CLAUDE.md`, comma-separated where the vault already declares one, and merge in `CLAUDE.md.sections`.
2. Copy `.claude/skills/para-brainstorm/` beside the base skills.
3. Run `/para-brainstorm`, or `/para-brainstorm <path>` on notes from a session already held.
