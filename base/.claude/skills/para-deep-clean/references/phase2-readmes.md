# Phase 2 - README structure consistency

Goal: the root README matches the para-os shape, and every entity README follows a documented canonical structure for the vault.

## Step 2.0 - Root README first

Its shape is not per-vault: every para-os `CLAUDE.md` fixes the same four opening headings, checked in Phase 1 Step 1.1. Fix those findings here, facts preserved verbatim: rename or translate headings to the four; fold numbered or renamed opening sections under them (an inventory or brand list becomes a `###` under Track record); write Vision from what the vault already says and flag it as inferred; reduce a "Working in this vault" section to one closing line.

Everything below this step concerns *entity* READMEs, whose shape is the vault's own.

## Step 2.1 - Check for canonical structure documentation

Read `CLAUDE.md`. Does it already describe what an entity README or brief contains, **under any heading**? Vaults word it differently (`## README structures`, `### Brief structure`, `## Entity shapes`), so look for the section by what it says rather than by its name - the same lookup `/para-new`'s `scaffold.md` makes. A vault that has declared a shape under an unexpected heading has not declared none.

**Where one exists, audit against it and add nothing.** Drafting a second section beside it leaves the vault with two descriptions of one thing, which is the say-it-once rule broken by the skill that enforces it, in the file every session reads first. Propose extending the existing section if it is genuinely incomplete.

**Where none exists**, draft one from what the existing READMEs already share and propose adding it, naming the heading you would use and keeping it short - `CLAUDE.md` states rules and stays under 200 lines with everything the vault adds.

**Order is the vault's call, not this skill's.** A declared shape may fix its section order as a contract, or may say order varies by entity and is not enforced. Audit against whichever it does, and **never report a vault as non-conforming for an order it deliberately declined to fix**. A structure this skill drafts specifies that sections which don't apply get explicit `_n/a_` lines (not omission, so gaps stay visible) and includes the domain-specific sections the vault's purpose needs; whether it also fixes an order is a question for the operator.

**This skill brings no default section list for entities.** The canonical structure comes from each vault's CLAUDE.md. Never invent or import a template.

## Step 2.2 - Archived and dead entities

Check CLAUDE.md for a documented archived-entity template, often shorter than the active one. If none is documented, **ask the user** - do not apply a default. Archived entities don't need open-items or active-relationship sections, but carry enough context (status marker, why archived, where source docs live) to be self-explanatory years later.

## Step 2.3 - Apply

For each entity README:

- Do the **first one as a worked example** and pause for approval before batching the rest.
- Preserve all existing facts verbatim - only reorganize and add missing sections.
- Promote inline bolded blocks (Ownership, Notary) to `##` sections for consistency.
- Add `_n/a_` placeholders for sections that genuinely don't apply.

## Edge case

- **A status or cost-basis table makes no sense for the entity type**: substitute a domain-appropriate "status at a glance" table. For jobs: salary band, stage, last contact. For contacts: role, last interaction, open asks. The principle is one table near the top that answers "where do we stand" in one look.
