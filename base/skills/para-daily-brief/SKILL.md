---
name: para-daily-brief
description: Produce a bucketed daily-action dashboard from the current vault's actions.md and per-contact files, with a meetings agenda from the vault's meetings.md. Use when user asks "what should I work on today", "what's overdue", or types /para-daily-brief [today|week|overdue|all].
allowed-tools: Bash, Glob, Grep, Read
---

# Daily Brief

Produces a single-pass, date-aware dashboard of open tasks from every action-bearing file in the current vault, grouped into urgency buckets relative to today. Covers both project/area action files and per-contact files (relationship-paced actions).

**This skill is vault-agnostic.** It discovers action-bearing files at runtime and relies on Obsidian Tasks plugin conventions - no vault-specific paths are hardcoded. There are two vault types, detected at runtime in Step 1b.

## Arguments

Optional single scope argument controls which sections render:

| Arg | Renders |
|---|---|
| *(none)* | 🗓 Agenda + 🔴 Overdue + 🟠 Today + 🟡 This week + 🔵 Next 30 days + 🔁 Recurring + ⏳ Waiting + 📥 Triage + Collapsed (one-line counts for Later and Undated) |
| `today` | 🗓 Agenda (today) + 🔴 + 🟠 + 📥 Triage (morning standup view) |
| `week` | 🗓 Agenda (today + this week) + 🔴 + 🟠 + 🟡 + 📥 Triage |
| `overdue` | 🔴 only - no Agenda, no Triage, no Collapsed (strict "what's late" view) |
| `all` | Full expansion - ⚪ Later and ❓ Undated as full sections, Agenda includes Upcoming |

In every mode except `overdue`, the 🗓 Agenda renders at the top (scoped to the arg, always including its Recurring group) and 📥 Triage renders at the bottom. Both appear only when they have content (Steps 5b/5c).

## Procedure

### Step 1: Get today's date

```bash
date +%Y-%m-%d
```

Use the Bash tool. **Do NOT substitute a cached date from memory or context** - the skill must reflect today's actual calendar date.

### Step 1b: Identify the vault type

- **Type B (read-only consumer vault)** - no `actions.md` anywhere in the vault **and** a `flip.ps1` or `render.ps1` at the vault root (the render-pipeline signature). Action tracking is absent by design, so the missing `actions.md` is **not** an error - never report it as one. Skip the task buckets and the Agenda entirely; the whole output is the 📥 Triage section (Step 5b), titled `## 📥 Triage - loose files (N · run /para-triage)`, plus a one-line note that this is a read-only vault, so the next step is to run `/para-triage` here.
- **Type A (PARA vault with action tracking)** otherwise - the normal full dashboard (Steps 2-6).

Fold the detection into Step 2: only if the grep returns zero `actions.md` matches, Glob for `flip.ps1`/`render.ps1` to decide Type B vs. a genuinely empty Type A vault.

### Step 2: Extract all open tasks and headings

One Grep call, scoped tightly to action-bearing files. Do NOT scan the whole vault with `path: .` + `type: md` - that pulls in every README and reference doc (70KB+ on a moderately populated vault).

- `pattern`: `^(# |## |- \[ \])`
- `glob`: `{**/actions.md,**/network/*.md,**/contacts/*.md,**/people/*.md}` (flat alternates only - ripgrep does not support nested `{}` globs)
- `output_mode`: `content`
- `-n`: `true`
- `head_limit`: `0` (unlimited - missing a match means a wrong dashboard)

ripgrep returns lines like `path/to/file.md:5:## Heading` grouped by file in line-number order. Discard any match where the file path starts with `archive/` (historical, not actionable).

If the call returns zero matches, apply the Step 1b Type B check; if Type A, respond `No action-bearing files found in <cwd>.` and stop.

**Handle truncated lines.** ripgrep emits `[Omitted long matching line]` for results past its column-width limit - common in vaults with detailed one-line tasks (owner, rent amount, source-doc link, instructions all on one line), and it silently corrupts the dashboard. For each `(file, line)` pair flagged as omitted, recover the line with `Read` using `offset: <line>, limit: 1` - do not read the whole file.

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

