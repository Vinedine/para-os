# Vault mirror

Give a vault on a synced drive (Google Drive for Desktop, OneDrive, a SharePoint library) a git history without a `.git` inside the drive. `mirror.py` copies the vault one way into a git repository on a local disk, the mirror, and commits.

```
<vault> on the synced drive, no .git  ──▶  mirror.py  ──▶  <mirror> on a local disk, holds .git
```

A `.git` inside a synced folder breaks two ways. Git does not run reliably on every drive's filesystem: on Google Drive for Desktop a partial commit (`git commit -- <paths>`) crashes. And the sync client uploads git's internal files one by one, so a conflict or a half-uploaded object can corrupt the repository, all the more when several people write the vault. A vault on a plain local disk keeps its own `.git` and needs none of this.

## Prerequisites

- **git**, and **Python 3.9+**, standard library only. On Windows run it with `py -3`; filenames outside the console's code page need no `-X utf8`.
- **Any platform.**

## The rule that matters

**Never edit the mirror.** It is a copy: a run overwrites what changed there and deletes any file the vault does not hold. The script refuses to run over uncommitted changes in the mirror; `--dry-run` lists them, and `--force` overwrites them.

## Install

1. Copy `mirror.py` to `<vault>/resources/scripts/vault-mirror/mirror.py`. It derives the vault from that path, three levels up, so it must sit exactly there.
2. Choose the mirror's folder: on a local disk, outside anything a drive syncs, such as `~/vault-mirrors/acme`. Name it in `PARAOS_VAULT_MIRROR`, or pass `--mirror <path>` on each run. The variable names one mirror, so with several vaults set it per vault, for instance in a shell function:
   ```powershell
   function mirror-acme { $env:PARAOS_VAULT_MIRROR = "$HOME\vault-mirrors\acme"; py -3 "<vault>\resources\scripts\vault-mirror\mirror.py" @args }
   ```
3. Create the mirror, one of the two ways below.

### A vault with no history yet

```
git init ~/vault-mirrors/acme
cp <para-os>/integrations/vault-mirror/info-exclude.template ~/vault-mirrors/acme/.git/info/exclude
py -3 <vault>/resources/scripts/vault-mirror/mirror.py --dry-run
py -3 <vault>/resources/scripts/vault-mirror/mirror.py -m "First mirror"
```

### A vault that already holds `.git`

1. Remove any stale `.git/index.lock` and `.git/next-index-*.lock` a crashed git left in the vault.
2. Stashes, and branches other than the checked-out one, do not survive the move: check `git -C <vault> stash list` and `git -C <vault> branch` and merge what you need first. Note the vault's `HEAD`: `git -C <vault> rev-parse HEAD`.
3. `git clone <vault> <mirror>`.
4. Copy `info-exclude.template` to `<mirror>/.git/info/exclude` and add the vault's `.gitignore` rules to it; any `.gitattributes` rules go to `<mirror>/.git/info/attributes`.
5. Run once: `py -3 mirror.py -m "Move history to the mirror"`. Whatever the vault held uncommitted lands in the mirror's history. The vault's `.git` is never copied.
6. Confirm the old `HEAD` is an ancestor of the mirror's: `git -C <mirror> merge-base --is-ancestor <old HEAD> HEAD && echo ok`.
7. Only then remove from the vault its `.git` folder and every `.gitignore`, `.gitattributes` and `.gitkeep` file. Drop the mirror's `origin`, which pointed at that `.git` (`git -C <mirror> remote remove origin`), and run again to commit the removal.

## Usage

```
py -3 mirror.py                     # copy, then commit with a generated message
py -3 mirror.py -m "Archive Alpha"  # your own subject, better when the change has a name
py -3 mirror.py --dry-run           # list what would be copied, write nothing
py -3 mirror.py --force             # overwrite uncommitted edits in the mirror
```

A generated subject reads `Mirror live vault: 3 added, 7 modified, 1 deleted`, with the committed paths in the body (the first 40). Run it at the end of a working session. Everything changed since the last run lands in one commit, with no per-person attribution; the drive's own version history still keeps who changed each file.

## What it copies and what it commits

- **It copies every file the vault holds**, deletes from the mirror what the vault no longer holds, and never writes the vault. A file whose size matches and whose timestamp alone moved is compared by content, not recopied.
- **It skips only files no script can read**, on both sides, so the mirror keeps whatever copy its history holds: Google Drive's native-format pointers (`.gdoc`, `.gsheet`, `.gslides` and the rest), the GUID-named marker OneDrive keeps locked in a synced root, and Office's `~$` lock files. It never copies a `.git`.
- **It stages with `git add -A`, so the mirror's `.git/info/exclude` decides what the history keeps.** A path listed there sits in the mirror's working tree and is never committed. Keep the rules there, never in a `.gitignore` inside the mirror, which the next run deletes because the vault holds none.
- **`info-exclude.template` is the starting file.** It re-includes `CLAUDE.md`, `CLAUDE.local.md` and `.claude/`, which a global gitignore often keeps out, and keeps out the activity log in `resources/logs/`, script caches and operating-system litter. Uncomment `archive/`, or list any large folder, to keep bulk as a copy only. `.mcp.json` is left to your global gitignore, since it can hold a live token: add `!.mcp.json` when the vault's copy holds none. `git -C <mirror> status --ignored` lists what the rules keep out.
- **A fresh clone of a mirror does not carry `.git/info/exclude`**: copy it over by hand when you rebuild one.
- **Paths over 260 characters** are reached on Windows through the extended-length prefix, with no machine setting.

## The `~/.paraos` contract

Nothing under `~/.paraos/`: the mirror's history is the state, and the script needs no secret, cache or config. Its one setting is `PARAOS_VAULT_MIRROR`. See [`integrations/README.md`](../README.md).
