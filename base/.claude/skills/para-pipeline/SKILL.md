---
name: para-pipeline
description: Render the board for every lifecycle the vault declares - each entity at its stage with days in stage, its next dated step and where it came from, the flags for what has stopped moving, the counts by stage and the quarter's metrics - closing on one next action. Use when the user asks "where does the pipeline stand", "what is in the funnel", "which deals have gone quiet", "what stage is <name> at", "show me the property pipeline", or types /para-pipeline [<lifecycle>].
allowed-tools: Bash, PowerShell, Glob, Grep, Read
arg-hint: '[<lifecycle>] [--test]'
---

# Para pipeline

The board for **staged entities**: every lifecycle the vault declares, each entity at its stage, the next step and its date, what has stopped moving, and what the quarter did. It answers "where does this stand and what moves next", which no action list answers, because a stage is a fact about the outside world rather than a task.

**Read-only contract.** This skill never edits a file. It reports; the operator moves the entity. A stage change, a reason line, a `Last touch` update are all hand edits, and a flag here is what prompts one.

**This skill is vault-agnostic.** It knows nothing about deals, properties or applications: only about declared lifecycles and Stage lines, whose contract is [para-shared/lifecycles.md](../para-shared/lifecycles.md). No stage name or home is hardcoded; the fields the next-step rules and the metrics read are the ones lifecycles.md names, and `Signer` is the only one whose value fires a flag.

**Operator-language output.** Every line is readable by someone who has not seen this skill: the vault's own entity and stage names, no bucket jargon beyond the section titles.

## Arguments

| Arg | Renders |
|---|---|
| *(none)* | Every declared lifecycle in turn: board, flags, counts, metrics, one closing next action |
| `<lifecycle>` | One lifecycle, matched on its heading noun (`deal`) or its heading text (`Deal lifecycle`), case-insensitively. Everything else is the same |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

**A leftover argument is a lifecycle name only when it reads like one**: one or two words carrying no sentence punctuation. Anything longer is prose the operator wrapped around the invocation: where it names a lifecycle noun ("the property pipeline"), that noun is the argument; otherwise take every lifecycle and treat the prose as an instruction for this run. A name matching no declared lifecycle is asked about, never silently widened to all of them.

## Procedure

### Step 1: Read the declarations

Resolve the vault root, then verify it - the path the operator named, or `pwd` read before anything else in the session has moved the shell. A root has `projects/` plus at least one of `areas/` `archive/`, and a `CLAUDE.md`. If it is not one, stop and say so, naming the path you actually checked.

Read the vault's `CLAUDE.md` and collect every section whose heading ends in `lifecycle`, parsing each table by [para-shared/lifecycles.md](../para-shared/lifecycles.md). Also read the rule file each lifecycle's entity documents load, which is what names their header fields.

**A vault that declares none has nothing to render.** Say so in one line, name the two places a lifecycle comes from (a flavor, a module), and stop. Never infer stages from folder names.

### Steps 2 and 3: Scan the homes, resolve each entity

One call per lifecycle scope, after Step 1 has the declared lifecycles, per [para-shared/scripts.md](../para-shared/scripts.md):

```bash
python3 "<this skill's base directory>/scripts/pipeline_scan.py" --vault . [--lifecycle <name>] [--today YYYY-MM-DD] > <scan output path>
```

Pass `--lifecycle` only under a lifecycle scope. Exit 3 is a `--lifecycle` matching no declared heading or noun (`{"error": "no such lifecycle", "declared": [...]}`): ask which of the declared ones was meant, never guess. Where the script cannot run, fall back to [references/scan.md](references/scan.md).

The rest of Steps 2 and 3 read its output: one record per entity, already at its matched stage with days in stage, its next step and every flag input computed. **Full field table: [references/scan.md](references/scan.md).**

### Step 4: Render

Word what the script computed into the board by stage, the flags, the counts, the per-lifecycle metrics and the single next action that closes the run - no new reading. **Full spec: [references/render.md](references/render.md).**

## Strict rules

- **Never edit a vault file.** Not a stage, not a `Last touch`, not a missing reason line, not a checkbox. Every flag names what the operator should change, and this skill changes none of it.
- **Never invent a stage, a date or a next step.** An entity with no `since` has an unknown time in stage and says so; an entity with no next step is flagged, never given one.
- **Never rank, score or weight an entity.** The board is ordered by the vault's own stage order, then by days in stage. No probability, no forecast, no weighted value: a pipeline of a dozen entities is read, not modelled.
- **Never follow a link for extra context** beyond the next-step sources in [references/scan.md](references/scan.md) Step 3.
- **Never report an archived entity as live.** A terminal stage feeds the metrics and the reason it records, nothing else.
- **Never widen the scan past the declared homes.** An entity carrying a Stage line outside them is not in the lifecycle, and a stage text matching no declared name is passed over silently.
- **A value figure is internal.** It renders in the terminal, never into a file, and never into anything shared outside the vault.

## Edge cases

- **A vault with two lifecycles**: render both, each with its own board, counts and metrics, in the order their sections appear in `CLAUDE.md`. Never merge them.
- **A declared home that does not exist yet** (the register file, an `archive/` folder): count it as empty and say so once, rather than reporting an error per stage.
- **An entity whose folder sits in the wrong home for its stage**: render it under the stage its Stage line names and flag the mismatch, naming both paths. The Stage line is the entity's own claim; the folder is where someone last left it.
- **Two entities with the same name** in different homes: render both, each with its path, and flag the collision.
- **A document in a declared home with no Stage line at all** (`no_stage`): list it by path under a closing line, but only where it carries a header field a staged entity would, or its home sits deeper than a PARA bucket's direct child - otherwise it is an ordinary project or area sharing the home, not a filing gap.
- **A register row missing a column** the table declares: render what it has, and flag the row rather than dropping it.
- **A lifecycle with no live entity at all**: render its counts as zeros and its metrics, and say in one line that nothing is live. An empty pipeline is a real answer.
- **The vault is on the read-only iPad delivery**: resolve every path through the [collected-state path map](../para-shared/operating-discipline.md#the-read-only-ipad-delivery), and read dates from the collected `.md`. Nothing here edits a file, so no edit cycle runs.

## Related skills

- `/para-daily-brief` - the same read-only contract over the vault's tasks. It carries one counts line per lifecycle and points here for the board.
- `/para-new` - creates a staged entity at the first stage's home, with its Stage line.
- `/para-archive` - the move into a terminal stage, which it refuses unless the Stage line and the reason are there.
