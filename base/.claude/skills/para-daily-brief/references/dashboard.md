# Visual dashboard - page spec (Step 7)

Defines the HTML page the brief publishes as an artifact. Build it entirely from the data the brief already collected - this file adds no new scanning.

## Identity and lifecycle

- `<title>`: `<Vault name> Dashboard` (e.g. `BelFoot Dashboard`). Keep it stable across days - it is also the update key: before publishing, list existing artifacts and republish to the matching title's `url`; only create a new artifact when none matches.
- Favicon: `📊`, never changed on redeploy.
- Description parameter: `Daily vault-state dashboard: open actions per project and area, health flags, ideas, agenda.`
- Write the HTML to the harness scratchpad or OS temp directory, **never into the vault** (derived output; it would sync). A stable filename like `vault-dashboard.html` in the scratchpad is fine.

## Hard constraints

- **Self-contained.** No external scripts, stylesheets, images, or fonts (system font stack). No JavaScript needed - the page is a static render of today's state; interactivity earns nothing here.
- **Theme-aware.** Define the light palette as CSS custom properties on `:root`; redefine the tokens under `@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`. Give `body` an explicit token background. Muted, calm palette; red is reserved for overdue and health flags so it keeps meaning.
- **Responsive.** Relative units, flexbox/grid, nothing forcing horizontal page scroll; wide content scrolls inside its own container.

## Page structure, top to bottom

1. **Header** - vault name, `Daily Brief`, today's date. Small and quiet.
2. **Stat tiles** - one row: Open actions · Overdue · Due this week · Undated share (%) · Ideas · Triage. Each tile a number plus a short label. Overdue tile uses the alert color only when nonzero.
3. **Open actions per entity** - the centerpiece. One horizontal bar per entity (same top-10 + remainder aggregation as the terminal view, network as one row), full width proportional to open count, **segmented**: overdue (alert), dated (accent), undated (muted). Entity name left, counts right, a `[P]`/`[A]` chip for bucket. A one-line legend. Pure CSS (nested `div` widths in %) - no chart library.
4. **Health flags** - the Step 4c flags verbatim, as a short alert-styled list. Omit the section when no flag fires.
5. **Now** - the same ≤5 ranked items as the terminal brief, with entity chip and due-date badge, then the one-line Later counts.
6. **Agenda** - today + this week, when the brief has one.
7. **Ideas** - one row per idea: name, last-touched date, Stage line when present, a dormancy badge at 6+ months.
8. **Footer** - `Generated <date> by /para-daily-brief · read-only: repairs via /para-deep-clean`, and the Next action as a highlighted closing strip above it.

## Tone

This page is the operator's morning glance and doubles as what a para-os demo shows a prospect: clean, dense, zero decoration that doesn't carry data. No motivational copy, no empty states rendered as sad text - omit what has no content, same rule as the terminal brief.
