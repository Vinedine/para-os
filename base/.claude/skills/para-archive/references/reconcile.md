# Reconcile, validate, route (Steps 2 to 5)

`scripts/archive_scan.py`'s plan call implements every mechanical rule below and `scripts/test_archive_scan.py` pins each one to a case. Read this file when a result looks wrong, when changing what a rule means, or when running the scan by hand per Step 0.

Everything that has to be settled before anything moves. Each step ends with a proposal and waits for approval.

## Step 2 - Reconcile open actions

Read the entity's `actions.md` (and any per-file action markers). Split into **done** vs **open**, where open is every unchecked checkbox and every `## Backlog` item with no stated disposition. A Backlog item already carrying a Done, Decided or Resolved line is settled: list it in the closed record, never ask about it. **`actions.done` and `.open` carry the checkboxes; `actions.backlog` carries every Backlog item, each with `settled` and `by` already computed** - a top-level non-checkbox bullet with its continuation lines, or a paragraph of prose outside any bullet, under the heading and any subheading of it.

**The settled match is a capitalised `Done`, `Decided` or `Resolved` as a whole word, case-sensitive.**

**A checkbox inside a fenced code block is not an open action**, per **A quoted syntax is not a used syntax** in [operating-discipline.md](../../para-shared/operating-discipline.md): a brief or plan illustrating what an `actions.md` looks like must not block an archive or be reconciled item by item. The script's own task and Backlog readers already skip fence content.

**`actions.other_checkbox_files` names every other file in the entity folder still holding open checkboxes** (a stray plan or log, each with its count and whether it sits under a `sources/` folder), the reconciliation the vault's own "no open actions" archive-hygiene rule expects beyond `actions.md` itself.

**Skip this step for ideas.** An idea carries no `actions.md` by the vault's own rule (`resources/` never holds a checkbox), so there is nothing to reconcile and no routing question to ask; its open questions retire with it. **`actions.idea_holds_actions`** flags the filing error where one exists anyway.

- If everything is done: note it, proceed.
- For each **open** action, **one question**, per [../../para-shared/asking.md](../../para-shared/asking.md), which also sets when the manifest prints. The standard dispositions:
  - **Done already** - mark complete (the live state moved past the file).
  - **Survives** - the work continues. Where to? Step 4's routing.
  - **Drop** - no longer relevant; record as dropped, don't silently delete the intent.
  - A **recurring** item is never done: it survives into the recurring section of the area that takes the work over, or is dropped.
  - A resolved `## Backlog` item stays in the closed record as a prose line stating its disposition and reason, with no date stamp.

**Where the destination is obvious, collapse Steps 2 and 4 into that one question** by offering it concretely: `Route to areas/business/actions.md` beats `Survives` followed by a second question the operator has already answered in their head. Name the actual file. Fall back to the two-stage form only where the skill genuinely cannot tell.

**`Drop` is destructive and gets the destructive treatment**, and its option description says what the record will read afterwards, since a dropped item leaves a line saying it was dropped rather than nothing at all. Where the skill is guessing that something is `Done already`, recommend what the evidence supports: a closed checkbox keeps its text and its reason, so it is reversible.

Never invent dates or completion stamps. Use the vault's marker syntax for any edits. Do not archive an entity with unresolved open actions still framed as live work.

## Step 3 - Validate brief and actions files

- **brief.md** (or the README the vault's shape gives the entity): must exist and read as a coherent record of what the entity *was* (for a project: outcome, what shipped, key decisions; for an idea: what the concept was and why it's being shelved - superseded, no traction, decided against; for an area: what it held and why it ended). If missing, offer to reconstruct a short historical brief from the actions.md plus any artifacts in the folder, stating clearly it's a post-hoc reconstruction and inventing nothing. If present but stale (still written as live or future work), offer to retense it to a closed record.
- **actions.md**: should end as a clean closed record - completed items, plus a forward pointer to wherever surviving work went. No open `[ ]` item or unresolved `## Backlog` prose left in an archived file.
- Respect "do not add" rules (some vaults forbid `actions.md` in certain trees).

