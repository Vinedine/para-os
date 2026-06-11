---
name: daily-brief
description: Produce a bucketed daily-action dashboard from the current vault's actions.md and per-contact files, with a meetings agenda from the vault's meetings.md. Use when user asks "what should I work on today", "what's overdue", or types /daily-brief [today|week|overdue|all].
allowed-tools: Bash, Glob, Grep, Read
---

# Daily Brief

Produces a single-pass, date-aware dashboard of open tasks from every action-bearing file in the current vault, grouped into urgency buckets relative to today. Covers both project/area action files and per-contact files (relationship-paced actions).

**This skill is vault-agnostic.** It discovers action-bearing files at runtime and relies on Obsidian Tasks plugin conventions - no vault-specific paths are hardcoded.

**Two vault types** (detected at runtime, Step 1b - no hardcoded paths):
- **Type A** - a PARA vault with `actions.md` files + a `triage/` inbox you process here. The normal full dashboard.
- **Type B** - a read-only consumer vault (the para-os read-only flavor: render pipeline, `flip.ps1`/`render.ps1`, **no `actions.md`** - action tracking is not used by design). The only thing to surface is loose `triage/` files, which are cleared by running `/triage` in the vault. In a Type B vault, render **only** the 📥 Triage section and do **not** report missing `actions.md` as an error.

## When to invoke

- User types `/daily-brief` (optionally followed by `today`, `week`, `overdue`, or `all`)
- User asks "what should I work on today" / "what's on my plate" / "show my dashboard"
- User asks "what's overdue" or "what's coming up"

## Arguments

Optional single scope argument:

| Arg | Shows |
|---|---|
| *(none)* | 🗓 Agenda + Overdue + Today + This week + Next 30 days + Recurring + Waiting + 📥 Triage. Collapses "Later" and "Undated" to one-line counts. |
| `today` | 🗓 Agenda (today) + Overdue + Today + 📥 Triage (morning standup view) |
| `week` | 🗓 Agenda (this week) + Overdue + Today + This week + 📥 Triage |
| `overdue` | Overdue only (skips the agenda + triage) |
| `all` | Full expansion - includes "Later (>30 days)" and "Undated" in full, plus 🗓 Agenda (with Upcoming) |

## Procedure

### Step 1: Get today's date

```bash
date +%Y-%m-%d
```

Use the Bash tool. **Do NOT substitute a cached date from memory or context** - the skill must reflect today's actual calendar date.

### Step 1b: Identify the vault type

A cheap Glob on the current vault, to branch the rest of the run:

- **Type B (read-only)** if there is **no `actions.md`** anywhere in the vault **and** a
  `flip.ps1` or `render.ps1` exists at the vault root (the render-pipeline signature).
  → Skip the task buckets entirely; produce only the 📥 Triage section per Step 5b, framed as
  "read-only vault - run `/triage` to clear." Do not treat the absent `actions.md` as an error.
- **Type A** otherwise → the normal full dashboard (Steps 2-7).

You can fold this into Step 2: if the Step 2 grep returns zero `actions.md` matches, do the
`flip.ps1`/`render.ps1` Glob to decide Type B vs. a genuinely empty Type A vault.

### Step 2: Extract all open tasks and headings

Run two `Grep` calls **in parallel** to scope the scan tightly to action-bearing files. Do NOT scan the whole vault with `path: .` + `type: md` - that produces oversized output (70KB+ on a moderately populated vault) that has to be persisted and re-read, and the `type: md` filter still pulls in every README and reference doc.

**Grep call 1 - actions.md files:**
- `pattern`: `^(# |## |- \[ \])`
- `glob`: `**/actions.md`
- `output_mode`: `content`
- `-n`: `true`
- `head_limit`: `0` (unlimited - missing a match means a wrong dashboard)

**Grep call 2 - contact files (per-contact action items live here, not in actions.md):**
- `pattern`: `^(# |## |- \[ \])`
- `glob`: `**/{network,contacts,people}/*.md`
- `output_mode`: `content`
- `-n`: `true`
- `head_limit`: `0`

