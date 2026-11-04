# Unattended triage: the routine

The prompt a scheduled task runs, after `/para-ingest`, for the vaults an operator has switched an action type on in. It skips a vault with nothing switched on, so it can be set up with the vault; read the first run after a switch end to end, report and quarantine manifest.

List the task in `${PARAOS_HOME:-~/.paraos}/tasks.json`, from [tasks.json.template](tasks.json.template): its schedule, and anything it reads beyond the sources the vaults declare, with the connection it goes through. The fields are in `para-shared/scripts/paraos_runs.py`, and `/para-audit` reports a scheduled task the file misses or whose schedule differs.

## Always allow, and nothing else

A scheduled task that asks for a permission stalls until someone answers it, so the task pre-approves exactly these, and nothing that deletes:

- `python3 <skills>/para-triage/scripts/triage_scan.py *` (`py -3` on Windows)
- `python3 <skills>/para-triage/scripts/auto_execute.py run *` and `auto_execute.py status *`
- Write `${PARAOS_HOME:-~/.paraos}/cache/triage/*-decisions.json`, the file a run hands the executor
- Read, Glob and Grep inside the registered vaults
- `python3 <skills>/para-ingest/scripts/funnel_page.py *` (`py -3` on Windows) and the Artifact publish of the page it writes
- `python3 <skills>/para-shared/scripts/paraos_runs.py record *`

## The prompt

> For each vault in `${PARAOS_HOME:-~/.paraos}/vaults.json` with no `machine`: run `auto_execute.py status --vault-name <name> --vault <path>`, and skip the vault where `on` is empty or `kill_switch` or `nothing_new` is true. For every other vault, start one reader, scoped to that vault, that loads its own `CLAUDE.md` and runs `/para-triage auto` there. Then print each vault's report, failures first, and rebuild and publish the funnel page as `/para-ingest`'s last step does. Last, run `paraos_runs.py record --task <this task's id> --status ok|failed|partial --summary "<one line: what was staged and filed>"`.

Nothing in a vault learns that another exists: each reader sees one vault.
