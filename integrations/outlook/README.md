# Outlook / Hotmail mail reader

Read a Microsoft account - personal (outlook.com, hotmail.com, live.com) or a Microsoft 365 work mailbox - on behalf of a vault, and hand the messages to whatever decides what they mean. **It writes nothing.**

```
Outlook.com  ──▶  outlook.py fetch   ──▶  JSON on stdout  ──▶  a skill judges it  ──▶  only the keepers are written
             └──▶  outlook.py search "..." ──▶  stdout only, an answer to one question
```

There used to be a third arrow. `sync --write` decided relevance from a static config and wrote every match into `triage/`, leaving something else to sort it out afterwards. It was **removed**, for two reasons that had both been measured. The filters were guesses maintained by hand, so being wrong cost a folder of files to delete rather than nothing. And on a live personal inbox the honest setting was "take everything", which meant four figures a week per vault. Reading the mailbox and judging before writing costs the same read and removes both problems, so there was nothing left for the write path to be better at.

Personal Microsoft accounts no longer accept Basic Auth or app passwords, so OAuth2 is the only way in: a browser sign-in (authorization code + PKCE), delegated `Mail.Read`, no client secret. A Graph GET does not change is-read state, so nothing here is visible in the mailbox.

## Prerequisites

- **Python 3.9+** and `requests` (`pip install requests`). Examples below use `python3`; on Windows `py` works in its place.
- **An Entra app registration** - public client, delegated `Mail.Read` + `offline_access`, with "Accounts in any organizational directory and personal Microsoft accounts" (or personal-only) enabled. You need its **client id**; there is no secret. Add `http://localhost` as a redirect URI under the **Mobile and desktop applications** platform, which is what the browser sign-in redirects to. Add delegated `Mail.Read.Shared` only if that app serves a **shared** mailbox; see "Scope is per account" below.
- One login **per mailbox**, once per machine. Auth is machine-global, so adding another vault later needs no re-login.

## Install

1. Copy `outlook.py` into the vault you want mail to land in, at `resources/scripts/`.
2. Create `resources/scripts/outlook.config.json` next to it - which mailboxes feed *this* vault, and nothing else, since there are no filters to configure:
   ```json
   { "accounts": ["someone@hotmail.com"] }
   ```
   If you reply from an alias, pass an object instead to name it, so those replies don't hide the counterparty: `{ "accounts": { "someone@hotmail.com": { "self": ["alias@domain.com"] } } }`.
   Not named `outlook.json`: that is the machine-global **secret** below, and two files sharing one name across opposite trust zones is how a credential ends up inside a synced vault.
3. Create `~/.paraos/secrets/outlook.json` with your client id:
   ```json
   { "client_id": "00000000-0000-0000-0000-000000000000", "authority": "consumers", "accounts": {} }
   ```
4. Log in once per mailbox: `python3 outlook.py login someone@hotmail.com`
   A Microsoft 365 mailbox needs its own tenant's app: `python3 outlook.py login someone@company.com --client-id <app> --authority <tenant-id>`. A personal-accounts app is registered against the `consumers` authority, which refuses work accounts outright, so both settings resolve per account.

### Scope is per account, and narrow by default

Every mailbox is asked for `Mail.Read` + `offline_access`. **`Mail.Read.Shared` is asked for only on an account that actually reads a shared mailbox**, which `account_scope()` derives from the config: some entry names it as its `via`, or `login --shared` set the flag ahead of that entry existing.

It is narrow by default because the token endpoint is asymmetric. A refresh may ask for **less** than was consented but never **more**, so a scope the account never consented to does not degrade to what it can have - it fails the refresh outright with `AADSTS65001` and takes an already-working mailbox offline. Asking every account for `Mail.Read.Shared` because one of them needed it did exactly that on a live machine: **every Microsoft 365 mailbox stopped authenticating at once**, while the personal ones kept working, because the `consumers` endpoint silently drops the extra and hands back a `Mail.Read` token. So the symptom pointed at the work tenants and the cause was a constant in this file. `AccountScope` in the test suite pins it, including that no module-wide `SCOPE` comes back.

`--shared` is only for the ordering case: consenting a user *before* the shared mailbox entry that names them exists. Once the `via` line is there, the scope follows from it and the flag is redundant.

### The login flow, and why it is not device code any more

`login` signs in through the **browser**: authorization code + PKCE, redirected to a loopback port this script opens for the duration. `login --device-code` still runs the old flow.

The default changed because device code flow is being closed off. Blocking it is one of the enforced security-defaults policies, and:

> Starting July 1, 2026, all new Microsoft Entra tenants block device code flow as part of security defaults.

So on a tenant created from that date, a device-code sign-in is refused outright with `AADSTS530035` while a browser sign-in is untouched. **This is the normal case for a new client tenant, not an edge case.**

The way it presents is worth knowing, because it does not look like a policy. A new tenant gets a **24-hour grace period** before security defaults are enforced. So the first login works, the mailbox reads fine for a day, and then every refresh starts failing the next afternoon, which reads as "it worked until lunchtime" and sounds nothing like a tenant policy.

