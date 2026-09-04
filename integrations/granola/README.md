# Granola meeting sync

Pull your [Granola](https://www.granola.ai/) meetings - the enhanced notes *and* the full transcript - into a vault's `triage/` as dated Markdown notes, one file per meeting. From there `/para-triage` files each one where it belongs (the owning project's `sources/`, a contact, `archive/meetings/` when it spans several).

Granola holds a rich, growing record of every call you take. This integration lands that record in your vault as plain Markdown, so the assistant can read across your meetings the same way it reads everything else.

```
Granola app  ──▶  granola.js  ──▶  <vault>/triage/20260709 Kickoff call.md  ──▶  /para-triage files it
```

## Prerequisites

- **The Granola desktop app**, signed in, on the same machine. The sync reads the app's local login token; there is no separate API key to request.
- **[Node.js](https://nodejs.org/) 18+** (for the built-in `fetch`). No `npm install` - the scripts use only Node's standard library.
- **Windows.** `granola-auth-init.js` extracts the token from Granola's encrypted store via Windows DPAPI. macOS/Linux aren't supported yet (the store is unlocked differently there); everything else is cross-platform.

## Install

1. Copy both scripts into the vault you want meetings to land in:
   ```
   <vault>/resources/scripts/granola.js
   <vault>/resources/scripts/granola-auth-init.js
   ```
   The sync finds its vault from its own location (two levels up), so it must live under `resources/scripts/`.

2. **One-time auth.** With the Granola app running and signed in:
   ```
   node <vault>/resources/scripts/granola-auth-init.js
   ```
   This writes your token to `~/.paraos/secrets/granola.json` and prints your newest meeting as a sanity check.

3. **Dry run**, then write:
   ```
   node <vault>/resources/scripts/granola.js            # shows what it would write, touches nothing
   node <vault>/resources/scripts/granola.js --write    # creates the notes in triage/
   ```

4. Run `/para-triage` in the vault to file the new notes.

## Usage

```
node granola.js            # DRY RUN (default) - last 30 days
node granola.js --write    # create the notes
node granola.js --days 14  # override the look-back window
```

Re-runs are safe: a dedup ledger (`~/.paraos/cache/granola/synced.json`) and an existing-file check mean a meeting is never written twice. Delete a synced note and it will not come back unless you also clear it from the ledger.

Each note carries YAML front-matter (`title`, `date`, `granola_id`, `source: granola`, `attendees`), a `## Summary` (Granola's enhanced notes), and a `## Transcript` (speaker-attributed).

## The `~/.paraos` contract

This integration follows the para-os rule *scripts live in the vault, their secrets don't*:

| What | Where | Bucket |
|---|---|---|
| The two scripts | `<vault>/resources/scripts/` | (in the vault, version-controlled) |
| Login token | `~/.paraos/secrets/granola.json` | secret - never syncs to a cloud drive or git |
| Dedup ledger | `~/.paraos/cache/granola/synced.json` | cache - safe to delete, rebuilds |

The root is `PARAOS_HOME` (default `~/.paraos`). See [`integrations/README.md`](../README.md) and `~/.paraos/README.md`.

## Multiple vaults (optional)

Run several vaults and want one Granola account fanned out across them? Prefix your meeting titles by vault (e.g. `Acme - Steering`, `Home - Contractor`) and drop a `granola.config.json` next to the script, mapping each title prefix to its sibling vault folder (copy `granola.config.json.template` to start):

```json
{
  "meetings_subdir": "triage",
  "route": { "Acme": "acme-client", "Home": "family", "Side": "side-project", "Client": "." }
}
```

**`"."` means the vault this copy lives in**, and it is the value to reach for whenever a route target is this vault. Never write the folder's own name: a folder name is machine-local - the OneDrive client names a synced SharePoint library in *its own display language*, so one library is `Client Site - Documents` on an English machine and `Client Site - Documenten` on a Dutch one - while `granola.config.json` is version-controlled and syncs to everybody. A literal name is therefore right on at most one machine, and wrong in the worst way on the rest: an unmatched target is treated as another vault's meeting and skipped in silence, so the run still reports success while every meeting is dropped. `"."` is also the shape a single-tenant client vault needs, where the alternative - no `route` at all - takes *every* meeting and would file other clients' calls into that client's library. A target that names neither this vault nor an existing sibling now warns once at startup rather than disappearing per meeting.

With `route` set, each copy of the script writes only its own vault's meetings by default; `--vault X` targets another (and stops the run if nothing routes to `X`, rather than skipping every meeting and reporting success), `--all` writes every routed vault in one pass. The vaults must be sibling folders under one parent. Prefixes match case-insensitively, so `ACME - Steering` routes on an `Acme` key. Omit the file entirely - or leave `route` empty - and every meeting simply goes to the local vault, which is all a single-vault user needs.

**The config is a separate file on purpose.** With the table in `granola.config.json`, `granola.js` holds nothing vault-specific, so re-syncing an installed copy is a straight file copy that leaves the routing untouched. Keep it that way: configure the vault in the JSON, never in the script - an edit to the script is what the next resync silently discards.
