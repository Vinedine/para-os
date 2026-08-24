# Outlook / Hotmail mail sync

Pull relevant mail from a **personal** Microsoft account (outlook.com, hotmail.com, live.com) into a vault's `triage/` as dated Markdown notes, one file per message. From there `/para-triage` files each where it belongs. A second mode, `search`, answers ad-hoc questions against the same mailbox without writing anything.

```
Outlook.com  ──▶  outlook_sync.py sync --write  ──▶  <vault>/triage/20260728 ....md  ──▶  /para-triage files it
             └──▶  outlook_sync.py search "..."  ──▶  stdout only, nothing written
```

Personal Microsoft accounts no longer accept Basic Auth or app passwords, so OAuth2 is the only way in. This uses the device-code flow against one Entra app registration with delegated `Mail.Read`, which serves any number of personal accounts. No client secret. **Read-only against the mailbox**: it never sends, deletes, or marks mail read.

## Prerequisites

- **Python 3.9+** and `requests` (`pip install requests`). Examples below use `python3`; on Windows `py` works in its place.
- **An Entra app registration** - public client, delegated `Mail.Read` + `offline_access`, with "Accounts in any organizational directory and personal Microsoft accounts" (or personal-only) enabled. You need its **client id**; there is no secret.
- One device-code login **per mailbox**, once per machine. Auth is machine-global, so adding another vault later needs no re-login.

## Install

1. Copy `outlook_sync.py` into the vault you want mail to land in, at `resources/scripts/`.
2. Create `resources/scripts/outlook_sync.json` next to it - which mailboxes feed *this* vault, plus its subject-keyword filter:
   ```json
   { "accounts": ["someone@hotmail.com"], "keywords": ["invoice", "contract"] }
   ```
3. Create `~/.paraos/secrets/outlook.json` with your client id:
   ```json
   { "client_id": "00000000-0000-0000-0000-000000000000", "authority": "consumers", "accounts": {} }
   ```
4. Log in once per mailbox: `python3 outlook_sync.py login someone@hotmail.com`

## Commands

| Command | What it does | Writes? |
|---|---|---|
| `login <email>` | Device-code login for one mailbox | secret file only |
| `accounts` | List configured mailboxes | no |
| `sync [--days N] [--write]` | Filtered pull into `triage/`. **Dry run by default** | `triage/` + ledger, only with `--write` |
| `search <query> [--limit N] [--body] [--all-mailboxes]` | Ad-hoc keyword search across the whole mailbox | **never** |
| `raw <graph-path>` | Raw Graph GET, for debugging | no |

`sync` is the default command, so a bare `outlook_sync.py --write` still runs a sync and the `/para-triage` sync-script convention works unchanged.

### `sync` vs `search`

They answer different questions and deliberately use different Graph paths.

- **`sync`** walks a **day window** (`$filter` on `receivedDateTime`) and applies the vault's relevance filter: the subject keywords from `outlook_sync.json`, plus an allowlist rebuilt on every run from every email address mentioned in `areas/network/*.md`. Adding a contact automatically widens what gets through. Good for "what arrived lately that this vault should know about".
- **`search`** hits the server-side index (`$search`) and **ignores both relevance filters** - the whole point is to ask something the filter would never have surfaced. It still respects the vault's *account* list, so a session in one vault never prints another's mail; `--all-mailboxes` widens it to every mailbox on the machine. Graph rejects `$search` combined with `$filter` or `$orderby`, so there is no date window and results come back ranked by relevance, not newest-first. It returns in seconds however far back the match lies, which a day-window walk cannot do across years of mail.

```
python3 outlook_sync.py search "supplier name"
python3 outlook_sync.py search "contract renewal" --account someone@hotmail.com --limit 20 --body
```

Because `$search` matches message bodies too, expect some loose hits; skim the dates and senders rather than trusting rank.

## Where state lives

The script is code, so it lives in the vault. Its runtime state does not - a secret written inside a vault leaks the moment that vault syncs.

| Path | Holds |
|---|---|
| `~/.paraos/secrets/outlook.json` | client id + per-account OAuth refresh tokens, rewritten each run (the provider rotates them); written atomically, one account at a time, so parallel runs don't clobber each other |
| `~/.paraos/cache/outlook/synced.json` | dedup ledger, keyed by message id → the vaults it has already been filed to |
| `<vault>/resources/scripts/outlook_sync.json` | that vault's accounts + keywords. Version-controlled with the vault; no secret ever lives here |

Both `~/.paraos` paths honour the `PARAOS_HOME` environment variable.

## Per-vault copy, shared state

This script is **copied** into each vault it serves and syncs only the vault it lives in, auto-detected from its own path. One mailbox can feed many vaults: each vault's own config lists the accounts that feed it. All copies share one secret file and one dedup ledger, and the ledger records filing *per vault*, so the same message can land in several vaults but never twice in the same one.

**This directory is the canonical copy.** Change it here first, then propagate to each vault's `resources/scripts/`. Editing a vault's copy directly is how the copies drift apart.
