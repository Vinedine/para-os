# Visual dashboard - page spec (Step 7)

Defines the HTML page the brief publishes as an artifact. Build it entirely from the data the brief already collected - this file adds no new scanning.

## Identity and lifecycle

- `<title>`: the vault's **display name** plus ` Dashboard`, and nothing longer. The display name is the vault's `CLAUDE.md` H1 with a trailing `Vault Conventions` stripped (`# BelFoot Vault Conventions` gives `BelFoot Dashboard`); the folder name is the fallback, used only when there is no H1 to read. **Not the folder name by default** - a folder name is a path, so `vesper-ventures` would title the page `vesper-ventures Dashboard`, and a fleet whose folders are kebab-case would put a lowercase hyphenated name on every page in the gallery.
- **The title is also the update key**, so it has to match a page an earlier revision named by a different rule. Before publishing, list existing artifacts and compare *normalized* forms of both sides: lowercase, `-` and `_` to spaces, runs of whitespace collapsed, and a `vault` token immediately before `dashboard` dropped. Republish to the `url` of the first title that matches; create a new artifact only when nothing does, and never rename one that already exists. Normalizing both sides is what keeps a rename of this rule from forking every dashboard in the fleet on its next run - widen it in step with any future change to the line above.
- Favicon: `📊`, never changed on redeploy.
- Description parameter: `Daily vault-state dashboard: open actions per project and area, health flags, ideas, agenda.`
- Write the HTML to the harness scratchpad or OS temp directory, **never into the vault** (derived output; it would sync). A stable filename like `vault-dashboard.html` in the scratchpad is fine.

## Hard constraints

- **Self-contained.** No external scripts, stylesheets, images, or fonts (system font stack). No JavaScript needed - the page is a static render of today's state; interactivity earns nothing here. **This overrides any general artifact-design guidance to pair webfonts**, deliberately and by precedence: the page republishes every day and is what a demo puts in front of a prospect, so it renders identically with no network fetch and cannot fail to a silent fallback face. Hierarchy comes from weight, size, and letter-spacing on the system stack.
- **Theme-aware.** Define the light palette as CSS custom properties on `:root`; redefine the tokens under `@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`. Give `body` an explicit token background. Muted, calm palette; red is reserved for overdue and health flags so it keeps meaning.
- **Responsive.** Relative units, flexbox/grid, nothing forcing horizontal page scroll; wide content scrolls inside its own container.

## Page structure, top to bottom

1. **Header** - vault name, `Daily Brief`, today's date. Small and quiet.
2. **Stat tiles** - one row: Open actions · Overdue · Due this week · Undated share (%) · Ideas · Triage. Each tile a number plus a short label. Overdue tile uses the alert color only when nonzero.
3. **Open actions per entity** - the centerpiece. One horizontal bar per entity (same top-10 + remainder aggregation as the terminal view, network as one row), full width proportional to open count, **segmented** by the Step 4b partition: overdue (alert), upcoming (accent), undated (muted). **Every date bucket maps onto one of the three, so the segments sum to the entity's open count**: overdue is 🔴 alone; upcoming is 🟠 🟡 🔵 ⚪ **and 🔁 ⏳** - a recurring or waiting item is scheduled work, not undated work, and leaving either out silently shortens the bar; undated is ❓ alone. **An overdue recurring item counts as upcoming here, not as overdue**, because Step 4 counts it once under Recurring and only *displays* it in 🔴; counting it red as well makes the overdue tile disagree with the 🔴 bucket by exactly the number of lapsed cadences, which is the shape of this disagreement when it happens. The overdue tile, the red segments and the 🔴 bucket therefore always carry one number. The undated share on the tile row reads from this same partition, so the tile and the chart can never disagree. Entity name left, counts right, a `[P]`/`[A]` chip for bucket. A one-line legend whose labels are those three words, and a totals line beneath carrying the same three numbers as the terminal brief. **The `(+N more)` remainder is not a chart row.** Its open count routinely exceeds the largest single entity, so a bar drawn beside the others either lies about magnitude or, scaled honestly, squashes every real row to make space. Put it below the legend as its own strip, composition only, saying so. Pure CSS (nested `div` widths in %) - no chart library.
4. **Health flags** - the Step 4c flags verbatim, as a short alert-styled list. Omit the section when no flag fires.
5. **Now** - the same ≤5 ranked items as the terminal brief, with entity chip and due-date badge, then the one-line Later counts.
6. **Agenda** - today + this week, when the brief has one; the same Upcoming expansion as the terminal view when both are empty, and any failed source named in a muted line beneath rather than dropped.
7. **Ideas** - one row per idea: name, last-touched date, the stage line when the brief states one, a dormancy badge at 6+ months.
8. **Footer** - `Generated <date> by /para-daily-brief · read-only: repairs via /para-deep-clean`, and the Next action as a highlighted closing strip above it.

## Tone

This page is the operator's morning glance and doubles as what a para-os demo shows a prospect: clean, dense, zero decoration that doesn't carry data. No motivational copy, no empty states rendered as sad text - omit what has no content, same rule as the terminal brief.
