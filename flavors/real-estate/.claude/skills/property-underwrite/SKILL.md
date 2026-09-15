---
name: property-underwrite
description: Bring one property's dossier to decision-ready - focused folder cleanup, enrichment from the vault's mailboxes, the lookups and portals its source register names, and comparables, then an analyst-persona pass producing structure, economics, two scenarios and a clear verdict, all written into the dossier. Covers prospects, deals in progress and held properties. Use when asked to underwrite a property, enrich a brief, run the analyst pass, refresh a held property's numbers, or on /property-underwrite <property>.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write, WebSearch, WebFetch, AskUserQuestion, TodoWrite, ToolSearch, mcp__*__search_threads, mcp__*__get_thread, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content
arg-hint: '<property-name> [--test]'
---

# Property underwrite

Brings a property's dossier to **decision-ready**: every reachable fact gathered, every number underwritten through the vault's analyst persona, and a verdict that falls out of the math. **All thinking happens here**, and everything this skill produces lands in the dossier, never in a side document.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Ask which property to underwrite |
| `<property-name>` | Match against `projects/`, `resources/ideas/`, then `areas/properties/` |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## What it reads

1. **The vault's `CLAUDE.md`**: its `**Flavor:**` and `**Delivery:**` lines, the books line under `## Deal sheets`, the network-card convention, the language rule. Then `.claude/rules/property-dossier.md` and `property-sources.md`.
2. **The source register**, `resources/property-evaluation/property-data-sources.md`. Every local fact comes from it; a local fact it does not name is never assumed.
3. **The analyst persona**, found by shape and not by name: the one folder under `resources/prompts/` holding a `*.core.md` and `adapters/claude-code.md`. Its `knowledge/` carries the tax and structure reasoning for the vault's jurisdiction.

Any of the three missing: stop and ask.

## Procedure

Track the phases in the harness's task list. Each phase ends with a short summary and waits for the go-ahead; never advance past a phase that changed files without one. On `**Delivery:** readonly-ipad`, run [its edit cycle](../para-shared/operating-discipline.md#the-read-only-ipad-delivery) around the writes.

1. **Setup**: the property and the mode. **Procedure: [references/enrichment.md](references/enrichment.md).**
2. **Focused folder cleanup**, this folder only. **Procedure: [references/enrichment.md](references/enrichment.md).**
3. **Email enrichment** from the mailboxes the vault declares. **Procedure: [references/enrichment.md](references/enrichment.md).**
4. **Register and web enrichment**: lookups, listings, comparables. **Procedure: [references/enrichment.md](references/enrichment.md).**
5. **Analyst underwriting** and the verdict. **Procedure: [references/underwriting.md](references/underwriting.md).**
6. **Report.** **Procedure: [references/underwriting.md](references/underwriting.md).**

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Never invent** a price, comparable, rent, renovation cost, date, name or rate. A flagged assumption is acceptable; a fabricated fact is not.
- **Local facts come from the register, tax reasoning from the persona's `knowledge/`**, never from memory. A rate or a registry not named there is a question, not a default.
- **Mailboxes are read-only.** No send, reply, label or archive.
- **Never translate.** Match the source language and keep local legal and tax terms verbatim.

## Stop and ask

When the property match is ambiguous or absent; the dossier is an empty stub; the persona or the register is missing; or anything else is genuinely uncertain. A load-bearing number no source gives is not a stop: [Step 5](references/underwriting.md) handles it.
