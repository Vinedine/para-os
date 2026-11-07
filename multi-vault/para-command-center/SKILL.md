---
name: para-command-center
description: Build and publish the Command Center, one page across every vault the registry lists - today's meetings, what is late or due, a map of every vault by neighbourhood and street with what came in this week and where it went, the scheduled runs, the repos and websites, and the weeks ahead. A script builds it from files on disk; the skill only reads the calendars and publishes. Read-only. Use when the operator runs several vaults and asks to "refresh the command center", "show me everything at once", "where do all my vaults stand", or types /para-command-center.
allowed-tools: Bash(python3 *), Bash(py *), Read, Write, Artifact, ToolSearch, mcp__google-workspace__list_calendars, mcp__google-workspace__get_events
argument-hint: '[--offline] [--test]'
---
<!-- reviewed with: claude-opus-5-5 -->

# Command Center

One page across every registered vault, built by a script from files on disk, so the same files always give the same page. **The skill adds no judgment to it: it reads the calendars, runs the script and publishes.** It writes nothing but the events file, the page and the page's data in `${PARAOS_HOME:-~/.paraos}/cache/command-center/data.json`.

- **It needs `para-audit/`, `para-daily-brief/`, `para-ingest/` and `para-shared/` beside it.**
- **Run it from anywhere.** The registry, `${PARAOS_HOME:-~/.paraos}/vaults.json`, is the only list of vaults. A para-os home the operator names in prose replaces it for the run.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Build the page and publish it |
| `--offline` | Pass it to the build: no `git fetch` and no `gh`, each repo's state as it is on disk |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

A leftover argument follows [para-shared/operating-discipline.md](../para-shared/operating-discipline.md#arguments).

## Step 1: List the calendars

Per [para-shared/scripts.md](../para-shared/scripts.md):

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/command_center.py" --calendars [--paraos-home <folder holding vaults.json>]
```

Exit 3: no registry, or one listing nothing. Say so, point at `vaults.json.template` in the multi-vault README, and stop. It prints `today`, `horizon` and `calendars`, one row per calendar account with the `vaults` that declare it.

## Step 2: Read the calendars

Each of `calendars` once, per [para-shared/connectors.md](../para-shared/connectors.md#calendar), from `today` to `horizon`, starts in the operator's time zone ([timestamps.md](../para-shared/timestamps.md)), all-day "free" placeholders dropped. Each event becomes `{date, start, end, title, source}`, `source` the row's Source, plus `"recurring": true` where the calendar says so.

Write `{"events": [...], "note": "..."}` to `<scratch folder>/events.json`. `note` names each calendar that answered with an error and what failed, never silently out; leave it out when every calendar answered. With no calendar connector at all, write no file and say so in the report: the page then shows only the meetings the vaults keep in `meetings.md`.

## Step 3: Build the page

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/command_center.py" --events <scratch folder>/events.json --model <your own model id> --out <scratch folder>/command-center.html [--offline] [--paraos-home <folder>]
```

Leave `--events` out where Step 2 wrote no file. What the page holds, and the file each part comes from, is in the script's docstring. It prints one line of JSON: `out`, `page`, `publish`, `title`, `description`, `key` and `url`.

## Step 4: Publish and report

Publish per [para-shared/pages.md](../para-shared/pages.md), the printed `key` standing in for the vault root. Then report in chat, briefly: the page's link on one line, and each line of `meta.notes` in the data file as written, since those say what was missing or left out. The page is the report: restate none of it.

## Where a vault stands on the page

The page draws each vault as a building in a neighbourhood, on a street. Both come from the vault's registry entry:

| Field | What it is |
|---|---|
| `neighbourhood` | The group the vault belongs to, in the operator's words: whose it is, or what kind it is. |
| `street` | Optional. A theme within the neighbourhood, such as the client work or the household. |

An entry with neither stands in "Your vaults" where the operator keeps the vault, else in "Vaults you look after". Change either only when the operator asks, by editing `vaults.json`.

A vault that is no longer read, such as one handed over to a client, is not in the registry. To keep it on the page, list it in `${PARAOS_HOME:-~/.paraos}/past-vaults.json`, a list of `{"name", "ended", "neighbourhood", "street", "note"}`: it shows as handed over, with no grade and no counts.

## On a schedule

A morning routine runs this skill, and `/para-ingest` rebuilds the page as its last step so the inbound figures follow each run. Its entry in the task registry (`tasks.json`) names `"skill": "para-command-center"`; the page then shows that run among the scheduled runs.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Never add judgment to the page.** No next action, no summary and no ranking of its own: what the script computes is what the page shows.
- **Never invent a meeting, time or attendee**: an event holds only what a calendar answered.
- **Never read a vault's files yourself.** The script reads them; the skill reads calendars.
- **Calendars are read, never changed.**
- **One artifact.** Publish to the page's remembered link; never create a second one where the first exists.

## Related skills

- `/para-daily-brief` - one vault's own brief and dashboard.
- `/para-ingest` - fills the triage folders this page counts, and rebuilds the page after each run.
- `/para-audit` - how each vault stands against the kit, in full; the page shows its count on each health card.
