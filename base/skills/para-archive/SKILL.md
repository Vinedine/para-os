---
name: para-archive
description: Archive a finished project or a retired idea end-to-end - reconcile its open actions, validate its brief/actions files, optionally version-suffix it (projects only), route living-reference files to resources/, then move it to archive/ and repoint every inbound link in the vault. Use when a project has shipped or an idea is being shelved and the user asks to "archive this", "close out <name>", "wrap up <name>", "shelve <idea>", or types /para-archive <name>.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write
arg-hint: '<name> [preview]'
---

# Para archive

Performs the full lifecycle transition for **one finished project or one retired idea**, leaving no dangling links behind:

- A **project** moves from `projects/<name>/` (active) to `archive/projects/<name>/` (closed).
- An **idea** moves from `resources/ideas/<name>/` (concept-stage) to `archive/ideas/<name>/` (shelved).

Both follow the same flow. The only difference is the source/destination bucket and the **version-suffix step, which applies to projects only** - ideas are archived under their own name with no `-v1` logic. This is the on-demand counterpart to `/para-deep-clean`, which only *flags* entities that look archivable during a vault-wide sweep. Deep-clean finds; this skill executes the one move thoroughly.

**This skill is vault-agnostic.** It reads the vault's CLAUDE.md at runtime to discover the PARA layout, the **Archive hygiene** conventions (the contract for what a clean archive looks like), the action-marker syntax, the naming convention, the ideas-vs-projects bar, and any "do not add" rules. It follows the shared [operating-discipline.md](../shared/operating-discipline.md) for approval/deletion/preservation rules. No vault-specific paths are hardcoded.

## When to invoke

- User types `/para-archive <name>` (optionally `preview` to stop before any change)
- User says "archive <name>", "close out <name>", "wrap up <name>", "<name> shipped, file it away" (a project)
- User says "shelve <idea>", "archive this idea", "park <idea>", "<idea> is going nowhere, file it" (an idea)
- A project's committed deliverable is done and it no longer belongs in `projects/`
- An idea has been abandoned, superseded, or has had no traction long enough that it should leave `resources/ideas/`

Do NOT invoke to archive areas or contacts - this skill handles projects and ideas. Do NOT invoke mid-project to "tidy up"; archiving a project means the time-bound deliverable is complete. Archiving an idea means the concept is being shelved, not that it's mid-exploration.

## Arguments

| Arg | Behavior |
|---|---|
| `<name>` | Full flow: reconcile → validate → version (projects only) → route refs → move → repoint links → report. Pauses for approval at each decision. |
| `<name> preview` | Run the analysis (open actions, file validation, inbound-link scan) and show the plan, but make NO changes. |

## Procedure

Each step that changes files ends with a proposal and waits for explicit approval. Never auto-advance through a destructive step (move, delete, link rewrite) without showing what will change.

### Step 1 - Confirm context and locate the entity

1. Verify the cwd is a vault root (has `projects/` + at least one of `areas/` `archive/`, and a `CLAUDE.md`). If not, stop and say so.
2. Read the vault's `CLAUDE.md` for: PARA layout, action-marker syntax, naming convention, the ideas-vs-projects bar, the archive subfolder layout (`archive/projects/`, `archive/ideas/`, `archive/meetings/`, etc.), and "do not add" rules.
3. **Determine whether `<name>` is a project or an idea:**
   - Look for `projects/<name>/` → it's a **project**; source = `projects/<name>/`, destination = `archive/projects/<name>[-vN]/`.
   - Look for `resources/ideas/<name>/` → it's an **idea**; source = `resources/ideas/<name>/`, destination = `archive/ideas/<name>/`.
   - If both exist, ask which one. If neither exists, list the `projects/` and `resources/ideas/` folders and ask which one.
   - Carry this **kind** (project vs idea) through the rest of the flow - it selects the source/destination bucket and whether Step 5 (versioning) runs.
