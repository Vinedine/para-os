# Promote an idea to a project

`resources/ideas/<name>/` becomes `projects/<name>/`: a move that keeps the idea's thinking.

1. **Check the bar**: someone waits on a dated deliverable, money or a formal engagement is committed, or a go/no-go is on the calendar, unless the vault or the brief sets a stricter one. An idea that is merely interesting again stays where it is.
2. **Ask only** who is waiting and by when, and the one next step. Where the brief's framing has drifted, the operator corrects it in one line.
3. **List the inbound references** to the idea's path and name, each a link to follow, prose to reword, or a historical mention inside `archive/` to leave, and show the list first.
4. **Move, retense, seed**:
   1. `git mv` the folder, or a plain move outside git.
   2. Retense the brief to the vault's project shape, facts verbatim: the concept becomes the goal, open questions stay open. Idea-only anchors go; a staged entity keeps its header, its Stage line moved to the promoting stage `(since <today>)`. Whatever no longer fits is surfaced, never dropped.
   3. Create `actions.md` with the one next step, a `📅` only for a real date.
   4. Repoint every inbound link, and rewrite the links inside the moved folder per [operating-discipline.md](../../para-shared/operating-discipline.md#moving-an-entity-folder).
5. **Verify**: no reference to the old path remains, and every relative link inside the moved folder resolves.

- **The idea has an `actions.md`**: fold its items into the project's file, one open, the rest `## Backlog` prose.
- **Only part of it is committed**: promote that part under its own name and leave the idea, narrowed, linked both ways.
- **It should become an area**: the same move into `areas/<name>/`, with the area's two questions.
- **A project of that name exists**: stop and ask.
