# Reconcile, validate, route (Steps 2 to 5)

Everything that has to be settled before anything moves. Each step ends with a proposal and waits for approval.

## Step 2 - Reconcile open actions

Read the entity's `actions.md` (and any per-file action markers). Split into **done** vs **open**.

**Skip this step for ideas.** An idea carries no `actions.md` by the vault's own rule (`resources/` never holds a checkbox), so there is nothing to reconcile and no routing question to ask; its open questions retire with it.

- If everything is done: note it, proceed.
- For each **open** action, **one question**, per [../../para-shared/asking.md](../../para-shared/asking.md), which also sets when the manifest prints. The standard dispositions:
  - **Done already** - mark complete (the live state moved past the file).
  - **Survives** - the work continues. Where to? Step 4's routing.
  - **Drop** - no longer relevant; record as dropped, don't silently delete the intent.

**Where the destination is obvious, collapse Steps 2 and 4 into that one question** by offering it concretely: `Route to areas/business/actions.md` beats `Survives` followed by a second question the operator has already answered in their head. Name the actual file. Fall back to the two-stage form only where the skill genuinely cannot tell.

**`Drop` is destructive and gets the destructive treatment**, and its option description says what the record will read afterwards, since a dropped item leaves a line saying it was dropped rather than nothing at all. Where the skill is guessing that something is `Done already`, recommend what the evidence supports: a closed checkbox keeps its text and its reason, so it is reversible.

Never invent dates or completion stamps. Use the vault's marker syntax for any edits. Do not archive an entity with unresolved open actions still framed as live work - that's how a "closed" project or a shelved idea keeps haunting `/para-daily-brief`.

## Step 3 - Validate brief and actions files

- **brief.md**: must exist and read as a coherent record of what the entity *was* (for a project: outcome, what shipped, key decisions; for an idea: what the concept was and why it's being shelved - superseded, no traction, decided against). If missing, offer to reconstruct a short historical brief from the actions.md plus any artifacts in the folder, stating clearly it's a post-hoc reconstruction and inventing nothing. If present but stale (still written as live or future work), offer to retense it to a closed record.
- **actions.md**: should end as a clean closed record - completed items, plus a forward pointer to wherever surviving work went. No open `[ ]` items left dangling in an archived file.
- Respect "do not add" rules (some vaults forbid `actions.md` in certain trees).

## Step 4 - Route surviving actions and living-reference files

**Surviving actions** (from Step 2): ask each time where they go - do not assume a v2. Options to offer:

- A **new successor idea** at `resources/ideas/<name>-vNext/` (scaffold `brief.md` **only**, cross-linked to the archived original) - use only if the user chooses it.
- An **existing project**, or an **area's rolling actions**.
- A **contact file**, for anything that is really a follow-up with one person.
- **Drop**.

**A successor idea never gets an `actions.md`** (the vault's "Where a checkbox may live" rule). Fold what survives into its `brief.md` as open questions and prose next steps. A genuinely dated commitment is not idea material: route it to the owning area's `actions.md`, an existing project, or the contact file.

**Living-reference files**: scan the entity folder for files whose *content* is reusable reference rather than history - playbooks, positioning or strategy docs, templates, anything linked by other live work as a resource. Propose moving them to `resources/<name>/`. The entity's history (brief, actions, one-time migration or handoff plans) archives with it.

**Stale source snapshots**: flag any in-folder copy superseded by a canonical live source - keeping a dead copy invites edits to the wrong source. Surface for deletion (compare contents plus individual approval, per the operating discipline).

## Step 5 - Decide the version suffix (projects only)

**Skip this step entirely for ideas.** Ideas are archived under their own name at `archive/ideas/<name>/`, with no `-v1` / `-vN` suffix - they were never a versioned deliverable, so the version pairing doesn't apply.

For **projects**, ask whether the archived folder should carry a version suffix (`<name>-v1`). One question, two options, the recommendation first with its reason in the description. Recommend one when **either**:

- A successor (a `-v2` idea, or a planned rebuild) exists or was just created in Step 4, so the pair reads as `v1` shipped / `v2` still a concept, **or**
- The project is likely to recur (websites, decks, seasonal work).

Recommend **no suffix** for one-off projects with no expected successor. Let the user override either way. Apply the chosen name to the archive destination.

## Edge cases

- **No brief.md**: offer a post-hoc reconstruction from actions plus artifacts; mark it clearly as reconstructed.
- **Open actions belong to another owner** (a contact, an area): route them there rather than into a successor idea.
- **No successor wanted but actions survive**: route to an area's rolling actions or an existing project; only scaffold an idea if the user asks.
- **Vault has no `actions.md`** (action tracking excluded by convention, as in read-only consumer vaults): there is nothing to reconcile in Step 2. Fall back to the vault's prose convention - read the entity's `brief.md` / `README.md` for next steps written as prose, resolve those with the user the same way (done / survives / drop), and record survivors as prose in the destination rather than as markers. Do not create an `actions.md` to do this.