ripgrep returns lines like `path/to/file.md:5:## Heading` grouped by file in line-number order. Discard any match where the file path starts with `archive/` (historical, not actionable).

If both calls return zero matches, respond `No action-bearing files found in <cwd>.` and stop.

**Handle truncated lines.** ripgrep emits `[Omitted long matching line]` for results past its column-width limit. In vaults with detailed property/tenant or recurring-task lines (owner, rent amount, source-doc link, instructions all on one line), this is common and silently corrupts the dashboard. For every `(file, line)` pair flagged as omitted, use `Read` to fetch that file and recover the actual line text before parsing markers. Cheaper than re-running ripgrep with `--max-columns=0`, since only a handful of lines per run hit the limit.

### Step 3: Associate tasks with section headings and parse markers

For each surviving file, walk its lines in the order ripgrep returned them, maintaining two cursors:

- `currentH1` - most recent `# ` heading seen
- `currentH2` - most recent `## ` heading seen since the last H1 (reset to null on H1)

For each line:
- `# <text>` → set `currentH1 = <text>`, reset `currentH2 = null`
- `## <text>` → set `currentH2 = <text>`
- `- [ ] <text>` → emit a task. Section heading = `currentH2`, unless it's literally `Next actions` (case-insensitive) in which case use `currentH1`. If both are null, leave section blank.

`- [x]` (completed) lines never match the regex, so no separate skip logic is needed.

For each emitted task, parse markers from the line text:

| Marker | Regex | Meaning |
|---|---|---|
| Due date | `📅 (\d{4}-\d{2}-\d{2})` | Hard deadline |
| Start date | `🛫 (\d{4}-\d{2}-\d{2})` | Not actionable until this date |
| Scheduled | `⏳ (\d{4}-\d{2}-\d{2})` | Planned work date |
| Recurring | `🔁 (every [^📅🛫⏳🔺🔼🔽⏬\n]+)` | Cadence pattern |
| Priority | `[🔺🔼🔽⏬]` | 🔺 highest → ⏬ lowest (4 levels; no marker = medium) |

Derive the **scope label** from the file path:
1. Strip the leading category folder if present (`projects/`, `areas/`, `resources/ideas/`).
2. Strip the trailing `/actions.md` for action files, or `.md` for contact files.

Examples:
- `projects/ticketing-platform-replacement/actions.md` → `ticketing-platform-replacement`
- `areas/stadium/actions.md` → `stadium`
- `areas/finance/vat/actions.md` → `finance/vat` (preserve the subfolder when the leaf alone is ambiguous, e.g. country-code or short acronym)
- `resources/ideas/fan-app/actions.md` → `fan-app`
- `areas/network/jan-claes.md` → `network/jan-claes`

If the path doesn't start with a known category folder, use the full relative path minus the trailing `/actions.md` or `.md`.

Final per-task record:
- File path (relative to CWD)
- Line number
- Scope label
- Task text (stripped of all emoji markers and trailing whitespace)
- Due / start / scheduled dates (if present)
- Priority (if present)
- Recurring cadence (if present)
- Section heading (per the H2/H1 fallback rule above)

### Step 4: Bucket against today

Let `T` = today's date from Step 1.

| Bucket | Condition |
|---|---|
| 🔴 Overdue | has `📅` AND `📅 < T` |
| 🟠 Today | has `📅` AND `📅 == T` |
| 🟡 This week | has `📅` AND `T < 📅 ≤ T+7` |
| 🔵 Next 30 days | has `📅` AND `T+7 < 📅 ≤ T+30` |
| ⚪ Later | has `📅` AND `📅 > T+30` |
| 🔁 Recurring | has `🔁` marker - classify here regardless of `📅` |
| ⏳ Waiting | has `🛫` AND `🛫 > T` (not actionable yet) |
| ❓ Undated | no `📅`, no `🛫`, no `🔁` |

**Precedence when multiple apply:** Recurring > Waiting > date-based bucket. A recurring item overdue is in Recurring, not Overdue (the `🔁` template says "do it, then check to roll forward").

