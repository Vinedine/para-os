# Unattended triage: the routine

The prompt a scheduled task runs, after `/para-ingest`, for the vaults an operator has switched an action type on in. Set up the task only once `/para-triage auto` has run by hand in one vault and its report and quarantine manifest have been read end to end.

## Always allow, and nothing else

A scheduled task that asks for a permission stalls until someone answers it, so the task pre-approves exactly these, and nothing that deletes:

- `python3 <skills>/para-triage/scripts/triage_scan.py *` (`py -3` on Windows)
- `python3 <skills>/para-triage/scripts/auto_execute.py run *` and `auto_execute.py status *`
- Write `${PARAOS_HOME:-~/.paraos}/cache/triage/*-decisions.json`, the file a run hands the executor
- Read, Glob and Grep inside the registered vaults

## The prompt

> For each vault in `${PARAOS_HOME:-~/.paraos}/vaults.json` that is not retired: run `auto_execute.py status --vault-name <name> --vault <path>`, and skip the vault where `on` is empty or `kill_switch` or `nothing_new` is true. For every other vault, start one reader, scoped to that vault, that loads its own `CLAUDE.md` and runs `/para-triage auto` there. Then print each vault's report, failures first.

Nothing in a vault learns that another exists: each reader sees one vault.