Derive the **scope label** from the file path: strip the leading category folder (`projects/`, `areas/`, `resources/ideas/`) and the trailing `/actions.md` (action files) or `.md` (contact files). Preserve an intermediate subfolder when the leaf alone is ambiguous (e.g. a country code or short acronym). Examples:

- `projects/ticketing-platform-replacement/actions.md` → `ticketing-platform-replacement`
- `areas/finance/vat/actions.md` → `finance/vat`
- `areas/network/jan-claes.md` → `network/jan-claes`

If the path doesn't start with a known category folder, use the full relative path minus the trailing `/actions.md` or `.md`.

Final per-task record: file path (relative to CWD), line number, scope label, task text (stripped of all emoji markers and trailing whitespace), due/start/scheduled dates, priority, recurring cadence, and section heading (per the H2/H1 fallback rule above).

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

Use Glob to check whether `triage/` exists in the current vault. If it does, list its **direct file children** (top-level only - do not recurse; subdirectories like `triage/mail/` are not loose triage items). Capture filenames and a count. If the folder is missing or empty, omit the Triage section entirely.

**Do not parse file contents.** This is a pure file listing - the triage folder is a reminder, not a task source.

In a Type B vault this section is the *entire* output, with the title and read-only framing from Step 1b.

### Step 5c: Build the 🗓 Agenda from meetings.md

Type A vaults only. Meetings live one per line in the vault's `meetings.md`. Grep the current vault:

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

Use this exact layout, filtered to the sections the argument selects (see Arguments). **Omit any bucket that has zero items** - no empty placeholders. Always start with the H1 title line.

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

## Strict rules

- **Do NOT parse completed items (`- [x]`)** - they're history.
- **Do NOT rewrite actions.md files** to "fix" missing markers. If an item is undated, report it as undated; don't invent dates.
- **Do NOT follow links** into other files for extra context. The H2 section heading is sufficient.
- **Do NOT add commentary or recommendations** about what to do. Just present the dashboard. Decisions are the user's.
- **Do NOT include the `**Status:**` lines** from actions files.
- **Do NOT dedupe cross-referenced items** (same task mentioned in two files). Show both - the links let the user jump to either context.
- **Meetings (🗓 Agenda): today + future only, never invented.** Ignore past-dated, non-recurring meeting lines (history). Render only what the `meetings.md` line contains - never fabricate a meeting, time, or attendee.

## Edge cases

- **Vault with no actions.md files:** apply Step 1b. Type B → the Triage-only output, never "No actions.md files found." Type A with an empty/absent `triage/` → respond "No actions.md files found in <cwd>." and stop; Type A with a populated triage → render only the 📥 Triage section.
- **`triage/` missing or empty:** silently omit the Triage section.
- **File with only completed items:** skip silently, don't list it.
- **Item with both 🛫 future AND 📅:** goes in Waiting (not actionable yet).
- **Item with 🛫 in the past:** ignore the 🛫 (it was a gate that has opened); bucket by 📅 instead.
- **Recurring item without 📅:** still list in Recurring, show "next: -" placeholder.
- **Undated item with 🔺 priority:** still goes in Undated bucket, but retains 🔺 marker in output.
- **Malformed date** (e.g. `📅 2026-13-45`): skip the date, treat as undated, and note "(malformed date)" at end of line.

## Example output (fragment)

```
# Daily Brief - 2026-04-22

## 🔴 Overdue (2)
- 🔺 Score the two remaining ticketing vendor bids - [ticketing-platform-replacement:13](projects/ticketing-platform-replacement/actions.md#L13) · *Vendor selection* · 📅 2026-03-31 (22d ago)
- Jan to send the legacy POS transaction export - [cashless-stadium-rollout:7](projects/cashless-stadium-rollout/actions.md#L7) · *Data migration (critical path)* · 📅 2026-04-02 (20d ago)
```
