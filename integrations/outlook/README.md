# Outlook / Hotmail mail sync

Pull relevant mail from a Microsoft account - personal (outlook.com, hotmail.com, live.com) or a Microsoft 365 work mailbox - into a vault's `triage/` as dated Markdown notes, one file per message. From there `/para-triage` files each where it belongs. A second mode, `search`, answers ad-hoc questions against the same mailbox without writing anything.

```
Outlook.com  ──▶  outlook.py sync --write  ──▶  <vault>/triage/20260728 ....md  ──▶  /para-triage files it
             └──▶  outlook.py search "..."  ──▶  stdout only, nothing written
```

Personal Microsoft accounts no longer accept Basic Auth or app passwords, so OAuth2 is the only way in: the device-code flow, delegated `Mail.Read`, no client secret. **Read-only against the mailbox**: it never sends, deletes, or marks mail read. One Entra app registration (the `consumers` authority) serves any number of personal accounts; a Microsoft 365 work mailbox needs its own tenant's app instead, passed per account (see Install).

## Prerequisites

- **Python 3.9+** and `requests` (`pip install requests`). Examples below use `python3`; on Windows `py` works in its place.
- **An Entra app registration** - public client, delegated `Mail.Read` + `offline_access`, with "Accounts in any organizational directory and personal Microsoft accounts" (or personal-only) enabled. You need its **client id**; there is no secret.
- One device-code login **per mailbox**, once per machine. Auth is machine-global, so adding another vault later needs no re-login.

## Install

1. Copy `outlook.py` into the vault you want mail to land in, at `resources/scripts/`.
2. Create `resources/scripts/outlook.config.json` next to it - which mailboxes feed *this* vault, plus their filters (see [Filtering](#filtering)):
   ```json
   { "accounts": ["someone@hotmail.com"], "keywords": ["invoice", "contract"] }
   ```
   Not named `outlook.json`: that is the machine-global **secret** below, and two files sharing one name across opposite trust zones is how a credential ends up inside a synced vault.
3. Create `~/.paraos/secrets/outlook.json` with your client id:
   ```json
   { "client_id": "00000000-0000-0000-0000-000000000000", "authority": "consumers", "accounts": {} }
   ```
4. Log in once per mailbox: `python3 outlook.py login someone@hotmail.com`
   A Microsoft 365 mailbox needs its own tenant's app: `python3 outlook.py login someone@company.com --client-id <app> --authority <tenant-id>`. A personal-accounts app is registered against the `consumers` authority, which refuses work accounts outright, so both settings resolve per account.

## Commands

| Command | What it does | Writes? |
|---|---|---|
| `login <email>` | Device-code login for one mailbox | secret file only |
| `accounts` | List configured mailboxes | no |
| `sync [--days N] [--write]` | Filtered pull into `triage/`. **Dry run by default** | `triage/` + ledger, only with `--write` |
| `search <query> [--limit N] [--body] [--all-mailboxes]` | Ad-hoc keyword search across the whole mailbox | **never** |
| `raw <graph-path>` | Raw Graph GET, for debugging | no |

`sync` is the default command, so a bare `outlook.py --write` still runs a sync and the `/para-triage` sync-script convention works unchanged.

### `sync` vs `search`

They answer different questions and deliberately use different Graph paths.

- **`sync`** walks a **day window** (`$filter` on `receivedDateTime`) and applies the vault's relevance filter: the keywords from `outlook.config.json`, plus an allowlist rebuilt on every run from every email address mentioned in `areas/network/*.md`. Adding a contact automatically widens what gets through. Good for "what arrived lately that this vault should know about".
- **`search`** hits the server-side index (`$search`) and **ignores both relevance filters** - the whole point is to ask something the filter would never have surfaced. It still respects the vault's *account* list, so a session in one vault never prints another's mail; `--all-mailboxes` widens it to every mailbox on the machine. Graph rejects `$search` combined with `$filter` or `$orderby`, so there is no date window and results come back ranked by relevance, not newest-first. It returns in seconds however far back the match lies, which a day-window walk cannot do across years of mail.

```
python3 outlook.py search "supplier name"
python3 outlook.py search "contract renewal" --account someone@hotmail.com --limit 20 --body
```

Because `$search` matches message bodies too, expect some loose hits; skim the dates and senders rather than trusting rank.

## Filtering

Two gates decide what `sync` files. A **contact allowlist**, rebuilt on every run from every email address mentioned in `areas/network/*.md` - so adding a contact automatically widens what gets through, and nothing about it is stored. And a **keyword filter**, from `outlook.config.json`. Either one matching is enough.

The keyword filter resolves **per mailbox**, because one vault can be fed by mailboxes of opposite shapes. A dedicated engagement mailbox *is* the filter: everything in it is in scope, and keywords there only subtract while adding silent-drop risk. A shared `info@` funnel is the reverse: a week can be four figures of mail, and the filter is the only thing between it and a `triage/` folder abandoned in its first week.

The simple form applies one filter to every mailbox:

```json
{ "accounts": ["someone@hotmail.com"], "keywords": ["invoice", "contract"] }
```

Give `accounts` an object to filter per mailbox instead. Each setting falls back **independently** to the vault-level default, so a block that only tightens `keywords` keeps the vault's other choices:

```json
{
  "keywords": ["invoice", "contract"],
  "accounts": {
    "engagement@company.com": { "match_all": true },
    "info@company.com":       { "keywords": ["offerte", "bestelling"] }
  }
}
```

| Setting | Default | What it does |
|---|---|---|
| `keywords` | `[]` | Words matched case-insensitively against the message |
| `match_all` | `false` | Take every message. The explicit catch-all |
| `match_body` | `true` | Match keywords against `bodyPreview` as well as the subject |

Three things worth knowing before you write one:

- **Emptying `keywords` does not mean "file everything".** It leaves the contact allowlist as the only gate, which is *stricter*, not looser. Use `"match_all": true`, which is also the right setting for a dedicated mailbox and for calibrating a new one.
- **Subject-only matching has a systematic blind spot.** It drops any message whose subject is in a language your keywords are not written in - and a dropped message leaves no trace, so you never find out. That is why `match_body` defaults to on.
- **A drafted filter is a hypothesis until it has run against real traffic.** Run `sync` without `--write` over a real window and read what it catches. Prefer distinguishing words: a company's own name matches nearly everything in that company's mailbox, so it is noise dressed as precision.

The filter shapes **only what `sync` files unasked**. `search` ignores it entirely and queries the whole mailbox, which is the point of a search.

## Where state lives

The script is code, so it lives in the vault. Its runtime state does not - a secret written inside a vault leaks the moment that vault syncs.

| Path | Holds |
|---|---|
| `~/.paraos/secrets/outlook.json` | client id + per-account OAuth refresh tokens, rewritten each run (the provider rotates them); written atomically, one account at a time, so parallel runs don't clobber each other |
| `~/.paraos/cache/outlook/synced.json` | dedup ledger, keyed by message id → the vaults it has already been filed to |
| `<vault>/resources/scripts/outlook.config.json` | that vault's accounts + filters. Version-controlled with the vault; no secret ever lives here. The pre-2026.08.03 name `outlook_sync.json` is still read, with a notice |

Both `~/.paraos` paths honour the `PARAOS_HOME` environment variable.

## Per-vault copy, shared state

**This directory is the canonical copy.** The script holds nothing vault-specific - accounts and filters in the `.json` beside it, credentials in `~/.paraos/secrets/`, the vault derived from the copy's own path - so propagating a change is a **straight file copy**, and your config survives it. Configure a vault through its `.json`, never by editing the script: an edit to the script is what the next resync silently discards.
