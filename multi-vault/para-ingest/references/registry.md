# The vault registry

`${PARAOS_HOME:-~/.paraos}/vaults.json` is the **single enumeration of vaults on this machine**. It lives outside every vault deliberately: a list of vaults held inside one of them would make that vault special, and would sync a machine fact into a shared folder.

## Shape

A JSON array of entries:

```json
{
  "name": "acme-client",
  "path": "C:/Users/<you>/Documents/acme-client",
  "purpose": "The Acme engagement: delivery workstreams, their stakeholders, and anything the client is waiting on.",
  "active": true
}
```

| Field | What it is |
|---|---|
| `name` | The vault's name, which ledger keys and run logs are keyed on. |
| `path` | Absolute path to the vault root, the folder holding `CLAUDE.md` and `triage/`. |
| `purpose` | **The routing input.** One line saying what this vault is for, written for the router rather than for a human index. |
| `active` | `false` keeps the entry and takes the vault out of the run: no sources pulled, nothing routed to it. A vault someone else writes is `false` unless its writers agreed to receive routed items. |
| `machine` | Optional. Who pulls the vault, where that is another machine; absent means this one. It takes the vault out of this skill's run whatever `active` says, and `/para-global-brief` shows its health with no triage count. |
| `retired` | Optional. The date the vault's work ended, `YYYY-MM-DD`; absent while it is live. It takes the vault out of this skill's run, and `/para-audit` and `/para-global-brief` list it as retired and read nothing in it. |
| `brief` | Optional. `"summary"` has `/para-global-brief` sum a vault you keep (counts by area and its top items) instead of listing every item, for one whose volume would bury the rest. |

## `purpose` is the field that does the work

Everything else is bookkeeping. `purpose` is what a thread's subject and snippet are judged against when no contact hit decides, so a vague one ("work stuff") routes badly and a specific one routes well. Write it the way you would brief someone sorting your post: what belongs here, in the terms the post itself would use.

It complements rather than duplicates the vault's own `Relevant when` rules. Those are per-mailbox and live in the vault; `purpose` is per-vault and lives here, and picks among the vaults that declared a mailbox without ever adding one.

## Never register

- **A mirror, a backup, or any one-way copy.** It is overwritten by its next sync, so a note staged there is destroyed and the item is then routed nowhere with nothing left to show it was lost. This is the one registry mistake with no visible symptom.
- **A folder that merely looks like a vault** (an old skeleton, a template, an examples folder). If nobody triages it, staging into it is a slow leak.
