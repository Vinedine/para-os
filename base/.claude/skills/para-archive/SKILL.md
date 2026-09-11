---
name: para-archive
description: Archive a finished project or a retired idea end-to-end - reconcile its open actions, validate its brief/actions files, optionally version-suffix it (projects only), route living-reference files to resources/, then move it to archive/ and repoint every inbound link in the vault. Use when a project has shipped or an idea is being shelved and the user asks to "archive this", "close out <name>", "wrap up <name>", "shelve <idea>", or types /para-archive <name>.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write, AskUserQuestion
arg-hint: '<name> [preview|table]'
---

# Para archive

Performs the full lifecycle transition for **one finished project or one retired idea**, leaving no dangling links behind:

- A **project** moves from `projects/<name>/` (active) to `archive/projects/<name>/` (closed).
- An **idea** moves from `resources/ideas/<name>/` (concept-stage) to `archive/ideas/<name>/` (shelved).

Both follow the same flow. The only difference is the source and destination bucket, and the **version-suffix step, which applies to projects only**. Deep-clean finds archivable entities during a sweep; this skill executes the one move thoroughly.

**This skill is vault-agnostic.** It reads the vault's CLAUDE.md at runtime for the PARA layout, the **Archive hygiene** conventions, the action-marker syntax, the naming convention, and any "do not add" rules. No vault-specific paths are hardcoded.

Do NOT invoke to archive areas or contacts - this skill handles projects and ideas only. Do NOT invoke mid-project to "tidy up": archiving a project means the deliverable is complete, and archiving an idea means the concept is being shelved, not that it's mid-exploration.

## Arguments

**The entity name is the part of the argument that reads like one, not the whole string.** An invocation collects operator prose around it ("on project acme-website using the 2026.09.02 branch, and flag any bugs you hit"): take the one to three words that could name a folder, or a `projects/<name>` / `resources/ideas/<name>` path, drop a leading `project`, `idea` or `on`, and treat everything else as an instruction for this run rather than as part of the name. Resolve what is left by Step 1's rules. Never match the whole sentence against a folder, and never stop to ask which entity a trailing sentence names: ask only where the extracted name genuinely matches none or several.

| Arg | Behavior |
|---|---|
| `<name>` | Full flow: reconcile, validate, version (projects only), route refs, move, repoint links, report. Pauses for approval at each decision. |
| `<name> preview` | Run the analysis (open actions, file validation, inbound-link scan) and show the plan - the manifest of questions a live run would ask, then the proposal - but make NO changes. |
| `<name> table` | The batch proposal flow: one markdown proposal table, one `go`, then execute. The explicit escape from item-by-item questions that [para-shared/asking.md](../para-shared/asking.md) requires every asking skill to name, for an operator who would rather read the batch than click through it. |

## Procedure

Each step that changes files ends with a proposal and waits for explicit approval. Never auto-advance through a destructive step (move, delete, link rewrite) without showing what will change. **Per-item decisions are asked one at a time** - every open action's disposition, and the version suffix - through `AskUserQuestion`, per [para-shared/asking.md](../para-shared/asking.md); the link repoints and the moves themselves stay a single batched proposal, since they are one mechanical consequence of decisions already made.

### Step 1 - Confirm context and locate the entity

1. **Resolve the vault root, then verify it** - the path the operator named, or `pwd` read before anything else in the session has moved the shell, never the current directory taken on trust (`operating-discipline.md`). A root has `projects/` plus at least one of `areas/` `archive/`, and a `CLAUDE.md`. If it is not one, stop and say so, naming the path you actually checked.
2. Read the vault's `CLAUDE.md` for: PARA layout, action-marker syntax, naming convention, the ideas-vs-projects bar, the archive subfolder layout (`archive/projects/`, `archive/ideas/`, `archive/meetings/`), and "do not add" rules.
3. **Determine whether `<name>` is a project or an idea:**
   - `projects/<name>/` exists: it's a **project**; source = `projects/<name>/`, destination = `archive/projects/<name>[-vN]/`.
   - `resources/ideas/<name>/` exists: it's an **idea**; source = `resources/ideas/<name>/`, destination = `archive/ideas/<name>/`.
   - If both exist, ask which one. If neither exists, list the `projects/` and `resources/ideas/` folders and ask which one.
   - Carry this **kind** through the rest of the flow - it selects the buckets and whether the versioning step runs.
4. **Confirm the entity is actually done, and keep that question two-way.** A project's deliverable is shipped (don't archive live work), or an idea is genuinely being shelved (don't archive an idea still under active exploration). Where the vault's own record disagrees - an open dated action, a brief saying it archives after some event still ahead - say so in one line and put it to the operator as **proceed or stop**, nothing else. It is the one question in the run whose answer is a fact about their situation rather than a disposition, so it carries no recommendation (`asking.md`). **Never offer a blanket disposition for what is still open.** A "drop what's left" option at the gate approves every destructive item in the run on a single click, which is the batching `asking.md` exists to forbid; what happens to each open item is Step 2's question, asked one at a time, once the gate says proceed.

### Steps 2 to 5 - Reconcile, validate, route, version

Split the actions into done and open and get a disposition for each open one; validate that `brief.md` and `actions.md` read as a closed record; route surviving actions and living-reference files out; then decide the version suffix (projects only). **Full procedure: [references/reconcile.md](references/reconcile.md).**

### Steps 6 to 8 - Scan links, execute, verify

Grep the whole vault for inbound references and classify each before anything moves; execute the moves with `git mv`, re-depthing the relative links *inside* whatever moved; then re-run the grep and resolve the outbound links, asserting zero dangling references in either direction. **Full procedure: [references/move.md](references/move.md).**

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Zero dangling links is the bar, in both directions.** Inbound references and the links written *from* inside the entity are two different scans; leaving either broken is a failed run, and the reconciliation (Steps 6 to 8) is not optional.
- **Ask, don't assume, for surviving actions,** one question per action and never a list approved at once. Don't auto-scaffold a successor; the user may want the work in an existing project, an area, or dropped.
- **Don't archive live work.** If a project's open actions are still genuinely live (not routable out), the project isn't done - stop and say so rather than burying live work. Likewise, don't archive an idea that's still under active exploration.
- **Version logic is for projects only.** Never apply a `-vN` suffix to an idea; ideas archive under their own name in `archive/ideas/`.

Archive-hygiene rules - no open actions, living-refs to resources, minimum record, zero dangling links - come from the **Archive hygiene** conventions in CLAUDE.md, whether that's the vault's own file or an inherited global one.

## Edge cases

- **Idea is actually being promoted, not shelved**: if the "archive" request is really "this idea became a project", that's a promotion (`resources/ideas/<name>/` to `projects/<name>/`), not an archive. Clarify, then hand off to `/para-new promote <name>` - this skill archives, it doesn't promote.

Step-specific edge cases (missing brief, collisions, partly-archived entities, vaults with no `actions.md`) live with their steps.

## Related skills

- `/para-new` - the other end of the lifecycle, and where the idea-to-project promotion this skill refuses is actually run.
- `/para-deep-clean` - its Phase 1 *flags* archive-vs-active misclassification; this skill *executes* one archival. Deep-clean to find candidates, here to close each.
