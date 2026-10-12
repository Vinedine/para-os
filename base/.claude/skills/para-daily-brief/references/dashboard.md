# Visual dashboard (Step 7)

The page the brief builds from data it already collected: no new scanning. It is one template with the data embedded, and its own script dates everything against the day it is opened.

## Rendering

`scripts/render_dashboard.py` builds the page from the scan output plus a judgment file holding only what the model decided: the flag lines worth showing, the agenda, and the Next action. Its docstring gives the judgment file's fields.

1. Write the judgment file with the Write tool, beside the scan output, never inside the vault.
2. Run `render_dashboard.py --scan <scan output> --judgment <judgment file> --out <scratchpad>/vault-dashboard.html`. It prints `out`, `publish`, the page's `title` and `description`, and the `url` this vault's dashboard was last published to.
3. Where `publish` is `local`, the page is already at `out`, on this machine: give that path and stop here.
4. Otherwise publish `out` to that `url`, with that `description`. Where it is null, or the publish refuses it, find the page by the title match below. After a publish, run `render_dashboard.py --remember <url> --vault <vault root>`.

**Exit 2 over the judgment** (it named a task or flag the scan does not hold): fix the judgment and render again.

## The judgment file

- `flags`: the Step 4c flag lines, verbatim. One that reports a scan flag is an object naming its `kind` (plus its `file` or `source`, per the docstring), and opens on the tasks, files or briefs behind it.
- `agenda`: today and this week, or the terminal view's Upcoming expansion when both are empty; `agenda_note` names any failed source rather than dropping it.
- `next_action`: the brief's Next action.

## Where the page goes

Each vault's choice, asked at onboarding and by `/para-upgrade`, and recorded with `render_dashboard.py --publish claude|local --vault <vault root>`: a private claude.ai artifact by default, or a local page that never leaves the machine. Change it only when the operator asks.

## Without a brief run

`scripts/refresh_dashboard.py`, run from an end-of-turn hook its docstring gives, keeps the local page current under `$PARAOS_HOME/cache/daily-brief/` with no model run. Wiring it is the operator's choice; the Next action and the agenda stay the full brief's.

## Identity and lifecycle

- **The printed `title` is also the update key** where no `url` is remembered, and an existing page may differ from it in case or separators. List existing artifacts and compare *normalized* forms of both sides: lowercase, `-` and `_` to spaces, runs of whitespace collapsed, and a `vault` token immediately before `dashboard` dropped. Read the first title that matches, then republish to its `url`; create a new artifact only when nothing does, and never rename one: a matched page keeps its title.
- Icon: `chart` on the first publish, omitted on redeploy.
