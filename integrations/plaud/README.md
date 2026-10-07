# Plaud recording sync

Pull your [Plaud](https://www.plaud.ai/) recordings - the AI summary *and* the full transcript - into a vault's `triage/` as dated Markdown notes, one file per recording. From there `/para-triage` files each one where it belongs (the owning project's `sources/`, a contact, `archive/meetings/` when it spans several).

Plaud makes wearable recorders (NotePin, Note) for conversations that happen off a screen. It lands its record the same way as [`pocket/`](../pocket/), and routes by the same title prefixes as pocket and [`granola/`](../granola/).

```
Plaud app  ──▶  plaud.py  ──▶  <vault>/triage/20260913 Site walkthrough.md  ──▶  /para-triage files it
```

## Prerequisites

- **A Plaud account** whose recordings the Plaud app transcribes and summarises.
- **A browser on the same machine, once.** `login` signs in through Plaud's web page and receives the answer on `http://localhost:8199`, so that port must be free while it runs.
- **Python 3.9+.** Standard library only, no `pip install`.
- **Any platform.**

## Install

1. Copy `plaud.py` into the vault recordings should land in:
   ```
   <vault>/resources/scripts/plaud.py
   ```
   The sync finds its vault from its own location (two levels up), so it must live under `resources/scripts/`.

2. **Sign in** once:
   ```
   py <vault>/resources/scripts/plaud.py login
   ```
   This opens Plaud's sign-in page and saves the tokens to `~/.paraos/secrets/plaud.json`. The access token refreshes on its own; when Plaud refuses a refresh, the script stops and asks you to run `login` again.

3. **Dry run**, then write:
   ```
   py <vault>/resources/scripts/plaud.py            # shows what it would write, touches nothing in the vault
   py <vault>/resources/scripts/plaud.py --write    # creates the notes in triage/
   ```

4. Run `/para-triage` in the vault to file the new notes.

## Usage

```
py plaud.py login         # one-time browser sign-in
py plaud.py               # DRY RUN (default) - last 30 days
py plaud.py --write       # create the notes
py plaud.py --days 90     # widen the look-back window
py plaud.py --dump <id>   # print one recording's raw API JSON
```

Re-runs skip a recording that is in the dedup ledger (`~/.paraos/data/plaud/synced.json`), and ledger one whose note (matched by its `plaud_id`) is still in `triage/` but missing from it; once `/para-triage` has filed a note elsewhere the ledger is the only record of it, so a cleared ledger re-imports every recording in the look-back window. Two different recordings with the same date and title both land: the second gets the first six characters of its id appended, or the whole id when those are taken.

Each note carries YAML front-matter (`title`, `date`, `plaud_id`, `source: plaud`, `duration_min`), then `## Summary` and `## Transcript`. The date is when the recording started, in local time.

- **Summary**: Plaud's AI summary in its own Markdown, under the template's title when there are several.
- **Transcript**: one paragraph per speaker turn, each opening on its `[mm:ss]` timestamp; consecutive turns of one speaker merge. The raw transcript is used, the polished copy only when there is no raw one.
- **Not included**: the outline, memos and the audio, which stay in Plaud.

A recording missing its transcript or its summary is not written yet: the run lists it as `HELD, no ... yet`, ledgers nothing, and tries again next run. Once 24 hours have passed since Plaud received it, it is written with whatever exists, and the note says what was missing, so a recording nobody transcribes cannot hold forever. Transcribe in the Plaud app within the day, or the note lands without it. Other cases:

- `HELD, unreadable`: the transcript is JSON in a shape the reader cannot parse. It holds past the 24 hours, since writing it would lose the words; the line prints the `--dump <id>` that shows the payload, and the fix belongs in `transcript_md` in this master.
- `FAILED`: fetching that recording, or the file its summary or transcript sits in, failed after retries. The rest of the run continues; a failure to list recordings stops the run instead.
- `UNDATED`: the listing's `created_at` does not parse, with its `--dump <id>`.

A held recording that ages out of the look-back window stops being listed; widen `--days` to reach it.

## Known limit: the API

The script reads Plaud's third-party API, the one Plaud's own command-line tool, `@plaud-ai/cli`, uses, and signs in as that tool's public OAuth client rather than a client of its own. Whether Plaud supports that client for other software, and how stable the API is, is not settled: a change on Plaud's side can stop the sync until this master is updated. The response shape is read from that tool, not from documentation, and `--dump <id>` shows what Plaud actually returns. Two environment variables override the defaults without editing the script: `PLAUD_CLIENT_ID` for the client id and `PLAUD_API_BASE` for the API address.

## The `~/.paraos` contract

| What | Where | Bucket |
|---|---|---|
| The script | `<vault>/resources/scripts/plaud.py` | (in the vault, version-controlled) |
| Routing config | `<vault>/resources/scripts/plaud.config.json` | (in the vault; never secret) |
| Sign-in tokens | `~/.paraos/secrets/plaud.json` | secret - never syncs to a cloud drive or git |
| Dedup ledger | `~/.paraos/data/plaud/synced.json` | data - it does not rebuild once notes have left `triage/` |

The root is `PARAOS_HOME` (default `~/.paraos`). See [`integrations/README.md`](../README.md).

## Multiple vaults (optional)

A vault that is the only destination for the account needs no config and no title prefixes: omit `plaud.config.json`, or leave `route` empty, and every recording goes to the local vault.

When one Plaud account feeds several vaults, routing is by **title prefix, the same rule as [pocket](../pocket/) and [granola](../granola/)**, so one naming habit serves all three: `Client - Steering` goes to the vault mapped to `Client`, and the prefix is dropped from the note's filename. The prefix is an alphanumeric run followed by a dash; `Client Steering` and `Client: Steering` are not prefixed. Rename the recording in the Plaud app to add one. Drop a `plaud.config.json` next to the script mapping each prefix to its vault (copy `plaud.config.json.template` to start):

```json
{
  "meetings_subdir": "triage",
  "route": { "Client": ".", "Home": "family", "Side": "side-project" }
}
```

**`"."` means the vault this copy lives in**; never write that folder's own name, which is machine-local (a synced library is named in the sync client's display language) while this file syncs to everyone. A target naming neither this vault nor an existing sibling warns once at startup.

With `route` set, a recording goes only where its prefix sends it. One with no routed prefix (including a recording not renamed yet) is listed as `UNROUTED` on every run and written nowhere, so it is visible rather than misfiled, and lands on the first run after it is renamed, as long as that is inside the look-back window. Each copy writes only its own vault by default; `--vault X` targets another (and stops if nothing routes to `X`), `--all` writes every routed vault in one pass. The vaults must be sibling folders under one parent. Prefixes match case-insensitively.

**The config is a separate file on purpose.** `plaud.py` holds nothing vault-specific, so re-syncing an installed copy is a straight file copy that leaves the routing untouched.