**Nothing about an existing account changes.** Which flow minted a refresh token is not recorded in it and not asked about when it is redeemed, so every mailbox already logged in keeps working untouched, with no re-login. The flow only decides what happens during `login`.

**What the app needs:** `http://localhost` registered as a redirect URI, under the *Mobile and desktop applications* platform. It is **not** one of the tick-boxes that blade offers (`nativeclient`, LiveSDK, `msal<id>://auth`) - type it into the free-text field below them. Register it **without a port**: Entra ignores the port when matching a loopback redirect, so one entry covers whatever ephemeral port the OS hands the script. If the portal refuses an `http://` entry there, add it through the app **Manifest** instead - `"replyUrlsWithType": [{"url": "http://localhost", "type": "InstalledClient"}]`, or `"publicClient": {"redirectUris": ["http://localhost"]}` in the Microsoft Graph manifest format. An app without that entry cannot use this flow, which is what `--device-code` is still there for on a tenant that permits it.

### When a token exchange fails

Microsoft says why in `error_description`, keyed by an `AADSTS` code, and the script quotes it rather than reducing it to `invalid_grant` / `invalid_request` - two classes that each cover a dozen unrelated causes. The remedy follows from the code, because "re-run login" is wrong for some of them and impossible for others:

| Code | Means | What actually fixes it |
|---|---|---|
| `AADSTS65001` | The consented scope does not cover what was asked | `login <email>`, with `--shared` if a shared mailbox routes through it, or a tenant admin grants the permission to the app |
| `AADSTS500113` | The app has no reply address, so the browser sign-in has nowhere to return to. Lands on Microsoft's error page and never reaches the script | Register `http://localhost` as above, then `login <email>` again |
| `AADSTS530035` | Security defaults block the sign-in, almost always device code flow | `login <email>` on the **default browser flow**, which they do not block - no admin needed. Failing that, an admin turns security defaults off (they are on or off, with no per-app exception), or adds Entra ID P1 and writes a Conditional Access policy whose *Authentication flows* condition permits the app |
| `AADSTS700082` / `70008` | The stored refresh token expired or was invalidated | `login <email>` |
| `AADSTS50076` / `50079` | The tenant wants an interactive MFA or CA challenge | `login <email>` |

## Commands

| Command | What it does | Writes? |
|---|---|---|
| `login <email> [--shared] [--device-code]` | Browser login for one mailbox | secret file only |
| `accounts` | List configured mailboxes | no |
| `fetch [--days N] [--include-bulk]` | Candidates as JSON on stdout, for a skill to judge | **never** |
| `search <query> [--limit N] [--body] [--all-mailboxes]` | Ad-hoc keyword search across the whole mailbox | **never** |
| `raw <graph-path>` | Raw Graph GET, for debugging | no |

There is no default command. A bare `outlook.py` asks for a subcommand: the default used to be `sync`, which is what made `outlook.py --write` do something, and nothing should quietly pick a behaviour for a script that reads mailboxes.

### An account not logged in on this machine

A refresh token lives only on the machine it was granted on, by design. So on a vault fed by several mailboxes, **no single machine ever holds every account** - not even the machine of whoever added the second one. A plain `fetch` therefore treats a not-logged-in account as absent rather than fatal: it warns one line per skip on stderr and fetches whatever this machine does have, exiting only when *none* of the vault's accounts are logged in here. Naming one explicitly with `--account <email>` still exits, because a direct ask deserves a direct answer rather than a skip.

### `fetch` and `search`

Both read and neither writes; they differ in the question they answer. `fetch` walks a recent window of the inbox and the archive, for a skill to triage. `search` asks one question of the whole mailbox at any depth and prints the answer, which is what you want when the thing you are looking for is older than any window worth walking.

The scopes differ on purpose. `fetch` asks "what has arrived that nobody has dealt with", so Junk Email and Deleted Items are answers someone already gave and it does not reopen them; `search` asks "where is this thing", and a thing can be anywhere, so it reads everything.

### `fetch`: read now, decide before writing

`fetch` reads a recent window and **writes nothing**. It prints the candidates as JSON on stdout, one object per thread, and leaves the relevance decision to whatever consumes it.

**It reads the inbox and the archive, and nothing else.** It used to read `/me/messages`, which is the whole mailbox, so a run re-surfaced mail the spam filter had already caught and mail the operator had already thrown away, and offered it back as something to triage. Measured across two live mailboxes over one 2-day window: **233 messages, of which 171 came from Junk Email, Deleted Items or Sent Items** - one of the two had an empty inbox and returned 30 messages, all of them junk. Nothing failed while this was wrong; the run simply looked productive, which is why the scope is pinned by tests rather than left to this paragraph. The archive stays in scope because an operator who archives fast can file a real message between two runs, and it is cheap: 6 messages over 30 days on the mailbox that actually archives. The folders are named by Graph's language-independent well-known names, since display names are localized and `Junk Email` is `Ongewenste e-mail` on a Dutch mailbox.

