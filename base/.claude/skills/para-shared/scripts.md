# Running a skill's script

A skill with a `scripts/` folder opens by running its scan. The call is the skill's own; this is what every such call shares.

- **Launcher**: `python3`, or `py -3` on Windows, where `python3` is often a stub printing a Microsoft Store message.
- **Paths anchor to the skill's base directory**, never to the shell's working directory: the shared library is `<this skill's base directory>/../para-shared/scripts/paraos_vault.py`.
- **Redirect stdout to a file outside the vault** (the session's temp or scratch directory) and keep it for the run, unless the scan reports `saved_to`: it has kept that copy itself, and the path it names is the scan output. Inside a synced vault the output syncs and comes back as a hit in the next scan.
- **The output is one JSON document.** A scan never writes into the vault, asks, or decides a disposition.
- **The para-os clone** a scan reads masters from is `--clone <path>` where the operator names one, else `$PARAOS_HOME/para-os` (default `~/.paraos/para-os`), where `INSTALL.md` puts it. Neither there is "no clone found", its own state; never guess another path.
- **`--today YYYY-MM-DD` only when the operator names a date.** Left off, the script dates the run by the system clock; never pass a date from memory or context.
- **Fall back by hand** where Python is missing, the script or the shared library is missing, the script exits 2, or it exits non-zero with a code the skill does not name: run the reference the skill names as the scan's specification, and say in one line that the scan ran by hand.
- **Re-check before each delete or move**: `python3 "<this skill's base directory>/../para-shared/scripts/paraos_vault.py" changed <scan output path>` (Windows: `py -3`) reads the output's `snapshot` (top-level, or under the phase key a phased scan nests it in) and exits 1 when a file in it changed, or when a file arrived since in a folder its `snapshot_folders` lists (`arrived`). Re-read what `changed` names before acting on it, and never touch what `arrived` names, per [operating-discipline.md](operating-discipline.md#a-synced-vault-can-change-mid-run).
