# Phase 3 - Derived copies: rules and scripts

## Sweep for

- **Vault-local skills** (`.claude/skills/`). Read every one; fix the rule text, not just the skill name.
- **Skill names** in `README.md`, `meetings.md`, briefs, and other skills. Verify each name still exists as a skill before repointing; drop references to skills that no longer exist rather than guessing a replacement. **The sweep's scope is the renames and removals the collected entries name**: an unresolved name no entry explains predates this delta, and is listed as a vault observation rather than repointed.
- **Installed skill copies**, in both places they can live, because each goes stale on its own:
  - *The vault's bundled `.claude/skills/`*. **These are skeleton content and this phase audits them like any other skeleton file.** They also shadow the user-level install, so a stale one silently overrides a correct global skill for every session in that vault. Diff each against the ref's master and report; call out by name a bundled skill the scan's `revisions_behind` puts at more than one revision behind.
  - *The user-level install*, if the vault runs on that instead. Report its drift the same way. Syncing them is a machine-level action, so propose it, don't do it silently.

  If both exist, say which one actually wins for this vault before reporting either as stale. **A copy that differs from the ref but matches the clone's working tree or another of its branches is ahead of the ref**, synced from there: report it that way, in the verdicts under `## Installed integration scripts`, never as drift. Installed flavor skills are checked only for a vault declaring that flavor.

  **A skill is compared as a tree**, its `scripts/` folder included: a file the master has and the copy lacks is under the row's `missing` ([scan.md](scan.md)). A copy whose `SKILL.md` names a script it does not have (`names_missing_script`) stops where it would run it, per [para-shared/scripts.md](../../para-shared/scripts.md): report the skill as unusable until synced, not as a missing file.

  **A skill script is not an installed integration.** It carries no `para-os-integration:` marker, no vault config and no local fixes, and it is matched to its master by path rather than by marker, so the four-condition gate below does not govern it: syncing one is the plain copy the user asks for. Verify it by re-running the scan, which reports the copy `identical`.

  **`para-shared/scripts/` is a dependency of the others, not a skill of its own.** It holds the library every skill script reads the vault with. Check it first and name it once, rather than per skill.
- **The vault's own `CLAUDE.md` claims about itself.** Enumerate the claims first, then verify each with a command, and report the list with a verdict per row rather than a sentence saying they were checked.

  | Claim shape | How it reads | The check |
  |---|---|---|
  | A path exists | "proposals live in `projects/ticketing-platform-replacement/sources/`" | `test -e` on the path |
  | A path *shape* | "`areas/*/sources/`", "`projects/<name>/brief.md`", "`archive/meetings/YYYYMMDD Description.ext`" | glob it; **one match is the claim met**. Never `test -e` a pattern |
  | A script is installed | "`scripts/` = `granola.py`, `outlook.py`..." | `ls` the folder; every name in the prose must be on disk, **and every script on disk must be in the prose** |
  | A config holds a key or value | "`outlook.config.json` carries `\"match_all\": true`" | read the file and compare the literal value |
  | A file carries a snippet | "`.claude/settings.json` holds `autoMemoryEnabled: false`" | grep the file for it |
  | A count or inventory | "4 vendor responses", "3 vendor calls" | count the folders and compare |
  | A named skill or command exists | "emptied via `/para-triage`" | the skill must resolve; a renamed one is repointed, a removed one dropped |

  **Split the literals from the shapes before running anything.**

  **Any backticked value in the prose is a claim**, a config key included. The check runs **in both directions** for inventories: prose naming something absent is stale, and disk holding something the prose never names is undocumented.

## Installed integration scripts

Every script a para-os integration ships carries `para-os-integration: <name> <revision>` in its header. An integration whose README installs it outside any vault (a machine-level hook) is checked where that README says it lives, once per machine, and reported as such.

**Compare the content, never the marker string.** The marker says which integration a file came from; it does not say what the file contains. A copy whose header was bumped by hand while the code stayed old reports clean under a string compare. The scan's `integrations` block carries the normalised diff, `diff_stat`, and the verdict for every marked script ([scan.md](scan.md), "The verdict").

