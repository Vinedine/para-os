# A skill's page

What every skill that ends on a page shares, for its own page and for one the vault declares for it. [scripts/paraos_pages.py](scripts/paraos_pages.py) does the mechanics; its docstring is the specification.

## Publishing it

- **Never inside the vault.** A page is written to a scratch folder, or to its local page under `$PARAOS_HOME/cache/`.
- **Where it goes is the vault's choice, per page**: a private claude.ai artifact by default, or a local page that never leaves the machine, recorded with `paraos_pages.py publish claude|local --page <page> --vault <vault root>`. Change it only when the operator asks; the daily brief's is asked at onboarding and by `/para-upgrade`.
- **A local page is already in place** at `out`: give that path and stop.
- **Otherwise publish `out`** to the printed `url`, with the printed `description`; icon `chart` on the first publish, none on a republish. Then record it: `paraos_pages.py remember <url> --page <page> --title <title> --vault <vault root>`, `page` and `title` as printed.
- **No `url`, or the publish refuses it:** list existing artifacts and pass their titles to `paraos_pages.py match <title> <listed title>...`. Read the artifact whose title it prints, then republish to its `url`; create a new artifact only when it prints null, and never rename one: a matched page keeps its title.
- **Without an Artifact tool, or when the publish fails,** say so in one line and move on. Otherwise give the page's link on one line.

## A page the vault declares

A vault names pages of its own under `## Pages` in its `CLAUDE.md`, one row per page, the script's path from the vault root:

| Skill | Script |
|---|---|
| para-pipeline | `resources/scripts/vendor-board.py` |

A skill whose steps link here runs the rows naming it after its own output, with `paraos_pages.py run --skill <skill> --scan <its scan output> --out-dir <scratch folder> --vault <vault root>`, and publishes each page it prints as above. A page with an `error` is said in one line and skipped. The script is the vault's, and the skill's strict rules hold for what it shows. A later step that changes what a page shows rebuilds it with `paraos_pages.py refresh --page <page> --vault <vault root>` and republishes it, never the whole skill.
