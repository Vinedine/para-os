---
type: llm
---

`./vault` already holds a `CLAUDE.md`, a README and filled project folders: it is an
existing vault. Step 1 of the kit's INSTALL.md says that in this case the install stops,
says so, and names `/para-upgrade` as the way to bring a vault up to date.

PASS if the reply says `./vault` is already a vault (or already holds a `CLAUDE.md`), stops
the install there, and names `/para-upgrade`.

FAIL if the reply goes on with the install (copies or proposes to copy the skeleton in, runs
or starts the bootstrap, asks the bootstrap's questions), or recommends overwriting or
replacing the existing `CLAUDE.md`.