**A script renamed upstream** (`renamed: true`, its folder's one script read as the master) is reported as part of the verdict. Where the folder ships several (`ambiguous-rename`), name the `candidates` and ask which. An `unresolvable` marker, its folder gone: report it, leave the script alone, and never match it to a folder with a similar name. A marker whose integration a collected entry retires is removed as that entry's Reaction says, one approval per file: the gate governs overwrites, not that removal.

Report from the line-ending-normalised diff:

- *Identical* - print it and move on.
- *Behind* - the copy lacks changes the master has. Name the script, the marker revision on each side, the changelog entries in between, and **what the diff actually shows**. A diff that touches only a config block is a different conversation from one that touches logic.
- *Ahead* - the copy has changes the master lacks. Say so and suggest folding them back into the master rather than touching the vault.
- *Both* - the two diverged: behind on the master's changes and ahead on its own. Report it as divergence, not as "behind".
- *Marker matches, content differs* - **two very different cases.** Say which one this is before saying anything else:
  - *Within-revision drift.* The copy was taken from that revision's branch before its tip settled, so both sides honestly carry the same marker. This is the **normal** state while a revision is in development: report it as "behind within `<revision>`", describe the diff, and move on.
  - *A hand-bumped marker.* The copy carries a revision whose content it never had - someone edited the header instead of the file. **This** is the loud one.

  Nothing in the two files distinguishes them, so **do not guess from the diff**. The separator is provenance: if the ref is an unmerged or recently-moved branch, or the vault's copy plausibly predates the tip, it is the first case. Ask the user which when it matters; against a released revision only the second case exists.
- *No marker* - an older copy, or a script written for that vault alone. Never guess which integration it came from. Name it, ask the user which shipped integration it is (if any), and stamp the copy at the revision they say they installed from. A script the user says is theirs stays unmarked and is named as skipped.

**Report, never overwrite** - this is the one read-only item in an otherwise applying skill. These scripts carry the vault's own config and local fixes, so re-syncing one is a merge the user makes with the diff in front of them.

### The one sanctioned overwrite

A user who reads the diff may say "sync it". An overwrite needs **all four**:

1. **The user asked**, in this session, for that script or for the integrations generally. Never infer it from a general "upgrade the vault".
2. **Equivalence is proven mechanically, not read.** The scan's `overwrite` field runs this proof against a commit in the master's history: `proof` is `history-match` (byte-identical, normalised, which also settles condition 3), `ast` (Python with identical syntax trees, docstrings aside) or `whitespace` (equal but for line endings and trailing whitespace). Any other difference is drift for the user to judge (`eligible: false`): report it. **Print the verdict.**
3. **The copy is not *ahead*.** Divergence means local work exists, and only the user can decide what survives - the scan never marks `eligible: true` for a verdict of `ahead`, `both`, or `marker-matches-content-differs`.
4. **It is verified after the write**, by re-diffing against the master and running the integration's own test suite (its `suite.runner`, with the suite's `files` and `fixtures` copied beside the installed copy) against the installed copy, not against the master - **from a scratch directory with no vault config present**, not in place. Run in place, the suite picks up whatever real config the installed copy resolves relative to itself (a multi-vault routing table, a live API key), which can fail assertions the fixture never anticipated even though the copy is provably correct. A failure that traces to config content rather than the script's own logic is inconclusive, not a failed verification - diagnose which before reporting either way.

**Conditions 2 and 3 are re-proven at write time, never carried over from the report.** A copy can change between the diff the operator read and the write (a sync client, another session, a re-sync made outside this one): re-run the scan with `--unchanged <the scan whose diff the operator was shown>` immediately before the overwrite. The copy's path in `since.changed` means it is no longer the file the operator saw: stop. Otherwise the fresh `integrations` row re-proves conditions 2 and 3 (`overwrite.eligible`).

## The prose that documents an integration

**Only the script is checked by the diff above.** The vault's `resources/scripts/README.md`, its `## Triage sources` row, and any `## MCP integration intent` block are hand-written descriptions of behaviour the integration owns, and a file copy leaves every sentence about it untouched.

So for every integration whose changelog entries fall inside this migration's delta, **read the entry for caller-visible changes and grep the vault's prose for the claims they invalidate.** Caller-visible means: what the tool reads, what a record represents, how a count is arrived at, how authentication happens, which flags exist, and anything the entry itself frames as a Reaction for the operator. Wording changes and internal refactors are not.

- Search the vault, not just `resources/scripts/README.md` - the same claim is usually restated in `CLAUDE.md` (a triage-source row is a description of a fetch) and sometimes in a project brief.
- Report each stale sentence with its file, its line, and **what the entry says is now true**. Fixing prose is an ordinary Phase 4 content edit in the vault's own words and language, not a script overwrite, so it is applied under normal approval rather than the four-condition gate above.
- An entry whose Reaction is an action **outside** the vault (register a redirect URI, add a tenant permission, re-consent an account) cannot be verified from disk. Report it as an open operator action and say plainly that you could not check it.
