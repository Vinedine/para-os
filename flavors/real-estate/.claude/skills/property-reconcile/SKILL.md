---
name: property-reconcile
description: Verify one property's dossier against its own source documents and the owner's books - parallel readers extract facts from every file in sources/ and the per-property ledger, each claim is checked, drift is corrected with a citation, and conflicts the documents cannot settle become open items. A fact the vault's source register lists as unobtainable is not an error. Use before a bid or deal sheet, after new sources land, when asked to reconcile or fact-check a brief, or on /property-reconcile <property>.
allowed-tools: Agent, Bash, PowerShell, Glob, Grep, Read, Edit, Write, AskUserQuestion, TodoWrite
arg-hint: '<property-name> [--test]'
---

# Property reconcile

Answers one question: **does what the dossier says match what the source documents and the owner's own books say?** A verification skill, not an enrichment one.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Ask which property to reconcile |
| `<property-name>` | Match against `projects/`, `resources/ideas/`, then `areas/properties/` |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## What it reads

- **The vault's `CLAUDE.md`**: its `**Flavor:**` and `**Delivery:**` lines, the books line under `## Deal sheets`, the language rule.
- **`.claude/rules/property-dossier.md`** (the shape claims live in) and **`property-sources.md`** (how `sources/` is named).
- **`resources/property-evaluation/property-data-sources.md`**, the source register: it says which gaps are unobtainable. It is not a licence to fetch.

A vault that declares no `**Flavor:** real-estate` and has no dossier rule is not a property vault: ask which vault to run in.

## Procedure

Track the phases in the harness's task list. On `**Delivery:** readonly-ipad`, run [its edit cycle](../para-shared/operating-discipline.md#the-read-only-ipad-delivery) around the writes.

1. **Locate.** Resolve the vault root once and hold it (`operating-discipline.md`). Resolve the property to exactly one folder and its dossier: `brief.md` in `projects/` or `resources/ideas/`, `README.md` in `areas/properties/`. None or several: stop and ask. List every file in `sources/`; with none, continue on the books alone if the vault names them, otherwise stop. Summarise and get the go-ahead.
2. **Extract, in parallel.** One agent per group of source documents plus one for the books, each returning quoted facts only. **Procedure: [references/extraction.md](references/extraction.md).**
3. **Reconcile claim by claim**, then the books pass on stage and cost. **Procedure: [references/reconcile.md](references/reconcile.md).**
4. **Apply after approval, and report.** **Procedure: [references/reconcile.md](references/reconcile.md).**

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Primary documents outrank quotes, and the books outrank documents on money and stage.** A figure on an official document (a registry extract, a certificate, a lease, a permit) outranks one quoted in a listing, an email or an earlier debrief. A derived file inside `sources/` (a debrief, a summary) is a claim to verify, never an authority to verify against.
- **Only `sources/` and the books.** No email or web (`/property-underwrite`), no restructuring (`/para-deep-clean`).
- **Never translate.** Keep local legal and tax terms verbatim.

## Stop and ask

When the property match is ambiguous or absent; there is nothing to verify against; a scan cannot be read; or two sources conflict on a load-bearing number and neither document can say which is current.
