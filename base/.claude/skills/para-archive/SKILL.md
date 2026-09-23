---
name: para-archive
description: Archive a finished project, a retired idea, or an area the vault names an archive destination for, end-to-end - reconcile its open actions, validate its brief/actions files, optionally version-suffix it (projects only), route living-reference files to resources/, then move it to archive/ and repoint every inbound link in the vault. Use when a project has shipped or an idea is being shelved and the user asks to "archive this", "close out <name>", "wrap up <name>", "shelve <idea>", or types /para-archive <name>.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write, AskUserQuestion
arg-hint: '<name> [preview|table] [--test]'
---

# Para archive

Performs the full lifecycle transition for **one finished project, retired idea, or ended area**, leaving no dangling links behind:

- A **project** moves from `projects/<name>/` (active) to `archive/projects/<name>/` (closed).
- An **idea** moves from `resources/ideas/<name>/` (concept-stage) to `archive/ideas/<name>/` (shelved).
- Where the vault's `CLAUDE.md` names another archive destination for the entity's kind, it goes there instead, and an **area** archives only where such a destination is named for its kind.

All follow the same flow. The only difference is the source and destination, and the **version-suffix step, which applies to projects only**. Deep-clean finds archivable entities during a sweep; this skill executes the one move thoroughly.

**This skill is vault-agnostic.** It reads the vault's CLAUDE.md at runtime for the PARA layout, the **Archive hygiene** conventions, the action-marker syntax, the naming convention, and any "do not add" rules. No vault-specific paths are hardcoded.

Do NOT invoke to archive contacts, or an area the vault names no archive destination for. Do NOT invoke mid-project to "tidy up": archiving a project means the deliverable is complete, and archiving an idea means the concept is being shelved, not that it's mid-exploration.

## Arguments

**The entity name is the part of the argument that reads like one, not the whole string.** An invocation collects operator prose around it ("on project acme-website using the 2026.09.02 branch, and flag any bugs you hit"): take the one to three words that could name a folder, or a `projects/<name>` / `resources/ideas/<name>` path, drop a leading `project`, `idea` or `on`, and treat everything else as an instruction for this run rather than as part of the name. Resolve what is left by Step 1's rules. Never match the whole sentence against a folder, and never stop to ask which entity a trailing sentence names: ask only where the extracted name genuinely matches none or several.

| Arg | Behavior |
|---|---|
| `<name>` | Full flow: reconcile, validate, version (projects only), route refs, move, repoint links, report. Pauses for approval at each decision. |
| `<name> preview` | Run the analysis (open actions, file validation, inbound-link scan) and show the plan - the manifest of questions a live run would ask, then the proposal - but make NO changes. |
| `<name> table` | The batch proposal flow: one markdown proposal table, one `go`, then execute. The explicit escape from item-by-item questions that [para-shared/asking.md](../para-shared/asking.md) requires every asking skill to name, for an operator who would rather read the batch than click through it. |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## Procedure

Each step that changes files ends with a proposal and waits for explicit approval. Never auto-advance through a destructive step (move, delete, link rewrite) without showing what will change. **Per-item decisions are asked one at a time** - every open action's disposition, and the version suffix - through `AskUserQuestion`, per [para-shared/asking.md](../para-shared/asking.md); the link repoints and the moves themselves stay a single batched proposal, since they are one mechanical consequence of decisions already made.

### Step 0 - Scan

Run the plan call per [para-shared/scripts.md](../para-shared/scripts.md); it answers everything Steps 1 to 6 read, and Step 8's verify call is in [references/move.md](references/move.md):

```bash
python3 "<this skill's base directory>/scripts/archive_scan.py" --vault . --entity <name> [--destination <path>] [--today YYYY-MM-DD] [--route <file>]... > <scan output path>
```