A skill consuming it judges each candidate against the vault's own `## Triage sources` rules and its README, the same way it judges mail from a Gmail connector, and writes only what survives. Getting a judgment wrong therefore costs nothing, where the removed write path cost a folder of files to delete.

**Bulk mail is dropped before the caller sees it**, on the RFC 2369 `List-Unsubscribe` header and nothing else. What that costs and why there is no sender-name backstop: "What shapes the candidate stream" below.

The remainder is the right remainder. What survives is spam and phishing that declines to identify itself, mixed with real correspondence, and telling those apart is judgment rather than a rule.

stdout is pure JSON so a caller can parse it; the per-account counts and every other human-readable line go to stderr.

**One record is one conversation, not one message.** The script groups on Graph's `conversationId` before it emits anything, falling back to the message id where Graph omits one. It used to hand the caller a record per message and leave the collapsing to them, which every caller then had to remember and one caller did not: a live mailbox produced 137 routing decisions over 68 real threads, one conversation accounting for 15 of them, and the run read as productive because the failure inflates rather than drops. Grouping at the source makes the invariant true for every caller instead of for the ones that remember.

A record describes the **newest** message in its thread and carries the whole of it:

| Field | What |
|---|---|
| `subject`, `from`, `from_name`, `received`, `preview`, `link`, `id`, `message_id` | The newest message. `message_id` is the RFC822 one, so a message reaching two mailboxes is recognisable as one message. |
| `thread_id` | The Graph conversation, or the message id where there is none. |
| `message_count`, `messages` | How many messages the window held for this thread, and all of them, newest first. |
| `participants` | Everyone who **wrote** on the thread, minus the mailbox owner. Match contacts against this, never against `from` alone: a thread where the owner replied last would otherwise hide the counterparty, which is the most ordinary thing a live thread does. Senders only, because who received a message says nothing about whose business it is. |
| `from_owner` | Whether the newest message is from the mailbox owner. |

## What shapes the candidate stream

Nothing configurable, which is the point. There is no keyword list, no catch-all switch and no contact allowlist any more; those existed to decide what got written, and nothing is written. Relevance is judged by the caller against the vault's own `## Triage sources` rules and its README, where the context actually is.

The one cut this script still makes is **bulk mail**, on one signal and a cost-saver rather than a filter: **RFC 2369 `List-Unsubscribe`**, which every legitimate marketing sender sets and ordinary correspondence does not. Measured on a live personal inbox: **177 messages over two days, 159 dropped, 18 candidates**, in about four seconds. `--include-bulk` turns it off.

**There is deliberately no noreply-style sender-name backstop**, and adding one back would be a regression the tests catch. Matching `noreply`, `notification` or `newsletter` on the local part is the exact exclusion [`para-shared/connectors.md`](../../base/.claude/skills/para-shared/connectors.md) forbids by default for every mailbox source, this one included: a domain or DNS action-required notice, a tax filing alert, an invoice, a payment receipt and a booking confirmation are nearly always sent from a `noreply@` address, so the pattern drops precisely the mail the vault exists to catch, and drops it invisibly. It also earned little - on that same inbox the name test alone left 144 of 177, because the shops write from `hello@` and `news@`. A mailbox that is measurably mostly bot mail is narrowed by naming that application's own domain in the vault's own `Relevant when` rules, where the narrowing stays visible to whoever reads the run.

What survives is real correspondence mixed with the spam that declines to identify itself. Telling those apart is judgment, which is what the stream is being handed to.

## Where state lives

The script is code, so it lives in the vault. Its runtime state does not - a secret written inside a vault leaks the moment that vault syncs.

| Path | Holds |
|---|---|
| `~/.paraos/secrets/outlook.json` | client id + per-account OAuth refresh tokens, rewritten each run (the provider rotates them); written atomically, one account at a time, so parallel runs don't clobber each other. Also the per-account `client_id` / `authority` / `via` / `shared` pointers the scope and route resolve from |
| `~/.paraos/cache/outlook/synced.json` | **frozen.** The dedup ledger the removed `sync` wrote, keyed by message id → the vaults it filed to. Nothing writes it now; keep it, because a consumer that stages mail of its own should not re-surface what was already filed from here |
| `<vault>/resources/scripts/outlook.config.json` | that vault's accounts. Version-controlled with the vault; no secret ever lives here. The superseded name `outlook_sync.json` is still read, with a notice |

Both `~/.paraos` paths honour the `PARAOS_HOME` environment variable.

## Per-vault copy, shared secret

**This directory is the canonical copy.** The script holds nothing vault-specific - accounts in the `.json` beside it, credentials in `~/.paraos/secrets/`, the vault derived from the copy's own path - so propagating a change is a **straight file copy**, and your config survives it. Configure a vault through its `.json`, never by editing the script: an edit to the script is what the next resync silently discards.
