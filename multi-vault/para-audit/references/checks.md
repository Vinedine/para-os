# The audit, in judgment

`scripts/audit_scan.py` runs every check over the shared vault library and `/para-upgrade`'s scan, and its docstring states each rule. This file is the judgment its output leaves to the skill.

## Reading the findings

- **`route: upgrade`** resolves with `/para-upgrade` run in that vault: say it once per vault, not once per finding.
- **A topic-file observation** may be a convention the vault grew on purpose. Report it, never as a defect.
- **Size** is about how reliably a session follows the file. The template's lever is extracting procedure to `.claude/rules/` with a one-line pointer left behind, never cutting the vault's own rules.