**Exit codes**: 0 answered, an unresolved or ambiguous entity included; 2 fall back to [references/reconcile.md](references/reconcile.md) and [references/move.md](references/move.md); 3 `--vault` is not a vault root (Step 1's stop).

### Step 1 - Confirm context and locate the entity

1. **The vault root is Step 0's `vault` block** - the path the operator named, or `pwd` read before anything else in the session has moved the shell, never the current directory taken on trust (`operating-discipline.md`). Where `root` is false, stop and say so, naming the path checked and, where `hint` names one, which registered vault actually holds it.
2. Read the vault's `CLAUDE.md` for: PARA layout, action-marker syntax, naming convention, the ideas-vs-projects bar, the archive subfolder layout (`archive/projects/`, `archive/ideas/`, `archive/meetings/`), any archive destination it names for a kind of entity, and "do not add" rules.
3. **`entity` and `destination` carry Step 1's resolution.** `entity.status` is `resolved` (kind and source given), `ambiguous` (ask which of `candidates`), `elsewhere` (already archived, in this same vault, at `already_archived`), or `unresolved` (nothing in this vault matches: list `this_vault`'s own folders and, from `other_vaults`, which other registered vault holds a folder of that name; ask which one, or which vault). A session that started in another vault resolves that vault's root; never run against the other vault until the operator names it. `destination.path` is the default for a project or idea; for an **area**, `needs_vault_rule: true` means the vault names no default - read its own named destination for the entity's kind and re-run with `--destination`. **An entity in a declared lifecycle archives into a stage**, not merely into a folder: `lifecycle` (null unless the Stage line names a stage of a declared table) gives every terminal stage's home made concrete for this entity, which one (if any) `destination` matches, whether the Stage line already names it, and the reason-gate's raw material - Step 3 in [references/reconcile.md](references/reconcile.md) is the gate itself, [para-shared/lifecycles.md](../para-shared/lifecycles.md) the contract behind it.
   Carry this **kind** through the rest of the flow - it selects the source, the destination and whether the versioning step runs.
4. **Confirm the entity is actually done, and keep that question two-way.** A project's deliverable is shipped (don't archive live work), or an idea is genuinely being shelved (don't archive an idea still under active exploration). Where `gate` disagrees - an open dated action in `open_dated`, a `future_dated_lines` entry still ahead - say so in one line and put it to the operator as **proceed or stop**, nothing else. A date sitting only in a link's own target (a filed meeting note's dated filename, an archive path) is never a `future_dated_lines` entry; the link's display text and plain prose still are. The gate reads live work only: `status_line` alone is never the evidence, since Step 3's retense exists to fix that line. It is the one question in the run whose answer is a fact about their situation rather than a disposition, so it carries no recommendation (`asking.md`). **Never offer a blanket disposition for what is still open.** A "drop what's left" option at the gate approves every destructive item in the run on a single click, which is the batching `asking.md` exists to forbid; what happens to each open item is Step 2's question, asked one at a time, once the gate says proceed.

### Steps 2 to 5 - Reconcile, validate, route, version

Split the actions into done and open and get a disposition for each open one; validate that `brief.md` and `actions.md` read as a closed record; route surviving actions and living-reference files out; then decide the version suffix (projects only), reading `destination.suffix_siblings` and `.next_suffix`. **Full procedure: [references/reconcile.md](references/reconcile.md).**

### Steps 6 to 8 - Scan links, execute, verify

Classify `inbound`'s references before anything moves, re-running the plan call with `--route` once Step 4 has decided what routes to `resources/`; execute the moves with `git mv`, rewriting the relative links *inside* whatever moved per `move_plan`; **re-check the snapshot** immediately before Step 7 writes anything; then run the verify call and resolve every count it reports, asserting zero dangling references in either direction. **Full procedure: [references/move.md](references/move.md).**

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Zero dangling links is the bar, in both directions.** Inbound references and the links written *from* inside the entity are two different scans; leaving either broken is a failed run, and the reconciliation (Steps 6 to 8) is not optional.
- **Ask, don't assume, for surviving actions,** one question per action and never a list approved at once. Don't auto-scaffold a successor; the user may want the work in an existing project, an area, or dropped.
- **Don't archive live work.** If a project's open actions are still genuinely live (not routable out), the project isn't done - stop and say so rather than burying live work. Likewise, don't archive an idea that's still under active exploration.
- **Version logic is for projects only.** Never apply a `-vN` suffix to an idea or an area; they archive under their own name.
- **Never move a staged entity into a terminal stage on your own.** The Stage line and the reason its rule file requires are the operator's words, written before the move. `lifecycle.reason` names the field, its current value and key, and the `allowed` list (or `null`, meaning read the rule file yourself); offer the exact lines; refuse the run until they are there.

Archive-hygiene rules - no open actions, living-refs to resources, minimum record, zero dangling links - come from the **Archive hygiene** conventions in CLAUDE.md, whether that's the vault's own file or an inherited global one.

## Edge cases

- **Idea is actually being promoted, not shelved**: if the "archive" request is really "this idea became a project", that's a promotion (`resources/ideas/<name>/` to `projects/<name>/`), not an archive. Clarify, then hand off to `/para-new promote <name>` - this skill archives, it doesn't promote.

Step-specific edge cases (missing brief, collisions, partly-archived entities, vaults with no `actions.md`) live with their steps.

## Related skills

- `/para-new` - the other end of the lifecycle, and where the idea-to-project promotion this skill refuses is actually run.
- `/para-deep-clean` - its Phase 1 *flags* archive-vs-active misclassification; this skill *executes* one archival. Deep-clean to find candidates, here to close each.
