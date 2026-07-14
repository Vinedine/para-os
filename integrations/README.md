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

The state root is `PARAOS_HOME` (default `~/.paraos`); no script hardcodes a home path. `~/.paraos/README.md` on each machine is the manifest of what's actually installed. The full convention for that destination folder - the buckets and the `PARAOS_HOME` resolver, with Python and Node snippets - is specified in [`base/skeleton/resources/scripts/README.md`](../base/skeleton/resources/scripts/README.md).

## Available

| Integration | Pulls in | Stack | Platform |
|---|---|---|---|
| [`granola/`](granola/) | Granola meeting notes + transcripts into `triage/` | Node 18+ | Windows |

## Adding one

1. Script goes in the vault it serves (`resources/scripts/`), never in `~/.paraos`.
2. Secret → `secrets/<service>`, cache → `cache/<service>/`, data → `data/<name>/`.
3. Resolve paths via `PARAOS_HOME`; don't hardcode `~/<something>`.
4. Ship a folder here: the script(s) plus a `README.md` covering prerequisites, one-time setup, and usage.
5. Add a row to the **Available** table above.
