# Visual dashboard - page spec (Step 7)

The HTML page the brief publishes as an artifact, built entirely from data the brief already collected: no new scanning.

## Identity and lifecycle

- `<title>`: the vault's **display name** plus ` Dashboard`, and nothing longer. The display name is the vault's `CLAUDE.md` H1 with a trailing `Vault Conventions` stripped (`# BelFoot Vault Conventions` gives `BelFoot Dashboard`); the folder name only when there is no H1.
- **The title is also the update key**, and must match a page an earlier revision named by a different rule. Before publishing, list existing artifacts and compare *normalized* forms of both sides: lowercase, `-` and `_` to spaces, runs of whitespace collapsed, and a `vault` token immediately before `dashboard` dropped. Republish to the `url` of the first title that matches; create a new artifact only when nothing does, and never rename one: a matched page keeps its title.
- Favicon: `📊`, never changed on redeploy.
- Description parameter: `Daily vault-state dashboard: open actions per project and area, health flags, ideas, agenda.`
- Write the HTML to the harness scratchpad or OS temp directory, **never into the vault**, under a stable filename such as `vault-dashboard.html`.

## Hard constraints

- **Self-contained.** No external scripts, stylesheets, images, or fonts (system font stack). No JavaScript. **This overrides any artifact-design guidance to pair webfonts**: hierarchy comes from weight, size, and letter-spacing on the system stack.
- **Theme-aware.** Define the light palette as CSS custom properties on `:root`; redefine the tokens under `@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`. Give `body` an explicit token background. Muted, calm palette; red only for overdue and health flags.
- **Responsive.** Relative units, flexbox/grid, nothing forcing horizontal page scroll; wide content scrolls inside its own container.

## Page structure, top to bottom

1. **Header** - vault name, `Daily Brief`, today's date. Small and quiet.
2. **Stat tiles** - one row: Open actions · Overdue · Due this week · Undated share (%) · Ideas · Triage. Each tile a number plus a short label. **Due this week** is the scan's `today` and `this_week` lanes, recurring items excluded. Overdue tile uses the alert color only when nonzero.
3. **Open actions per entity** - the centerpiece. One horizontal bar per entity (same top-10 + remainder aggregation as the terminal view, network as one row), full width proportional to open count, **segmented** by the Step 4b partition: overdue (alert), upcoming (accent), undated (muted). **Every date bucket maps onto one of the three, so the segments sum to the entity's open count**: overdue is 🔴 alone; upcoming is 🟠 🟡 🔵 ⚪ **and 🔁 ⏳**; undated is ❓ alone. **An overdue recurring item counts as upcoming here, not as overdue**, so the overdue tile, the red segments and the 🔴 bucket carry one number. The undated share tile reads from this same partition. Entity name left, counts right, a `[P]`/`[A]` chip for bucket. A one-line legend whose labels are those three words, and a totals line beneath carrying the same three numbers as the terminal brief. **The `(+N more)` remainder is not a chart row**: put it below the legend as its own strip, composition only, saying so. Pure CSS (nested `div` widths in %) - no chart library.
4. **Health flags** - the Step 4c flags verbatim, as a short alert-styled list. Omit the section when no flag fires.
5. **Now** - the same ≤5 ranked items as the terminal brief, with entity chip and due-date badge, then the one-line Later counts; with no ranked items, the Later line alone, under no Now label.
6. **Agenda** - today + this week, when the brief has one; the same Upcoming expansion as the terminal view when both are empty, and any failed source named in a muted line beneath rather than dropped.
7. **Ideas** - one row per idea: name, last-touched date, the stage line when the brief states one, a dormancy badge at 6+ months.
8. **Footer** - `Generated <date> by /para-daily-brief · read-only: repairs via /para-deep-clean`, and the Next action as a highlighted closing strip above it.

## In a Type B vault

Drop the panels the task scan feeds - the stat tiles that count actions, the per-entity bars (3), and Now (5) - and keep 1, 4 (the over-grown-brief flag only), 6, 7, 8. The tile row becomes Ideas · Triage · Dormant ideas. Say once, in the header, that the vault tracks no actions by design; never render an empty actions chart or a zeroed overdue tile.

## Tone

Clean and dense, no decoration that doesn't carry data, no motivational copy. Omit what has no content, as the terminal brief does.
