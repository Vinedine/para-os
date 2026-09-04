# Promote an idea to a project

`resources/ideas/<name>/` becomes `projects/<name>/`. This is a **move**, not a copy and not a fresh start: the idea's brief carries thinking worth keeping, and the vault rule is that every move repoints inbound links in the same pass.

## Step 1 - Check the bar is actually met

The lifecycle names it: someone is waiting on a deliverable by a date, money or a formal engagement is committed, or a go/no-go review is on the calendar. If the vault or the idea's own brief defines a stricter bar, that one applies.

An idea that has merely become interesting again has not been promoted. Say so and leave it where it is - moving it early creates a project that `/para-daily-brief` counts and nobody works on, which is exactly the noise the idea bucket exists to keep out.

## Step 2 - Ask only what the brief cannot answer

The idea brief already holds the concept and the reasoning, so the project interview shrinks to what an idea by definition never carried:

1. Who is waiting for it, and by when?
2. What is the one next step?

Do not re-ask what the concept is. If the brief's framing has drifted from what the user now means, note the difference and let them correct it in one line rather than re-interviewing.

## Step 3 - Scan inbound links before moving

Grep the whole vault for references to the idea's path and name. Classify each: a link that should follow the move, a mention in prose that should be reworded, a historical reference inside an archived folder that stays as it is. Show the list before touching anything.

## Step 4 - Move, retense, seed

In order:

1. Move the folder with `git mv` so history is preserved, falling back to a plain move if the vault is not a git repo.
2. **Retense the brief** to the vault's project shape. Facts are preserved verbatim: the concept becomes the goal, the reasoning becomes why it matters, open questions that are still open stay open questions. Idea-only anchors that the vault's conventions define (a stage line, a promotion-criteria section) are removed, because they now describe a state the entity has left. Nothing is silently dropped: anything that no longer fits the project shape is surfaced, not deleted.
3. **Create `actions.md`** with the single next step from Step 2, and a `📅` only where the date is real. Everything else the brief proposed stays prose.
4. **Repoint every inbound link** from Step 3.
5. **Re-depth the links *inside* the moved folder** ([operating-discipline.md](../../para-shared/operating-discipline.md#moving-an-entity-folder)). This move is `resources/ideas/<name>/` to `projects/<name>/`: three levels to two, so each link **loses one** `../`.

## Step 5 - Verify

Two assertions, because one of them passes while the vault is broken. Re-run the Step 3 grep and assert zero stale references to the old path. Then resolve **every relative link inside the moved folder** against its new location and assert each target exists. The first check alone reports success on a folder full of dead links, which is exactly how this fails in practice. A promotion that leaves broken links either way is a failed run.

## Edge cases

- **The idea has an `actions.md`** it should never have had (`resources/` holds no checkboxes). Fold its items into the new project's file rather than treating the file as a surprise: it is pre-existing intent, and the one-action rule applies to what stays open, so the rest becomes `## Backlog` prose.
- **Only part of the idea is being committed.** Promote the committed part under its own name and leave the idea in place, narrowed, with a link each way. Do not move the whole folder and hope the surplus is ignored.
- **The idea should become an area, not a project** (it turned out to be something maintained). Same move, different destination and no deadline to ask for: it lands in `areas/<name>/` with the area interview's two questions, and everything else in this procedure - the link scan, the retensing, the repoint, the verify - is unchanged.
- **A project of that name already exists.** Stop. Either the work is already tracked, or one of the two needs a distinct name, and both are the operator's call.