### Step 5: Sort within each bucket

1. Priority descending: 🔺 → 🔼 → (no marker) → 🔽 → ⏬
2. Date ascending (nearest first)
3. File path alphabetically

### Step 5b: Check the triage folder (optional)

Use Glob to check whether `triage/` exists in the current vault. If it does, list its **direct file children** (top-level only - do not recurse, do not list subdirectories like `triage/mail/`). Capture filenames and a count.

If the folder does not exist, or exists but is empty, skip the Triage section in the output entirely.

**Do not parse file contents.** This is a pure file listing - the triage folder is a reminder, not a task source.

In a **Type B (read-only)** vault (Step 1b) this is the *whole* output: title the section
`## 📥 Triage - loose files (N · run /triage)` and add a one-line note that this is a read-only
vault, so the next step is to run `/triage` here. No task buckets, no "missing actions.md" message.

### Step 5c: Build the 🗓 Agenda from meetings.md

Meetings live one per line in the vault's `meetings.md`. **Type A vaults only** - skip this step in a
Type B (read-only) vault. Grep the current vault:

- `pattern`: `^- 🗓 `
- `glob`: `**/meetings.md`
- `output_mode`: `content`, `-n`: `true`, `head_limit`: `0`

Discard `archive/` paths. Parse each line - `- 🗓 <date> [<time>] · <title> [· <field>…] [🔁 every <cadence>]`:
- date `(\d{4}-\d{2}-\d{2})`; optional time `(\d{1,2}:\d{2}(?:[–-]\d{1,2}:\d{2})?)`; then ` · `-separated
  fields (first = title). If `🔁 (every …)` present, capture the cadence and strip it.

Bucket against today `T`:
- `🔁` present → **Recurring**; date == `T` → **Today**; `T` < date ≤ `T+7` → **This week**;
  date > `T+7` → **Upcoming** (count only, expand in `all`); date < `T` and not recurring → ignore (past).

Sort within each group by date then time. Omit the Agenda entirely if no meetings are in scope, or if
the vault has no `meetings.md`.

### Step 6: Render output

Use this exact layout. **Omit any bucket that has zero items** - no empty placeholders. Always start with the H1 title line.

```
# Daily Brief - <YYYY-MM-DD>

## 🗓 Agenda
**Today**
- <time> · <title> · <attendees/where>
**This week**
- <Dow DD> · <time> · <title>
**Recurring**
- every <cadence> · <title>
*(+N more upcoming)*

## 🔴 Overdue (N)
- 🔺 <task text> - [<scope>:<line>](<relative/path>#L<line>) · *<section heading>* · 📅 <date> (<Nd> ago)
- ...

## 🟠 Today (N)
- <task text> - [<scope>:<line>](<path>#L<line>) · *<section>* · 📅 <today>

## 🟡 This week (N)
- <task text> - [<scope>:<line>](<path>#L<line>) · *<section>* · 📅 <date> (in <Nd>)

## 🔵 Next 30 days (N)
- ...

## 🔁 Recurring (N)
- <task text> - [<scope>:<line>](<path>#L<line>) · *<section>* · every 3 months · next 📅 <date>

## ⏳ Waiting on start date (N)
- <task text> - [<scope>:<line>](<path>#L<line>) · *<section>* · 🛫 <date> (starts in <Nd>)

## 📥 Triage (N to process)
- [<filename>](triage/<filename>)
- ...

## Collapsed
- Later (>30 days): N items
- Undated: N items
```

**Line rules:**
- One line per task - no wraps
- Priority emoji at start of bullet when present (🔺/🔼/🔽/⏬), omit the emoji when priority is medium
- Date suffix in parens - "(22d ago)" for overdue, "(in 5d)" for upcoming
- Section heading italicized - gives context *why* the task exists
- Link text is `<scope>:<line>` (e.g. `cashless-stadium-rollout:7`), so the project/area is visible without opening the file
- Use relative paths from CWD for the link target (VS Code renders them clickable via the extension)

### Step 7: Apply argument overrides

Handle the optional arg by filtering which buckets render:

