# Scanning, parsing and bucketing tasks (Steps 2 to 4b)

Everything between "the vault is a folder of markdown" and "a set of bucketed, per-entity task records". Mechanical: no judgment lives here.

## Step 2: Extract all open tasks and headings

One Grep call, scoped tightly to action-bearing files. Do NOT scan the whole vault with `path: .` plus `type: md` - that pulls in every README and reference doc.

- `pattern`: `^(# |## |- \[ \])`
- `glob`: `{**/actions.md,**/network/*.md,**/contacts/*.md,**/people/*.md}` (flat alternates only - ripgrep does not support nested `{}` globs)
- `path`: `.` - the vault root, which is the CWD
- `output_mode`: `content`, `-n`: `true`, `head_limit`: `0` (unlimited - missing a match means a wrong dashboard)

ripgrep returns lines grouped by file in line-number order. **Discard any match whose path starts with `archive/` or `resources/`** (the vault's "Where a checkbox may live" rule) - but **count what you discard**, per bucket: it feeds a health flag. Post-filter, never anchor the glob to `projects/**/`: a root-anchored alternate silently matches nothing when `path` is not the vault root.

If the call returns zero matches, apply the SKILL.md Step 1b type check; if Type A, respond `No action-bearing files found in <cwd>.` and stop.

**Handle truncated lines.** ripgrep emits `[Omitted long matching line]` past its column-width limit. For each `(file, line)` pair flagged as omitted, recover it with `Read` using `offset: <line>, limit: 1` - do not read the whole file.

## Step 3: Associate tasks with headings, parse markers

For each surviving file, walk its lines in order, maintaining two cursors:

- `currentH1` - most recent `# ` heading seen
- `currentH2` - most recent `## ` heading since the last H1 (reset to null on H1)

For each line: `# <text>` sets `currentH1` and resets `currentH2`; `## <text>` sets `currentH2`; `- [ ] <text>` emits a task with section = `currentH2`, unless that is literally `Next actions` (case-insensitive), in which case `currentH1`. `- [x]` lines never match the regex.

Parse markers from each task line:

| Marker | Regex | Meaning |
|---|---|---|
| Due date | `📅 (\d{4}-\d{2}-\d{2})` | Hard deadline |
| Start date | `🛫 (\d{4}-\d{2}-\d{2})` | Not actionable until this date |
| Scheduled | `⏳ (\d{4}-\d{2}-\d{2})` | Planned work date - the effective date when there is no `📅` |
| Recurring | `🔁 (every [^📅🛫⏳🔺🔼🔽⏬\n]+)` | Cadence pattern |
| Priority | `[🔺🔼🔽⏬]` | 🔺 highest to ⏬ lowest; no marker means medium |

Derive the **scope label** from the file path: strip the leading category folder (`projects/`, `areas/`) and the trailing `/actions.md` or `.md`, preserving an intermediate subfolder when the leaf alone is ambiguous. Record which bucket the file came from (`projects/` vs `areas/`) - the dashboard shows it.

Final per-task record: file path, line number, bucket, scope label, task text (stripped of emoji markers), dates, priority, cadence, section heading.

## Step 4: Bucket against today

Let `T` be today. Let `D` be the task's effective date: its `📅` if present, else its `⏳`.

| Bucket | Condition |
|---|---|
| 🔴 Overdue | has `D` AND `D < T` |
| 🟠 Today | has `D` AND `D == T` |
| 🟡 This week | has `D` AND `T < D <= T+7` |
| 🔵 Next 30 days | has `D` AND `T+7 < D <= T+30` |
| ⚪ Later | has `D` AND `D > T+30` |
| 🔁 Recurring | has `🔁` - classify here regardless of `D` |
| ⏳ Waiting | has `🛫` AND `🛫 > T` |
| ❓ Undated | no `D`, no `🔁`, no *future* `🛫` |

A **past `🛫`** (start-gate already open) is not "waiting": ignore it and bucket by `D`, else Undated. Only a *future* `🛫` routes to Waiting. **Precedence:** Recurring > Waiting > date-based. In the `overdue` scope, overdue recurring items also appear in 🔴, tagged `🔁`.

## Step 4b: Aggregate per entity

Group the task records by scope label. **Aggregate all contact files into one `network` row** (with the file count) - one row per person floods the dashboard. Per entity compute: bucket (`[P]` / `[A]`), open count, overdue count, dated count (has `D` or `🔁`), undated count.

Get each action file's last-modified date in one Bash call (`stat -c '%y' <files>` on Linux or Git Bash, `stat -f '%Sm'` on macOS; fall back to `ls -l --time-style=+%Y-%m-%d`). Filesystem mtime, not git - it works in every vault, including ones without `.git`.
