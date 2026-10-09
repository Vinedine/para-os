# Reconcile, validate, route (Steps 2 to 5)

## Step 2 - Reconcile open actions

**Open is every `actions.open` checkbox and every `actions.backlog` item not `settled`.** A settled item stays in the closed record and is never asked about. `actions.other_checkbox_files` names the entity's other files still holding open checkboxes, reconciled the same way.

Skip this step for an idea: it holds no checkbox, and `actions.idea_holds_actions` flags one that does. Where `actions.file` is null the vault tracks no actions: settle the next steps its brief states in prose the same way, record survivors as prose, and create no `actions.md`.

One question per open item:

- **Done already**: tick it.
- **Survives**: name the destination where it is obvious (`Route to areas/business/actions.md`); otherwise Step 4 asks.
- **Drop**: the record keeps a line saying it was dropped, as the option says.

A recurring item survives into the recurring section of the area taking the work over, or is dropped. A resolved Backlog item stays as a prose line stating its disposition and reason, undated.

## Step 3 - Validate brief and actions files

- **`brief.md`** (or the README the vault's shape gives it) reads as a closed record: a project's outcome, what shipped and its key decisions; an idea's concept and why it is shelved; an area's scope and why it ended. Offer to retense one still written as live work. With none, offer one reconstructed from the actions and artifacts, marked reconstructed, inventing nothing.
- **`actions.md`** ends as completed items plus a pointer to wherever surviving work went: no open checkbox, no unresolved Backlog item.

**A staged entity is gated.** Where `lifecycle.destination_matches` names a terminal stage ([lifecycles.md](../../para-shared/lifecycles.md)), nothing moves until the operator has written:

- **A Stage line naming that stage** (`lifecycle.stage_line_names_destination`). Show the line as it stands and as it would become.
- **Any reason line the rule file requires for that stage**, non-empty and, where the file gives a list, from it. `lifecycle.reason` carries the field name, its `raw` value, its `key` (the text before its first comma) and the `allowed` list; `allowed: null` means read the rule file yourself.

Name everything missing in one stop, with the exact lines and where they go.

## Step 4 - Route surviving actions and living-reference files

Ask where each surviving action goes, never assuming a v2:

- A **successor idea** at `resources/ideas/<name>-vNext/`, only if chosen: a `brief.md` cross-linked to the archived original, holding what survives as open questions and prose next steps, never an `actions.md`. A dated commitment goes to one of the other homes.
- An **existing project**, or an **area's** `actions.md`.
- A **contact file**, only as `actions.route_options` lists it.
- **Drop**.

**Living-reference files** (playbooks, positioning, templates, anything live work uses as a resource) move to `resources/<name>/`; history (brief, actions, one-time plans) archives with the entity. `inbound.living_reference_candidates` lists each file a live file outside the entity links to: candidates, not a verdict.

**A stale snapshot**, an in-folder copy superseded by a live source, is proposed for deletion.

## Step 5 - Decide the version suffix (projects only)

One question: suffix the archived folder (`<name>-v1`) or not. Recommend `destination.next_suffix` when a successor exists or was just created, or the work recurs (websites, decks, seasonal work); recommend none for a one-off. `destination.suffix_siblings` lists the versions already archived.
