---
name: para-audit
description: Read every vault the registry lists and report in one table how each stands against the para-os template - revision, declared type, machine-read lines and roster roles, rule files, integration scripts, bundled skill copies, CLAUDE.md sections and size - every finding with its fix, closing on the vault to upgrade first. Never writes to a vault. Use when the operator runs several vaults and asks to "audit all my vaults", "which of my vaults are behind", "are my vaults up to date", "which vault should I upgrade first", or types /para-audit.
allowed-tools: Bash(python3 *), Bash(py *), Glob, Grep, Read
argument-hint: '[ref=<git-ref>] [--clone <path>] [--test]'
---

# Fleet audit

Reads every vault the registry lists and reports, in one table, how far each has drifted from the para-os template. Every finding names its fix, which is nearly always `/para-upgrade` run in that vault.

**It never writes to a vault**, not even a fix the operator approves on the spot: `/para-upgrade` owns every write inside one.

- **It needs `para-shared/` and `para-upgrade/` beside it.** Its scan runs over their scripts, and its `../para-shared/` links resolve only there.
- **Run it from anywhere.** Like `/para-ingest`, it is not scoped to the cwd: the registry outside the vaults is what tells it they exist.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Every registered vault against `origin/stable` in the default clone |
| `ref=<git-ref>` | Read every master at this committed ref instead, such as `origin/main` or a revision branch. A working-tree path is refused. |
| `--clone <path>` | Read this para-os clone, per [para-shared/scripts.md](../para-shared/scripts.md) |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

A leftover argument follows [para-shared/operating-discipline.md](../para-shared/operating-discipline.md#arguments). A para-os home the operator names in prose, the folder holding `vaults.json`, replaces `${PARAOS_HOME:-~/.paraos}` for the run.

## Step 1: Run the scan

Per [para-shared/scripts.md](../para-shared/scripts.md):

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/audit_scan.py" [--clone <path>] [--ref <git-ref>] [--paraos-home <folder holding vaults.json>] [--app-tasks <file>] > <scan output path>
```

Where this session has the scheduled-tasks tool, save its task list as JSON beside the scan output and pass it as `--app-tasks`.

**Exit codes**: 0 answered; 3 no registry, or one listing nothing: say so, point at `vaults.json.template` in the multi-vault README, and stop; 4 the clone or the ref cannot be read (ask for a clone path or a ref that resolves, never guess one); 5 no ref named and the clone has no `origin/stable`: ask the operator to switch the clone to `stable`, then scan again. With no clone found (`clone.error`), every vault is still audited and its revision, rules, integrations, skills and sections read `not judged`: say so, and ask for the clone's path to judge them.

The output holds `master` (the ref, its revision, `in_development`), `tasks`, `vaults` (one row per audited vault: a `cells` value per column, `revision`, `findings` each with `detail`, `fix` and `route`, and `observations`), `excluded`, `drives` and `upgrade_first`. Every field and rule is in the script's docstring.

## Step 2: Report

In this order, and nothing else:

1. **The master, in one line**: the ref and its revision. Where `in_development` is set, one more line: a newer revision is in development in the clone's working tree, and it is not the bar.
2. **One table, one row per audited vault**, in registry order: `Vault`, then `Revision`, `Type`, `Declarations`, `Rules`, `Integrations`, `Skills`, `Sections`, `Size`, each cell as the scan gives it. An inactive vault is a row like any other.
3. **Excluded**: every `excluded` entry with its status (`UNREACHABLE`, `INVALID`) and its reason. A `drives` row is one line naming the drive as the cause, above the vaults it took with it, never its vaults as separate failures. With nothing excluded, say so in one line.
4. **Fixes**, per vault with findings: each finding's `detail` and `fix`. A vault's `observations` follow under their own label, never as defects.
5. **Scheduled runs**: each `tasks.findings` entry's `detail` and `fix`, or one line saying the task registry matches. Where `app_compared` is false, say the app's own list was not read.
6. **One closing line** naming `upgrade_first` and why: revisions behind, then findings. Where it is null, say no vault needs `/para-upgrade`; where no revision could be judged, say which vault goes first cannot be told.

What a finding means for the operator, beyond its cell: [references/checks.md](references/checks.md#reading-the-findings).

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Size is an adherence finding.** Never present extraction as a token saving.

## Related skills

- `/para-upgrade` - applies every finding routed to it, one vault at a time. Run it in the vault this skill names first.
- `/para-ingest` - the registry's other reader. `active: false` or a `machine` takes a vault out of it, never out of this audit.
