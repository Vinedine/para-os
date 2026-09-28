# Phase 2 - README structure consistency

Goal: the root README matches the para-os shape, and every entity README follows a documented canonical structure for the vault.

## Step 2.0 - Root README first

Its shape is not per-vault: every para-os `CLAUDE.md` fixes the same four opening headings, checked in Phase 1 Step 1.1. Fix those findings here, facts preserved verbatim: rename or translate headings to the four; fold numbered or renamed opening sections under them (an inventory or brand list becomes a `###` under Track record); write Vision from what the vault already says and flag it as inferred; reduce a "Working in this vault" section to one closing line.

## Step 2.1 - Check for canonical structure documentation

Find the vault's declared shape for entity READMEs and briefs, per [A vault's rule files](../../para-shared/operating-discipline.md#a-vaults-rule-files).

**Where one exists, audit against it and add nothing.** Propose extending it where it lives if it is genuinely incomplete.

**Where none exists**, draft a shape file from what the existing READMEs already share, per the rule-file contract in the vault's `CLAUDE.md` `## Do not add`, and propose adding it with its pointer.

**Order is the vault's call, not this skill's.** A declared shape may fix its section order as a contract, or may say order varies by entity and is not enforced. Audit against whichever it does, and **never report a vault as non-conforming for an order it deliberately declined to fix**. A structure this skill drafts specifies that sections which don't apply get explicit `_n/a_` lines and includes the domain-specific sections the vault's purpose needs; whether it also fixes an order is a question for the operator.

**"At least" names a content contract, not a heading contract.** Where a declared shape says a document carries at least a named set of facts, the facts must be present, under any heading. Renaming sections to the shape's own headings is optional: offer it, never apply it by default.

**This skill brings no default section list for entities.** Never invent or import a template.

## Step 2.2 - Archived and dead entities

Check `CLAUDE.md` and its rule files for a documented archived-entity template. If none is documented, **ask the user** - do not apply a default. Archived entities don't need open-items or active-relationship sections, but carry enough context (status marker, why archived, where source docs live).

## Step 2.3 - Apply

For each entity README:

- Do the **first one as a worked example** and pause for approval before batching the rest.
- Preserve all existing facts verbatim - only reorganize and add missing sections.
- Promote inline bolded blocks (Ownership, Notary) to `##` sections, except where the declared shape uses bold labels there itself. The heading replaces the bold label; the text beneath stays verbatim.
- Add `_n/a_` placeholders for sections that genuinely don't apply.

**In a vault with no entity README tier**, where every entity is documented by its `brief.md`, apply to each brief only what its shape file names, and to each contact file only what `CLAUDE.md` fixes for it: no promoted bold blocks and no `_n/a_` placeholders the shape does not require.

## Edge case

- **A status or cost-basis table makes no sense for the entity type**: substitute one domain-appropriate table near the top that answers "where do we stand" in one look.
