# Scanning, parsing and bucketing tasks (Steps 1b to 4b)

Everything between "the vault is a folder of markdown" and "a set of bucketed, per-entity task records". Mechanical: no judgment lives here.

`scripts/brief_scan.py` implements every rule below. What comes back:

| Field | Holds |
|---|---|
| `today` | The date the brief is dated by |
| `entity` | `status` of `resolved`, `ambiguous`, `elsewhere` or `unresolved`, with `match`, `candidates`, `elsewhere` and `nearest` (Step 1b) |
| `tasks` | One record per open item: file, line, bucket, scope, section, text, markers, `lane`, `days`, `also_lane`, `malformed_date` |
| `entities`, `totals` | Per-entity rows with the three counts that partition the open count and a `bar` width, and the same four numbers vault-wide |
| `lanes` | Each lane's `(file, line)` references, joined back into `tasks` for the counts a rendered section needs; a recurring item overdue or due today is in `recurring` and that lane too |
| `mentioned_elsewhere` | Under an entity scope only: open items naming it that live in another file |
| `file_dates` | Each action file's date, by the rule in [Step 4b](#step-4b-aggregate-per-entity) |
| `flags`, `ideas`, `triage`, `triage_preview`, `lifecycles` | Everything [signals.md](signals.md) computes from files |
| `review` | Under `--review` only: `window` (`start`, `end`, `days`), `done` (`count`, `undated`, `by_entity` rows of `items`), `slipped`, `moved` (one entry per lifecycle: `count`, `entities`), `stuck` (`overdue` references, `no_next_step` entities) and `decisions`, by [the review window](#the-review-window); null for an entity name that did not resolve |

Where the script cannot run, apply the rest of this file by hand.

## Step 1b: Resolve an entity scope

Runs only when the argument, or what follows `review` and its window, is not a reserved scope word **and reads like an entity name** (SKILL.md, Arguments). The scope words win on a collision, so an entity genuinely named `all` is reached by its path (`/para-daily-brief projects/all`).

Build the candidate list from the direct subfolders of `projects/` and `areas/`, one Bash call:

```bash
ls -d projects/*/ areas/*/ 2>/dev/null
```

Match the argument against those folder names, **case-insensitively and with every separator read as a hyphen** - a space, a dot or an underscore, so `Acme Website` is `acme-website` and a release-style name like `Para OS 2026.09.04` reaches `para-os-2026-09-04` - **in this order**, and stop at the first rule that yields exactly one:

1. **Exact** folder-name match. It wins even when the name is also a substring of others, which is what makes `acme-website` reachable in a vault that also holds `acme-website-v2`.
2. **Unique substring** match. `ticketing` resolves when it appears in one folder name.
3. Anything else is unresolved. **Do not pick.**

Then, by outcome:

- **One match** - scope everything downstream to it. Record its bucket (`[P]` / `[A]`) and its folder path; both are rendered.
- **Several matches** - list them, one per line, and ask which. Never rank them, never take the shortest.
- **No match** - before reporting, check `resources/ideas/<name>/` and `archive/` with one Glob each, so the answer can say *where the thing actually is* rather than that it does not exist. An idea holds no `actions.md` by the vault's own rule, and an archived entity holds none that is open; say which case it is. If it is nowhere, say so and list the three nearest folder names by substring overlap.

## Step 2: Extract all open tasks and headings

One Grep call, scoped tightly to action-bearing files. Do NOT scan the whole vault with `path: .` plus `type: md`.

- `pattern`: `^(# |## |- \[ \])`
- `glob`: `{**/actions.md,**/network/*.md,**/contacts/*.md,**/people/*.md}` (flat alternates only - ripgrep does not support nested `{}` globs)
- `path`: `.` - the vault root, which is the CWD
- `output_mode`: `content`, `-n`: `true`, `head_limit`: `0` (unlimited)

ripgrep returns lines grouped by file in line-number order. **Discard any match whose path starts with `archive/` or `resources/`** (the vault's "Where a checkbox may live" rule). Post-filter, never anchor the glob to `projects/**/`: a root-anchored alternate silently matches nothing when `path` is not the vault root.

**Both calls below are raw `Grep` patterns and therefore count fence content**, per **A quoted syntax is not a used syntax** in [operating-discipline.md](../../para-shared/operating-discipline.md): where a bucket's count is non-zero, read the matched files before reporting the number, or say in the output that it includes samples. A frozen-record note does not cover a fenced sample.

**Count the misplaced checkboxes with their own call**, not from what the discard above dropped - the glob above reaches only `actions.md` and contact files, so it cannot see an open checkbox in an archived meeting note or action plan. One Grep in `count` mode per bucket - `pattern`: `^- \[ \]`, `glob`: `**/*.md`, `path`: `archive` then `resources` - which names the files and their counts. Read each file with a non-zero count and drop the checkboxes inside a fence before the number feeds the flag.

If the call returns zero matches, SKILL.md's first edge case decides what renders.

**Handle truncated lines.** ripgrep emits `[Omitted long matching line]` past its column-width limit. Recover each `(file, line)` pair with `Read` using `offset: <line>, limit: 1`; once **more than 10** pairs are omitted, read the affected files whole instead, one call per file rather than one per line.

### Under an entity scope

Same call, two changes: `path` becomes the resolved entity folder (`projects/<name>` or `areas/<name>`) and `glob` narrows to `**/actions.md`, or to `*.md` where the entity is a contact area (`areas/network/`, `contacts/`, `people/`), whose items live in the contact files. Move the scope into `path`, **not** into the glob. The `archive/` and `resources/` discard no longer fires (the path cannot reach them), so the misplaced-checkbox flag is not computed under this scope.

**Then one more grep, for what is filed elsewhere.**

A task mentions the entity where a link on its line - the first or any further one - resolves into the entity's folder, or, only where the entity's name carries a hyphen, dot or space, where the name or its space/dot form appears as a whole word in the text; a single-token name (`network`, `quill`) is too common a word to trust and never matches by text, only by a link.

- `pattern`: `]\(` to find every link on a line, plus, for a multi-token name only, the name itself case-insensitive (`-i`) and its **space-separated** and **dot-separated** forms as whole words. **Always the full name, never a shortened stem or a date inside it.**
- `glob` and `path`: as the unscoped Step 2 call, then discard `archive/`, `resources/`, and the entity's own files
- Keep only `- [ ]` lines, and for a link match, resolve the target from the linking file's own folder and confirm it lands inside the entity's path before counting it

**Match paths separator-insensitively when discarding.** On Windows ripgrep returns `.\areas\para-os\actions.md`, so a filter written with `/` silently keeps the entity's own file and reports it as filed elsewhere. Normalise before comparing.

Render these under their own heading as **mentions, never as the entity's own work** - they belong to the file they live in, and their counts stay out of the entity's totals. Cap at five with a `(+N more)` line.

## Step 3: Associate tasks with headings, parse markers

For each surviving file, walk its lines in order, maintaining two cursors:

- `currentH1` - most recent `# ` heading seen
- `currentH2` - most recent `## ` heading since the last H1 (reset to null on H1)

For each line: `# <text>` sets `currentH1` and resets `currentH2`; `## <text>` sets `currentH2`; `- [ ] <text>` emits a task with section = `currentH2`, unless that is literally `Next actions` (case-insensitive), in which case `currentH1`. `- [x]` lines never match the regex.

Parse markers from each task line:

| Marker | Regex | Meaning |
|---|---|---|
| Due date | `📅️?\s*(\d{4}-\d{2}-\d{2})` | Hard deadline |
| Start date | `🛫️?\s*(\d{4}-\d{2}-\d{2})` | Not actionable until this date |
| Scheduled | `⏳️?\s*(\d{4}-\d{2}-\d{2})` | Planned work date - the effective date when there is no `📅` |
| Recurring | `🔁️?\s*(every [^📅🛫⏳🔺🔼🔽⏬\n]+)` | Cadence pattern |
| Priority | `[🔺🔼🔽⏬]` | 🔺 highest to ⏬ lowest; no marker means medium |

Each date and cadence marker may carry an invisible U+FE0F variation selector, the `️?` above.

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
| Waiting on others | text opens on `Waiting on` and has no `D`; its age is T less its `(since YYYY-MM-DD)` |
| ❓ Undated | no `D`, no `🔁`, no *future* `🛫` |

A **past `🛫`** (start-gate already open) is not "waiting": ignore it and bucket by `D`, else Undated. Only a *future* `🛫` routes to Waiting. **Precedence:** Recurring > Waiting > date-based, except that a recurring item whose `D` is past or today **also** appears in 🔴 or 🟠 tagged `🔁`, in every scope rather than only in `overdue`. It is still counted once, under Recurring.

## Step 4b: Aggregate per entity

Group the task records by scope label. **Aggregate all contact files into one `network` row** (with the file count). Per entity compute: bucket (`[P]` / `[A]`), open count, and three counts that **partition** it: **overdue**, **upcoming** (carries a `D`, a `🔁` or a future `🛫`, and is not overdue), **undated**. They sum to the open count wherever they are reported, the dashboard's bar segments included; never report a "dated" count that also contains the overdue ones.

Date each action file, and each idea brief for Step 4d, by its mtime, in one Bash call (`stat -c '%y' <files>` on Linux or Git Bash, `stat -f '%Sm'` on macOS; fall back to `ls -l --time-style=+%Y-%m-%d`), never by a folder. **A bulk write resets mtimes too:** where a file's mtime is within 60 seconds of at least two others of its kind, a checkout or sync wrote them together, so in a vault with `.git` date it by `git log -1 --follow --format=%as -- <path>` at its current path, unless `git status` shows it modified. A vault whose history lives in a separate one-way mirror runs that `git log` in the mirror instead. Where git returns nothing, the mtime stands, and the brief says those dates may be a sync's.

## The review window

Under `review` only. The window runs from its start to today, both counted in: `week` is the seven days ending today, `month` the thirty, `since <date>` every day from that date. Every rule reads the vault, or under an entity scope that entity's own folder.

- **Done**: each `- [x]` whose `✅ YYYY-MM-DD` falls in the window, in Step 2's files and, vault-wide, every `archive/**/actions.md`, grouped by entity as in Step 4b. A close in a live file with no `✅` is counted as undated and placed in no window; an archived one is not counted.
- **Slipped**: each open item whose `📅` falls in the window before today. A `⏳` is a plan, not a deadline.
- **Moved**: per declared lifecycle, each entity in its homes, terminal ones and closed register rows included, whose Stage line or Stage cell carries a `since <date>` in the window. No `since`, no move.
- **Stuck**: the 🔴 lane, and every entity with nothing open (signals.md Step 4c); under an entity scope, the entity itself when it has no open item.
- **Decisions**: each entry dated in the window in a development log, the section under a `Development log`, `Dev log`, `Decision log`, `Log` or `Decisions` heading (a trailing parenthetical aside) down to the next heading of its level, or a whole file so named (`development-log.md`), in any note under `projects/` or `areas/` outside a `sources/` folder. An entry is a line, list item, heading or table row opening on its date; a date alone on its line takes the next line as its text.