**A staged entity carries one more check, and it is a gate rather than an offer**, where it is in a declared lifecycle ([para-shared/lifecycles.md](../../para-shared/lifecycles.md)) and the destination is a terminal stage's home. **`lifecycle` is null unless the Stage line names a stage of a declared table**; where it is not, `destination_matches` names which terminal stage (if any) the destination equals, and `reason` carries both parts of the gate below together:

- **The Stage line must name that terminal stage.** A brief still reading `**Stage:** Proposal` is an entity whose operator has not yet said it is over. Show the line as it stands and the line it would become, and stop until the operator writes it. Never edit the stage yourself. **`lifecycle.stage_line_names_destination`** is this check, already run.
- **Where the rule file requires a reason line for that stage**, it must be present and non-empty, with a value from whatever list that file gives. **`lifecycle.reason`** carries the field name, its `raw` value and `key` (the text before its first comma), and the `allowed` list parsed from the vault's own `.claude/rules/*.md` prose (the bold values following "one of" in the paragraph that states the field) - `allowed: null` means no rule file declares one, so read it yourself.
- **Both missing is one stop, not two.** Name them together, with the exact lines to add and where they go, so the operator writes both and reruns once.

## Step 4 - Route surviving actions and living-reference files

**Surviving actions** (from Step 2): ask each time where they go - do not assume a v2. Options to offer:

- A **new successor idea** at `resources/ideas/<name>-vNext/` (scaffold `brief.md` **only**, cross-linked to the archived original) - use only if the user chooses it.
- An **existing project**, or an **area's rolling actions**.
- A **contact file**, for anything that is really a follow-up with one person.
- **Drop**.

**A successor idea never gets an `actions.md`** (the vault's "Where a checkbox may live" rule). Fold what survives into its `brief.md` as open questions and prose next steps. A genuinely dated commitment is not idea material: route it to the owning area's `actions.md`, an existing project, or the contact file.

**Living-reference files**: scan the entity folder for files whose *content* is reusable reference rather than history - playbooks, positioning or strategy docs, templates, anything linked by other live work as a resource. Propose moving them to `resources/<name>/`. The entity's history (brief, actions, one-time migration or handoff plans) archives with it. **`inbound.living_reference_candidates`** lists every file inside the entity folder that a live file outside it already links to, each with the files linking to it - candidates to judge, never a verdict: the script does not know which are history and which are reference.

**Stale source snapshots**: flag any in-folder copy superseded by a canonical live source - keeping a dead copy invites edits to the wrong source. Surface for deletion (compare contents plus individual approval, per the operating discipline).

## Step 5 - Decide the version suffix (projects only)

**Skip this step entirely for ideas and areas.** They archive under their own name, with no `-v1` / `-vN` suffix.

For **projects**, ask whether the archived folder should carry a version suffix (`<name>-v1`). One question, two options, the recommendation first with its reason in the description. **`destination.suffix_siblings`** names the existing `<name>-vN` folders already in the destination's parent and **`.next_suffix`** the lowest free one. Recommend one when **either**:

- A successor (a `-v2` idea, or a planned rebuild) exists or was just created in Step 4, so the pair reads as `v1` shipped / `v2` still a concept, **or**
- The project is likely to recur (websites, decks, seasonal work).

Recommend **no suffix** for one-off projects with no expected successor. Let the user override either way. Apply the chosen name to the archive destination.

## Edge cases

- **No brief.md**: offer a post-hoc reconstruction from actions plus artifacts; mark it clearly as reconstructed.
- **Open actions belong to another owner** (a contact, an area): route them there rather than into a successor idea.
- **No successor wanted but actions survive**: route to an area's rolling actions or an existing project; only scaffold an idea if the user asks.
- **Vault has no `actions.md`** (action tracking excluded by convention, as in read-only consumer vaults): there is nothing to reconcile in Step 2 - **`actions.file: null`** is the script's own signal for this case, and it still reports `backlog` from `brief.md` alone. Fall back to the vault's prose convention - read the entity's `brief.md` / `README.md` for next steps written as prose, resolve those with the user the same way (done / survives / drop), and record survivors as prose in the destination rather than as markers. Do not create an `actions.md` to do this.