- `today`: show only 🗓 Agenda (today) + 🔴 + 🟠 + 📥 Triage. Omit Collapsed.
- `week`: show 🗓 Agenda (this week) + 🔴 + 🟠 + 🟡 + 📥 Triage. Omit Collapsed.
- `overdue`: show only 🔴. Omit Agenda, Triage and Collapsed (strict "what's late" view).
- `all`: expand Collapsed - show ⚪ Later and ❓ Undated as full sections; Agenda expands **Upcoming**. Triage shown as normal.

The 🗓 Agenda renders at the **top** in all modes except `overdue`, scoped to match the arg (today → Today only; week → Today + This week), always plus **Recurring**, and only when the vault has a `meetings.md` with meetings in scope. The 📥 Triage section renders in all modes except `overdue`, and only when the folder exists with at least one file in it.

## Strict rules

- **Do NOT parse completed items (`- [x]`)** - they're history.
- **Do NOT rewrite actions.md files** to "fix" missing markers. If an item is undated, report it as undated; don't invent dates.
- **Do NOT follow links** into other files for extra context. The H2 section heading is sufficient.
- **Do NOT add commentary or recommendations** about what to do. Just present the dashboard. Decisions are the user's.
- **Do NOT include the `**Status:**` lines** from actions files.
- **Do NOT dedupe cross-referenced items** (same task mentioned in two files). Show both - the links let the user jump to either context.
- **Meetings (🗓 Agenda): today + future only, never invented.** Ignore past-dated, non-recurring meeting lines (history). Render only what the `meetings.md` line contains - never fabricate a meeting, time, or attendee.

## Edge cases

- **Vault with no actions.md files:** first apply Step 1b. If it's a **Type B (read-only)** vault (render-pipeline signature present), this is expected - render only the 📥 Triage section with the "run `/triage`" framing; never say "No actions.md files found." If it's **Type A** with no actions.md and an empty/absent `triage/`, respond "No actions.md files found in <cwd>." and stop; if Type A with a populated triage, render only the 📥 Triage section.
- **`triage/` missing or empty:** silently omit the Triage section.
- **Subdirectories inside `triage/`:** ignore them (e.g. `triage/mail/` could be an email mirror, not loose triage items). Only top-level files render.
- **File with only completed items:** skip silently, don't list it.
- **Item with both 🛫 future AND 📅:** goes in Waiting (not actionable yet).
- **Item with 🛫 in the past:** ignore the 🛫 (it was a gate that has opened); bucket by 📅 instead.
- **Recurring item without 📅:** still list in Recurring, show "next: -" placeholder.
- **Undated item with 🔺 priority:** still goes in Undated bucket, but retains 🔺 marker in output.
- **Malformed date** (e.g. `📅 2026-13-45`): skip the date, treat as undated, and note "(malformed date)" at end of line.

## Example output (fragment)

```
# Daily Brief - 2026-04-22

## 🔴 Overdue (4)
- 🔺 Score the two remaining ticketing vendor bids - [ticketing-platform-replacement:13](projects/ticketing-platform-replacement/actions.md#L13) · *Vendor selection* · 📅 2026-03-31 (22d ago)
- Collect signed NDAs from the shortlisted vendors - [ticketing-platform-replacement:7](projects/ticketing-platform-replacement/actions.md#L7) · *Procurement* · 📅 2026-04-21 (1d ago)
- Confirm the stadium WiFi survey scope with facilities - [cashless-stadium-rollout:11](projects/cashless-stadium-rollout/actions.md#L11) · *Infrastructure* · 📅 2026-02-26 (55d ago)
- Jan to send the legacy POS transaction export - [cashless-stadium-rollout:7](projects/cashless-stadium-rollout/actions.md#L7) · *Data migration (critical path)* · 📅 2026-04-02 (20d ago)

## 🟡 This week (6)
- 🔺 Present the modernisation budget to the CFO - [stadium:11](areas/stadium/actions.md#L11) · *Budget cycle* · 📅 2026-04-25 (in 3d)
- ...
```
