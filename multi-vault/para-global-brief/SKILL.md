---
name: para-global-brief
description: One brief across every vault the registry lists - each vault's open, overdue, due-this-week, undated and triage counts, the most urgent items across vaults with their vault named, and one next action. Read-only. Use when the operator runs several vaults and asks "what's going on across my vaults", "what's urgent everywhere", "brief me on all my vaults", or types /para-global-brief.
allowed-tools: Bash(python3 *), Bash(py *), Read
argument-hint: '[--test]'
---

# Global brief

One view across every registered vault, so an operator with several does not run `/para-daily-brief` in each. **It never writes**, to a vault or anywhere else.

- **It needs `para-audit/`, `para-daily-brief/` and `para-shared/` beside it.** Its scan runs over their scripts.
- **Run it from anywhere.** The registry, `${PARAOS_HOME:-~/.paraos}/vaults.json`, is the only list of vaults. A para-os home the operator names in prose replaces it for the run.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Every registered vault |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

A leftover argument follows [para-shared/operating-discipline.md](../para-shared/operating-discipline.md#arguments).

## Step 1: Run the scan

Per [para-shared/scripts.md](../para-shared/scripts.md):

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/global_scan.py" [--paraos-home <folder holding vaults.json>] > <scan output path>
```

Exit 3: no registry, or one listing nothing. Say so, point at `vaults.json.template` in the multi-vault README, and stop. The output's fields are in the script's docstring.

## Step 2: Report

Everything comes from the scan. Read no vault's files.

1. **One table, one row per vault**, in registry order: `Vault`, `Open`, `Overdue`, `This week`, `Undated`, `Triage`, and `Flags` naming the flags fired. Where `proposal` is set, the row says a triage proposal is waiting.
2. **Urgent**: the `urgent` items, at most ten, each tagged with its vault. With more, count the rest per vault.
3. **Excluded**: every `excluded` entry with its status and reason, or one line saying none was.
4. **One next action**, closing the brief: the single item to do first, its vault named, and the vault to open `/para-daily-brief` in for the rest.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Never drop a vault silently.** A vault left out reads exactly like one with nothing due.
