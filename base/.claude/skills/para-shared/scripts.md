# Running a skill's script

A skill with a `scripts/` folder opens by running its scan. The call is the skill's own; this is what every such call shares.

- **Launcher**: `python3`, or `py -3` on Windows, where `python3` is often a Store stub.
- **Paths anchor to the skill's base directory**, never the shell's working directory: the shared library is `<this skill's base directory>/../para-shared/scripts/`.
- **Redirect stdout to a file outside the vault** and keep it for the run, unless the scan reports `saved_to`, which is then the scan output; inside a synced vault the output syncs and comes back as a hit.
- **The output is one JSON document.** A scan never writes into the vault, asks, or decides a disposition.
- **The para-os clone** is `--clone <path>` where the operator names one, else `$PARAOS_HOME/para-os` (default `~/.paraos/para-os`). Neither there is "no clone found", its own state.
- **`--today YYYY-MM-DD` only when the operator names a date**; otherwise the script dates the run by the system clock.
- **Fall back by hand** where Python, the script or the shared library is missing, the script exits 2, or it exits with a code the skill does not name: run the reference the skill names as the scan's specification, and say in one line that the scan ran by hand.
- **Re-check before each delete or move**: `paraos_vault.py changed <scan output path>`, per [operating-discipline.md](operating-discipline.md#a-synced-vault-can-change-mid-run).
