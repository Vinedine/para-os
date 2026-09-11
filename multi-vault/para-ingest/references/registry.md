# The vault registry (Step 0)

`${PARAOS_HOME:-~/.paraos}/vaults.json` is the **single enumeration of vaults on this machine**. It lives outside every vault deliberately: a list of vaults held inside one of them would make that vault special, and would sync a machine fact into a shared folder.

## Shape

A JSON array of entries:

```json
{
  "name": "acme-client",
  "path": "C:/Users/<you>/Documents/acme-client",
  "kind": "engagement",
  "purpose": "The Acme engagement: delivery workstreams, their stakeholders, and anything the client is waiting on.",
  "active": true
}
```

| Field | What it is |
|---|---|
| `name` | The vault's folder basename. It is what ledger keys and run logs are keyed on, so it must match the folder exactly. |
| `path` | Absolute path to the vault root, the folder holding `CLAUDE.md` and `triage/`. |
| `kind` | A free-text label for the operator's own grouping. Nothing dispatches on it. |
| `purpose` | **The routing input.** One line saying what this vault is for, written for the router rather than for a human index. |
| `active` | `false` keeps the entry and takes the vault out of the run: no sources pulled, nothing routed to it. |

## `purpose` is the field that does the work

Everything else is bookkeeping. `purpose` is what a thread's subject and snippet are judged against when no contact hit decides, so a vague one ("work stuff") routes badly and a specific one routes well. Write it the way you would brief someone sorting your post: what belongs here, in the terms the post itself would use.

It complements rather than duplicates the vault's own `Relevant when` rules. Those are per-mailbox and live in the vault; `purpose` is per-vault and lives here, and is the only thing available for a vault that declares no sources at all.

## Reading it

- **Missing registry:** there is nothing to ingest for. Say so, point at `vaults.json.template` in the module README, stop. **Never glob a directory to guess the list** - a guessed list quietly includes things that are not vaults and quietly misses ones that are.
- **Malformed JSON:** stop and say which entry failed. Do not proceed on a partially parsed list: the vaults that dropped out would be silently unrouted, which looks exactly like a quiet day.
- **Path not mounted** (a network drive, an unsynced client library, an external disk): record an error row for that vault, route nothing to it, and continue the run. `active: true` with an absent path is an error, not an implicit `false`.

  **Route *to* it as normal, then withhold the ledger entry.** An unmounted vault is still a routing destination: work out that a thread belongs to it, fail to deliver, and record that failure as `undelivered` rather than pretending the thread routed nowhere. The rule that keeps such a thread alive is in [staging.md](staging.md): a thread routed to a vault that could not be written gets **no ledger entry at all**, so the next run refetches it and delivers the moment the path is back. Ledgering it instead is how a routed item disappears for good, and one unmounted drive can take several vaults with it.

  **A whole drive can vanish at once.** The four vaults on one shared drive are four registry rows and one failure, so report the failure as the drive and expect the count of mounted vaults to move in steps rather than by one. A run that finds noticeably fewer vaults than the previous run found is reporting an outage, not a quiet day.
- **A path that exists but holds no `CLAUDE.md`:** same treatment. It is registered as a vault and is not one.

## Never register

- **A mirror, a backup, or any one-way copy.** It is overwritten by its next sync, so a note staged there is destroyed and the item is then routed nowhere with nothing left to show it was lost. This is the one registry mistake with no visible symptom.
- **A vault someone else writes.** Routing an item into a shared library puts your post in front of its members.
- **A folder that merely looks like a vault** (an old skeleton, a template, an examples folder). If nobody triages it, staging into it is a slow leak.
