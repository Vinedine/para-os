# Integrations

Small, self-contained connectors that pull an outside system into a vault. Each drops a script into a vault's `resources/scripts/` and lands real Markdown (or files) where the assistant can read it alongside everything else.

An integration is **not** a [flavor](../flavors/). A flavor changes how a whole vault is consumed (e.g. `readonly-ipad` adds a render pipeline). An integration is an optional add-on that works with *any* vault regardless of flavor, and carries prerequisites (an app, an account, a platform) that not everyone has - which is why these live here and not in [`base/`](../base/), the dependency-free core everyone copies.

## The contract every integration follows

*Scripts live in the vault, their secrets don't* - the same rule stated in the main [README](../README.md).

| What | Where |
|---|---|
| Script(s) | `<vault>/resources/scripts/` - in the vault, version-controlled next to where they run |
| Credentials | `~/.paraos/secrets/<service>.{json,env}` - never syncs to a cloud drive or git remote |
| Regenerable output | `~/.paraos/cache/<service>/` - safe to delete anytime |
| Bulk working data | `~/.paraos/data/<name>/` - kept, but not vault-worthy |

The state root is `PARAOS_HOME` (default `~/.paraos`); no script hardcodes a home path. `~/.paraos/README.md` on each machine is the manifest of what's actually installed. The full convention for that destination folder - the buckets and the `PARAOS_HOME` resolver, with Python and Node snippets - is specified in [`base/resources/scripts/README.md`](../base/resources/scripts/README.md).

## Available

| Integration | Version | Pulls in | Stack | Platform |
|---|---|---|---|---|
| [`granola/`](granola/) | 2026.08.02 | Granola meeting notes + transcripts into `triage/` | Node 18+ | Windows |
| [`outlook/`](outlook/) | 2026.08.02 | Personal Outlook / Hotmail mail into `triage/`, plus ad-hoc mailbox search | Python 3.9+ | any |

## Versioning

An installed integration is a **copy**, so the vault needs a way to tell whether its copy is current. Every shipped script carries a marker in its header, in the same `YYYY.MM.NN` scheme as the [template revisions](../CHANGELOG.md):

```
para-os-integration: granola 2026.08.02
```

The version is **per integration, not per file**: every script in the folder carries the same one, stamped with the revision that folder's *code* last changed in. Bump it when a change is something an already-installed copy has to react to (a fixed API call, a new argument, a changed output path), and note the change under that revision's **Integrations** line in the changelog. A README rewording is not a bump.

`/para-upgrade` reads the marker in each script under a vault's `resources/scripts/`, compares it against the master's, and **reports** anything behind. It never overwrites a vault's copy: these scripts are meant to be edited in place (granola's routing table is an explicit "edit this block" section), so re-syncing one is a hand-merge with the changelog entry in front of you, not a file copy. A script with no marker is left alone and named as skipped.

## Adding one

1. Script goes in the vault it serves (`resources/scripts/`), never in `~/.paraos`.
2. Secret → `secrets/<service>`, cache → `cache/<service>/`, data → `data/<name>/`.
3. Resolve paths via `PARAOS_HOME`; don't hardcode `~/<something>`.
4. Stamp every script's header with `para-os-integration: <name> <revision>` (see **Versioning** above).
5. Ship a folder here: the script(s) plus a `README.md` covering prerequisites, one-time setup, and usage.
6. Add a row to the **Available** table above, and an **Integrations** line to the changelog entry for that revision.
7. Cover the folder's pure functions with tests next to the script (`test_*.py`, `*.test.js`; no runner or dependency beyond the language's built-in one), then run `python3 tools/check.py` from the repo root - it verifies the marker, the table row, and the revision all agree, and runs every integration's suite. A folder with no suite is a failure, as is one whose runtime is missing.
