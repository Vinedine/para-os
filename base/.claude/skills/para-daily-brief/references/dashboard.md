# Visual dashboard (Step 7)

The HTML page the brief publishes as an artifact, built entirely from data the brief already collected: no new scanning.

## Rendering

`scripts/render_dashboard.py` builds the page from the scan output plus a judgment file holding only what the model decided: the ranked Now items, the flag lines worth showing, the agenda, and the Next action. Its docstring gives the judgment file's fields.

1. Write the judgment file with the Write tool, beside the scan output, never inside the vault.
2. Run `render_dashboard.py --scan <scan output> --judgment <judgment file> --out <scratchpad>/vault-dashboard.html`. It prints the page's `title` and `description`, and the `url` this vault's dashboard was last published to.
3. Publish to that `url`, with that `description`. Where it is null, or the publish refuses it, find the page by the title match below.
4. After a publish, run `render_dashboard.py --remember <url> --vault <vault root>`.

**Exit 2 over the judgment** (it named a task or flag the scan does not hold): fix the judgment and render again.

## The judgment file

- `now`: the same five or fewer ranked items as the terminal brief.
- `flags`: the Step 4c flag lines, verbatim. One that reports a scan flag is an object naming its `kind` (and its `file`, for an over-threshold or stale file), and opens on the tasks, files or briefs behind it.
- `agenda`: today and this week, or the terminal view's Upcoming expansion when both are empty; `agenda_note` names any failed source rather than dropping it.
- `next_action`: the brief's Next action.

## Without a brief run

`scripts/refresh_dashboard.py`, run from an end-of-turn hook its docstring gives, keeps a numbers-only copy of the page current under `$PARAOS_HOME/cache/daily-brief/` with no model run. Wiring it is the operator's choice; the Next action, the agenda and the published page stay the full brief's.

## Identity and lifecycle

- **The printed `title` is also the update key** where no `url` is remembered, and an existing page may differ from it in case or separators. List existing artifacts and compare *normalized* forms of both sides: lowercase, `-` and `_` to spaces, runs of whitespace collapsed, and a `vault` token immediately before `dashboard` dropped. Read the first title that matches, then republish to its `url`; create a new artifact only when nothing does, and never rename one: a matched page keeps its title.
- Icon: `chart` on the first publish, omitted on redeploy.
