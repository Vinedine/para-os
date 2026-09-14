---
name: property-dealsheet
description: Convert one property's decision-ready dossier into the designed deal sheet (HTML, rendered to PDF on the read-only iPad delivery). Pure derivation - reads only the dossier, fills the vault's deal-sheet template, embeds images. It gathers no new information; a missing fact stops it and points to /property-underwrite or /property-reconcile. Covers acquisitions and held properties, with a per-unit table for a building sold unit by unit. Use when asked to build or refresh a deal sheet, or on /property-dealsheet <property>.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write, AskUserQuestion, TodoWrite
arg-hint: '<property-name> [--test]'
---

# Property dealsheet

Turns one property's dossier into the designed deal sheet a decision-maker reads, as `## Deal sheets` in the vault's `CLAUDE.md` defines it. The dossier is the underwriting model; the sheet is the derived memo.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Ask which property |
| `<property-name>` | Match against `projects/`, `resources/ideas/`, then `areas/properties/` |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## What it reads

- **The vault's `CLAUDE.md`**: its `**Delivery:**` line, the `## Deal sheets` rules, the language rule.
- **The template**, `resources/prompts/dealsheet-template.html`. Its header comment is the design system, the section skeleton and the stage variants.
- **The source register**, `resources/property-evaluation/property-data-sources.md`, for two things only: which facts no free source settles, and the plan renderer if it names one.
- **The dossier**, the only fact source.

Template or dossier missing: stop and ask.

## Procedure

Track the phases in the harness's task list. On `**Delivery:** readonly-ipad`, run [its edit cycle](../para-shared/operating-discipline.md#the-read-only-ipad-delivery) around the build.

1. **Locate and check readiness.** Resolve the vault root once and hold it (`operating-discipline.md`). Resolve the property to exactly one folder and its dossier; none or several, stop and ask. Run the readiness check, and on any gap stop with the checklist. **Procedure: [references/build.md](references/build.md).** Summarise the verdict and get the go-ahead.
2. **Build the sheet** from the template. **Procedure: [references/build.md](references/build.md).** Get the go-ahead before rendering.
3. **Render or verify, and report.** **Procedure: [references/build.md](references/build.md).**

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **The dossier is the only fact source.** Every number, date, name and the verdict come from it. No email, no web, no analyst pass, no source document read for facts: a need the dossier cannot meet is a gate, never a research task.
- **Copy-fill the template, never an existing sheet**, and never hand-patch a number into a built sheet: rebuild it.
- **Honesty.** Every estimate the dossier flags stays flagged in the Assumptions block; never soften an open item.
- **The sheet's language is the dossier's**, the template's own labels included.

## Stop and ask

When the property match is ambiguous or absent; the template is missing; the readiness check fails; or the dossier contradicts itself on a load-bearing number, which is a `/property-reconcile` signal.
