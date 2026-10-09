---
name: para-pipeline
description: Render the board for every lifecycle the vault declares - each entity at its stage with days in stage, its next dated step and where it came from, the flags for what has stopped moving, the counts by stage and the quarter's metrics - closing on one next action. Use when the user asks "where does the pipeline stand", "what is in the funnel", "which deals have gone quiet", "what stage is <name> at", "show me the property pipeline", or types /para-pipeline [<lifecycle>].
allowed-tools: Bash(python3 *), Bash(py *), Bash(pwd *), Glob, Grep, Read
argument-hint: '[<lifecycle>] [--test]'
---

# Para pipeline

The board for **staged entities**: every lifecycle the vault declares, each entity at its stage, the next step and its date, what has stopped moving, and what the quarter did.

**Read-only contract.** It reports; the operator moves the entity, and a flag here is what prompts the edit.

**This skill is vault-agnostic.** It knows only declared lifecycles and Stage lines ([para-shared/lifecycles.md](../para-shared/lifecycles.md)), and every line it prints uses the vault's own entity and stage names, never a scan field's.

## Arguments

| Arg | Renders |
|---|---|
| *(none)* | Every declared lifecycle in turn: board, flags, counts, metrics, one closing next action |
| `<lifecycle>` | One lifecycle, matched on its heading noun (`deal`) or its heading text (`Deal lifecycle`), case-insensitively. Everything else is the same |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

A leftover argument follows [operating-discipline.md](../para-shared/operating-discipline.md#arguments), a lifecycle name being one or two words; prose naming a lifecycle noun ("the property pipeline") makes that noun the argument. A name matching no declared lifecycle is asked about, never widened to all of them, even where the vault declares only one.

## Procedure

### Step 1: Read the declarations

Resolve the vault root per [operating-discipline.md](../para-shared/operating-discipline.md#defer-to-the-vault), then verify it: `projects/` plus at least one of `areas/` `archive/`, and a `CLAUDE.md`. If it is not one, stop and say so, naming the path you actually checked.

Read the vault's `CLAUDE.md` for every section whose heading ends in `lifecycle` ([para-shared/lifecycles.md](../para-shared/lifecycles.md)), and the rule file their documents load.

**A vault that declares none has nothing to render.** Say so in one line, name the two places a lifecycle comes from (a flavor, a module), and stop. Never infer stages from folder names.

**A lifecycle argument is matched here**, against the declared headings and nouns. On no match, ask which declared lifecycle was meant, naming them, and stop: no board renders in the same reply.

### Steps 2 and 3: Scan the homes, resolve each entity

One call, per [para-shared/scripts.md](../para-shared/scripts.md):

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/pipeline_scan.py" --vault <root> [--lifecycle <name>] [--today YYYY-MM-DD] > <scan output path>
```

Pass `--lifecycle` only under a lifecycle scope. Exit 3 (`no such lifecycle`, with the `declared` list) is asked about as in Step 1. **Field table: [references/scan.md](references/scan.md).**

### Step 4: Render

Word what the scan computed into the board, the flags, the counts, the metrics and the one Next action, reading nothing past it. **Layout and rules: [references/render.md](references/render.md).**

## Strict rules

- **Never invent a stage, a date or a next step.** Unknown stays unknown, and a missing step is flagged.
- **Never rank, score, weight or forecast.** The board follows the vault's stage order, with no probability, conversion rate or funnel percentage: a pipeline of a dozen entities is read, not modelled.
- **A value figure is internal.** It renders in the terminal, never into a file or anything shared outside the vault.