4. Confirm with the user in one line that the entity is actually done: a project's deliverable is shipped (don't archive live work), or an idea is genuinely being shelved (don't archive an idea still under active exploration).

### Step 2 - Reconcile open actions

Read the entity's `actions.md` (and any per-file action markers). Split into **done** vs **open**.

- If everything is done: note it, proceed.
- For each **open** action, present it and ask what happens. Offer the standard dispositions:
  - **Done already** - mark complete (the live state moved past the file).
  - **Survives** - the work continues. Where to? Ask, per Step 4's routing - a new version idea, an existing project, an area's rolling actions, or a contact file.
  - **Drop** - no longer relevant; record as dropped, don't silently delete the intent.

Never invent dates or completion stamps. Use the vault's marker syntax for any edits. Do not archive an entity with unresolved open actions still framed as live work - that's how a "closed" project or a shelved idea keeps haunting `/para-daily-brief`.

### Step 3 - Validate brief + actions files

- **brief.md**: must exist and read as a coherent record of what the entity *was* (for a project: outcome, what shipped, key decisions; for an idea: what the concept was and why it's being shelved - superseded, no traction, decided against). If missing, offer to reconstruct a short historical brief from the actions.md + any artifacts in the folder (state clearly it's a post-hoc reconstruction; invent nothing). If present but stale (still written as live/future work), offer to retense it to a closed record.
- **actions.md**: should end as a clean closed record - completed items, plus a forward pointer to wherever surviving work went. No open `[ ]` items left dangling in an archived file.
- Respect "do not add" rules (e.g. some vaults forbid `actions.md` in certain trees).

### Step 4 - Route surviving actions and living-reference files

**Surviving actions** (from Step 2): ask each time where they go - do not assume a v2. Options to offer:
- A **new successor idea** at `resources/ideas/<name>-vNext/` (scaffold `brief.md` + `actions.md`, cross-linked to the archived original) - use only if the user chooses it.
- An **existing project** or an **area's rolling actions**.
- **Drop**.

**Living-reference files**: per the Archive hygiene contract (history archives, living references go to `resources/`), scan the entity folder for files whose *content* is reusable reference rather than history - playbooks, positioning/strategy docs, templates, anything self-describing as "keep current"/"reusable"/"template" or linked by other live work as a resource. Propose moving them to `resources/<name>/`. The entity's *history* (brief, actions, one-time migration/handoff plans) stays and gets archived.

**Stale source snapshots**: flag any in-folder copy superseded by a canonical live source (a `starter/` snapshot now owned by a public repo; a vendored copy of files that live authoritatively elsewhere) - keeping a dead copy invites edits to the wrong source. Surface for deletion (compare contents + individual approval, per the operating discipline).

### Step 5 - Decide the version suffix (projects only)

**Skip this step entirely for ideas.** Ideas are archived under their own name at `archive/ideas/<name>/`, with no `-v1`/`-vN` suffix - they were never a versioned deliverable, so the version pairing doesn't apply.

For **projects**, ask whether the archived folder should carry a version suffix (`<name>-v1`, etc.). Recommend one when **either**:
- A successor (`-v2` idea, or a planned rebuild) exists or was just created in Step 4, so the pair reads as `v1` shipped / `v2` backlog, **or**
- The project is likely to recur (websites, decks, seasonal work).

Recommend **no suffix** for one-off projects with no expected successor. Let the user override either way. Apply the chosen name to the archive destination.

### Step 6 - Scan inbound links (the part that breaks silently)

Before moving anything, grep the **entire vault** for references to the entity's current path and to files moving out of it. Use the source bucket from Step 1 (`projects/<name>/` for a project, `resources/ideas/<name>/` for an idea):

```bash
# from vault root - find every inbound reference (project example)
grep -rn "projects/<name>/" --include="*.md" .
grep -rn "<name>" --include="*.md" . | grep -E "\]\(|\.md"   # catch relative links by filename
```

```bash
# idea example
grep -rn "resources/ideas/<name>/" --include="*.md" .
```

Build an **inbound-link table**: every file + line that points at the entity, its brief, its actions, or any file being routed to `resources/`. Classify each:
- → repoint to the **archive** path (`archive/projects/<name>[-v1]/...` for a project, `archive/ideas/<name>/...` for an idea)
- → repoint to the **successor** (`resources/ideas/<name>-vNext/...`) when it referenced live/forward work (e.g. an `actions.md` link tracking remaining work)
- → repoint to the **resources** home (for routed living-reference files)
- → repoint to a **live external source** (e.g. a shipped URL, a public repo) when that's the truer target than a dead vault path
- → leave as-is

Note: some of these links may **already be broken** from earlier moves - fix them in the same pass.

### Step 7 - Execute

In order, with `git mv` / `git rm` so history is preserved (fall back to plain `mv`/`rm` if not a git repo):

1. Move living-reference files to `resources/<name>/`.
2. Delete approved stale snapshots.
3. Create the successor scaffold if chosen.
4. Retense/clean brief.md and actions.md to their archived form.
5. Move the entity to its archive bucket: `projects/<name>/` → `archive/projects/<name>[-v1]/`, or `resources/ideas/<name>/` → `archive/ideas/<name>/`. Create the destination parent (`archive/ideas/`) if it doesn't exist yet.
6. Apply every approved link repoint from the Step 6 table.
7. **Windows note**: an empty source directory can linger ("device or resource busy") if the IDE or a terminal holds a handle - the files moved fine; `rm -rf` the empty shell and tell the user it was a stale handle, not a failure.

### Step 8 - Verify and report

- Re-run the inbound-link grep. Assert **zero** stale references remain to the old source path (a still-live historical mention inside the archived folder itself - e.g. a migration plan - is acceptable; flag it explicitly).
- Confirm the archived folder contains only history (brief, actions, one-time plans) and the successor (if any) holds the surviving work.
- Report: what was archived (and whether it was a project or an idea), the version decision (projects only), files routed to resources, snapshots deleted, the successor created, and the count of links repointed (with the table).
- Remind the user that nothing is committed (per the no-commit convention) and, if the skill itself or a public repo was touched, that those need their own review.

## Strict rules

Approval, deletion-safety, fact-preservation, no-invented-dates, and no-commit rules are inherited from [shared/operating-discipline.md](../shared/operating-discipline.md). The rules specific to *this* skill:

- **Zero dangling links is the bar.** Archiving that leaves broken inbound references is a failed run - the link reconciliation (Steps 6 + 8) is not optional.
- **Ask, don't assume, for surviving actions.** Don't auto-scaffold a successor; the user may want the work in an existing project, an area, or dropped.
- **Don't archive live work.** If a project's open actions are still genuinely live (not routable out), the project isn't done - stop and say so rather than burying live work. Likewise, don't archive an idea that's still under active exploration.
- **Version logic is for projects only.** Never apply a `-vN` suffix to an idea; ideas archive under their own name in `archive/ideas/`.

(Archive-hygiene rules - no open actions, living-refs-to-resources, minimum record, zero dangling links - come from the **Archive hygiene** conventions in CLAUDE.md, whether that's the vault's own file or an inherited global one.)

## Edge cases

- **No brief.md**: offer a post-hoc reconstruction from actions + artifacts; mark it clearly as reconstructed.
- **Entity already partly archived** (someone moved the folder but left links broken): run Steps 6-8 only - reconcile the links and validate the archived files.
- **Open actions belong to another owner** (a contact, an area): route them there rather than into a successor idea.
- **No successor wanted but actions survive**: route to an area's rolling actions or an existing project; only scaffold an idea if the user asks.
- **Vault has no `actions.md`** (action tracking excluded by convention - e.g. read-only consumer vaults): there's no actions.md to reconcile in Step 2. Fall back to the vault's prose convention - read the entity's `brief.md`/`README.md` for "next steps" written as prose, resolve those with the user the same way (done / survives / drop), and record survivors as prose in the destination rather than as markers. Do not create an `actions.md` to do this (respect the vault's "do not add").
- **Suffix collision** (`<name>-v1` already exists in archive): ask whether this is a further version or a re-archive of the same; never silently overwrite. (Projects only.)
- **Idea name collision** (`archive/ideas/<name>/` already exists): ask whether this re-archives the same idea or is a distinct one needing a disambiguating name; never silently overwrite.
- **Idea is actually being promoted, not shelved**: if the "archive" request is really "this idea became a project", that's a promotion (`resources/ideas/<name>/` → `projects/<name>/`), not an archive. Clarify and stop - this skill archives, it doesn't promote.

## Related skills

Part of the para-os skill set. Siblings:

- `/para-deep-clean` - vault-wide periodic sweep; its Phase 1 *flags* archive-vs-active misclassification (including ideas with no traction). This skill *executes* a single archival thoroughly. Run deep-clean to find candidates, para-archive to close each one.
- `/para-triage` - routes loose inbound files; unrelated to lifecycle but shares the propose-then-approve discipline.
- `/para-daily-brief` - reads open actions; a properly archived project or idea (no dangling open items) stops cluttering its output.
