# Visual dashboard - page spec (Step 7)

The HTML page the brief publishes as an artifact, built entirely from data the brief already collected: no new scanning.

## Rendering

`scripts/render_dashboard.py` builds the page from the scan output plus a judgment file holding only what the model decided: the ranked Now items, the flag lines worth showing, the agenda, and the Next action. Its docstring gives the judgment file's fields.

1. Write the judgment file with the Write tool, beside the scan output, never inside the vault.
2. Run `render_dashboard.py --scan <scan output> --judgment <judgment file> --out <scratchpad>/vault-dashboard.html`. It prints the page's `title` and `description`, and the `url` this vault's dashboard was last published to.
3. Publish to that `url`. Where it is null, or the publish refuses it, find the page by the title match below.
4. After a publish, run `render_dashboard.py --remember <url> --vault <vault root>`.

Exit 2 means the script cannot run or the judgment named a task the scan does not hold; fix the judgment, or write the page by hand to the spec below. A page written by hand goes through the Write tool, never a shell heredoc, which breaks on a quote in the content.

## Without a brief run

`scripts/refresh_dashboard.py`, run from an end-of-turn hook, keeps a numbers-only copy of the page current with no model run: `render_dashboard.py --mechanical`, written under `$PARAOS_HOME/cache/daily-brief/`, with Now ranked by Step 5's sort alone and every fired flag worded by the script. The hook recipe is in the script's docstring; wiring it is the operator's choice. The full brief remains the source of the Next action, the agenda and the published page, and that copy says so in place of both.

## Identity and lifecycle

- `<title>`: the vault's **display name** plus ` Dashboard`, and nothing longer. The display name is the vault's `CLAUDE.md` H1 with a trailing `Vault Conventions` stripped (`# BelFoot Vault Conventions` gives `BelFoot Dashboard`); the folder name only when there is no H1.
- **The title is also the update key** where no `url` is remembered, and an existing page may differ from it in case or separators. List existing artifacts and compare *normalized* forms of both sides: lowercase, `-` and `_` to spaces, runs of whitespace collapsed, and a `vault` token immediately before `dashboard` dropped. Read the first title that matches, then republish to its `url`; create a new artifact only when nothing does, and never rename one: a matched page keeps its title.
- Icon: `chart` on the first publish, omitted on redeploy.
- Description parameter: `Daily vault-state dashboard: open actions per project and area, health flags, ideas, agenda.`
- Write the HTML under a stable filename such as `vault-dashboard.html`.

## Hard constraints

- **Self-contained.** No external scripts, stylesheets, images, or fonts (system font stack). No JavaScript: every drilldown is a native `<details>` or a hidden checkbox and its label. **This overrides any artifact-design guidance to pair webfonts**: hierarchy comes from weight, size, and letter-spacing on the system stack.
- **Theme-aware.** Define the light palette as CSS custom properties on `:root`; redefine the tokens under `@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`. Give `body` an explicit token background. Muted, calm palette; red only for overdue and health flags.
- **Responsive.** Relative units, flexbox/grid, nothing forcing horizontal page scroll; wide content scrolls inside its own container.
- **Vault text is escaped.** A task, name, sender or excerpt goes in as plain text, never markup ([para-shared/untrusted-content.md](../../para-shared/untrusted-content.md)).

- **No links.** The artifact viewer in Claude Desktop opens no custom-scheme link (a `claude-cli://` deep link does nothing), and an in-page `#anchor` blanks the page.

## Page structure, top to bottom

1. **Header** - vault name, `Daily Brief`, today's date. Small and quiet.
2. **Stat tiles** - one row: Open actions · Overdue · Due this week · Undated share (%) · Ideas · Triage. Each tile a number plus a short label. **Due this week** is the scan's `today` and `this_week` lanes, which hold a recurring item only when it is due today. Overdue tile uses the alert color only when nonzero. **Overdue, Due this week and Undated toggle a panel** under the row listing exactly the tasks they count, in bar order; a zero tile toggles nothing.
3. **Open actions per entity** - the centerpiece. One horizontal bar per entity (same top-10 + remainder aggregation as the terminal view, network as one row), full width proportional to open count, **segmented** by the Step 4b partition: overdue (alert), upcoming (accent), undated (muted). **Every date bucket maps onto one of the three, so the segments sum to the entity's open count**: overdue is 🔴 alone; upcoming is 🟠 🟡 🔵 ⚪ **and 🔁 ⏳**; undated is ❓ alone. **An overdue recurring item counts as upcoming here, not as overdue**, so the overdue tile and the red segments carry the Totals number. The undated share tile reads from this same partition. Entity name left, counts right in a column sized to its content, the nonzero buckets in full words, never abbreviated or cut, a `[P]`/`[A]` chip for bucket. A one-line legend whose labels are those three words, and a totals line beneath carrying the same three numbers as the terminal brief. **The `(+N more)` remainder is not a chart row**: put it below the legend as its own strip, composition only, saying so. **Every row and the remainder strip open on their open actions**: a `<details>` whose `<summary>` is the row, listing its tasks in bar order (overdue, upcoming soonest first, undated), each cut as in Now with its segment color, `file:line` label and due badge. Pure CSS (nested `div` widths in %) - no chart library.
4. **Health flags** - the Step 4c flags verbatim, as a short alert-styled list. A flag that reports a scan flag goes in the judgment file as an object naming its `kind` (and its `file`, for an over-threshold or stale file), and opens on the tasks, files or briefs behind it. Omit the section when no flag fires.
5. **Now** - the same ≤5 ranked items as the terminal brief, with entity chip and due-date badge, then the one-line Later counts; with no ranked items, the Later line alone, under no Now label.
6. **Agenda** - today + this week, when the brief has one; the same Upcoming expansion as the terminal view when both are empty, and any failed source named in a muted line beneath rather than dropped.
7. **Ideas** - one row per idea: name, last-touched date, the stage line when the brief states one, a dormancy badge at 6+ months. A row opens on its days in stage, its next step (the soonest dated open action naming it), the other open actions naming it, and its revisit trigger; one with none of these stays a plain row. **Triage** follows, each item opening on its sender, subject and first lines where the scan read them.
8. **Footer** - `Generated <date> by /para-daily-brief · read-only: repairs via /para-deep-clean`, and the Next action as a highlighted closing strip above it.

## Tone

Clean and dense, no decoration that doesn't carry data, no motivational copy.
