# Pocket recording sync

Pull your [Pocket](https://heypocket.com/) recordings - the AI summary *and* the full transcript - into a vault's `triage/` as dated Markdown notes, one file per recording. From there `/para-triage` files each one where it belongs (the owning project's `sources/`, a contact, `archive/meetings/` when it spans several).

Pocket is a wearable recorder for conversations that happen off a screen: site visits, notary appointments, a walk-through with a contractor. It is the in-person counterpart of [`granola/`](../granola/), and lands its record the same way.

```
Pocket app  ──▶  pocket.py  ──▶  <vault>/triage/20260913 Site walkthrough.md  ──▶  /para-triage files it
```

## Prerequisites

- **A Pocket account with an API key.** In the Pocket app: Settings → Developer → API Keys. The key starts with `pk_`. The script reads through [Pocket's public API](https://docs.heypocketai.com/docs/api) and only ever sends `GET`.
- **Python 3.9+.** Standard library only, no `pip install`.
- **Any platform.**

## Install

1. Copy `pocket.py` into the vault recordings should land in:
   ```
   <vault>/resources/scripts/pocket.py
   ```
   The sync finds its vault from its own location (two levels up), so it must live under `resources/scripts/`.

2. **Store the key** as `~/.paraos/secrets/pocket.json`:
   ```json
   { "api_key": "pk_..." }
   ```

3. **Dry run**, then write:
   ```
   py <vault>/resources/scripts/pocket.py            # shows what it would write, touches nothing
   py <vault>/resources/scripts/pocket.py --write    # creates the notes in triage/
   ```

4. Run `/para-triage` in the vault to file the new notes.

## Usage

```
py pocket.py              # DRY RUN (default) - last 30 days
py pocket.py --write      # create the notes
py pocket.py --days 90    # widen the look-back window
py pocket.py --dump <id>  # print one recording's raw API JSON
```

Re-runs skip a recording that is in the dedup ledger (`~/.paraos/data/pocket/synced.json`), and ledger one whose note (matched by its `pocket_id`) is still in `triage/` but missing from it; once `/para-triage` has filed a note elsewhere the ledger is the only record of it, so a cleared ledger re-imports every recording in the look-back window. Two different recordings with the same date and title both land: the second gets the first six characters of its id appended, or the whole id when those are taken.

Each note carries YAML front-matter (`title`, `date`, `pocket_id`, `source: pocket`, `recorded_by`, `duration_min`, `tags`), then `## Summary`, `## Action items` when Pocket generated any, and `## Transcript`. The date is when the conversation was recorded, in local time.

- **Summary**: Pocket's own Markdown. Its custom `<pocket:timeline>` blocks become a bold title over plain bullets, since renderers hide unknown tags.
- **Action items**: plain bullets marked unconfirmed, never checkboxes. The note lands in `triage/`, and `/para-triage` decides which, if any, become a real action.
- **Transcript**: one paragraph per segment, each opening on its `[mm:ss]` timestamp. Pocket often skips speaker detection; when it does label speakers, consecutive turns of one speaker merge.
- **Not included**: Pocket's `language` field (the transcriber's guess, not the language spoken), the mind map, and the audio, which stay in Pocket.

A recording with no speech or no summary is written, and the note says there was none, only when every status Pocket reports for it (the recording's `state`, each summary's, the transcript's) is one the script knows to be final. Where Pocket *reports* a failure (a transcript or summary error), the note is written and says that instead. Every other case writes nothing, ledgers nothing, and comes back on the next run:

- `HELD, still processing`: any of those statuses is still in progress.
- `HELD, unreadable`: a field holds text in a shape the readers cannot parse (only text where text is expected counts, never a title, template name, error message or timestamp), or a field is blank while a status is one the script does not know. Pocket's API reference leaves `transcript` and `summarizations` untyped, so the readers are built on the shape a live account returned: `transcript.segments[]`, and per summarization id `v2.summary.markdown` plus `v2.actionItems.actions[]`. The line prints the `--dump <id>` that shows the payload; the fix belongs in `transcript_md` / `summaries_md` in this master.
- `FAILED`: fetching that recording failed after retries (a rate limit, a server error, the network). The rest of the run continues; a failure to list recordings stops the run instead.
- `UNDATED`: neither `recording_at` nor `created_at` parses, with its `--dump <id>`.

A held recording that ages out of the look-back window stops being listed; widen `--days` to reach it.

## The `~/.paraos` contract

| What | Where | Bucket |
|---|---|---|
| The script | `<vault>/resources/scripts/pocket.py` | (in the vault, version-controlled) |
| Routing config | `<vault>/resources/scripts/pocket.config.json` | (in the vault; never secret) |
| API key | `~/.paraos/secrets/pocket.json` | secret - never syncs to a cloud drive or git |
| Dedup ledger | `~/.paraos/data/pocket/synced.json` | data - it does not rebuild once notes have left `triage/`; an older `cache/pocket/synced.json` is still read and merged in |

The root is `PARAOS_HOME` (default `~/.paraos`). See [`integrations/README.md`](../README.md).

## Multiple vaults (optional)

Routing is by **title prefix, the same rule as [granola](../granola/)**, so one naming habit serves both: `Client - Steering` goes to the vault mapped to `Client`, and the prefix is dropped from the note's filename. The prefix is an alphanumeric run followed by a dash; `Client Steering` without the dash is not prefixed. Pocket titles each recording itself, so the prefix goes in by renaming the recording in the app. Drop a `pocket.config.json` next to the script mapping each prefix to its vault (copy `pocket.config.json.template` to start):

```json
{
  "meetings_subdir": "triage",
  "route": { "Client": ".", "Home": "family", "Side": "side-project" }
}
```

**`"."` means the vault this copy lives in**; never write that folder's own name, which is machine-local (a synced library is named in the sync client's display language) while this file syncs to everyone. A target naming neither this vault nor an existing sibling warns once at startup.

With `route` set, a recording goes only where its prefix sends it. One with no routed prefix (including a recording not renamed yet) is listed as `UNROUTED` on every run and written nowhere, so it is visible rather than misfiled, and lands on the first run after it is renamed, as long as that is inside the look-back window. Each copy writes only its own vault by default; `--vault X` targets another (and stops if nothing routes to `X`), `--all` writes every routed vault in one pass. The vaults must be sibling folders under one parent. Prefixes match case-insensitively.

Omit the file, or leave `route` empty, and every recording goes to the local vault: all a single-vault user needs.

**The config is a separate file on purpose.** `pocket.py` holds nothing vault-specific, so re-syncing an installed copy is a straight file copy that leaves the routing untouched.
