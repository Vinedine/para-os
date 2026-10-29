# Unattended triage: the routine

The prompt a scheduled task runs, after `/para-ingest`, for the vaults an operator has switched an action type on in. It skips a vault with nothing switched on, so it can be set up with the vault; read the first run after a switch end to end, report and quarantine manifest.

## Always allow, and nothing else

A scheduled task that asks for a permission stalls until someone answers it, so the task pre-approves exactly these, and nothing that deletes:

- `python3 <skills>/para-triage/scripts/triage_scan.py *` (`py -3` on Windows)
- `python3 <skills>/para-triage/scripts/auto_execute.py run *` and `auto_execute.py status *`
- Write `${PARAOS_HOME:-~/.paraos}/cache/triage/*-decisions.json`, the file a run hands the executor
- Read, Glob and Grep inside the registered vaults
- `python3 <skills>/para-ingest/scripts/funnel_page.py *` (`py -3` on Windows) and the Artifact publish of the page it writes

## The prompt

> For each vault in `${PARAOS_HOME:-~/.paraos}/vaults.json` that is not retired: run `auto_execute.py status --vault-name <name> --vault <path>`, and skip the vault where `on` is empty or `kill_switch` or `nothing_new` is true. For every other vault, start one reader, scoped to that vault, that loads its own `CLAUDE.md` and runs `/para-triage auto` there. Then print each vault's report, failures first, and rebuild and publish the funnel page as `/para-ingest`'s last step does.

Nothing in a vault learns that another exists: each reader sees one vault.
