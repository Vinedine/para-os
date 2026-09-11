# Phase 3 - Derived copies: rules and scripts

**This is the phase that pays for the skill.** A vault's rules get copied into places a template diff never looks, and a stale copy silently re-breaks the vault on its next run. An installed integration script is the same failure in code rather than prose: the vault holds a copy, the master moved, and nothing on either side says so.

It is also the one phase Phase 0 runs when the template revisions already match, because it keys off each script's own marker rather than the template's.

## Sweep for

- **Vault-local skills** (`.claude/skills/`). A skill that restates a rule the changelog just changed will undo this migration the next time it runs. Read every one; fix the rule text, not just the skill name.
- **Skill names** in `README.md`, `meetings.md`, briefs, and other skills. Renames don't propagate on their own. Verify each name still exists as a skill before repointing; drop references to skills that no longer exist rather than guessing a replacement.
- **Installed skill copies**, in both places they can live, because each goes stale on its own:
  - *The vault's bundled `.claude/skills/`*, which the skeleton ships so an adopter can run `/para-daily-brief` the moment bootstrap finishes. **These are skeleton content and this phase audits them like any other skeleton file.** They are also the copy that shadows the user-level install, so a stale one silently overrides a correct global skill for every session run in that vault - the failure is invisible precisely because the vault looks equipped. Diff each against the ref's master and report; a bundled skill more than one revision behind is worth calling out by name, since bootstrap re-creates these on every new vault and a one-off cleanup cannot hold the property.
  - *The user-level install*, if the vault runs on that instead. Diff against the ref's masters and report drift. Syncing them is a machine-level action, so propose it, don't do it silently.

  If both exist, say which one actually wins for this vault before reporting either as stale.

  **Normalize line endings on these diffs too**, exactly as the integration scripts below require. A `git show` master is LF and an installed copy on Windows is usually CRLF, so a byte-exact compare reports every file in the tree as drifted while the content is identical. This one fails loudly rather than quietly, which is worse than it sounds: a phantom drift list, produced by the one skill whose job is to say what is stale, teaches the reader to discount the real entries next to it.
- **The vault's own `CLAUDE.md` claims about itself.** These rot quietly, and "check each against disk" is not a procedure - it is a good intention that survives exactly as long as the agent's patience. Enumerate the claims first, then verify each with a command, and report the list with a verdict per row rather than a sentence saying they were checked. A claim that was never turned into a command was never checked.

  | Claim shape | How it reads | The check |
  |---|---|---|
  | A path exists | "proposals live in `projects/ticketing-platform-replacement/sources/`" | `test -e` on the path |
  | A script is installed | "`scripts/` = `granola.py`, `outlook.py`..." | `ls` the folder; every name in the prose must be on disk, **and every script on disk must be in the prose** |
  | A config holds a key or value | "`outlook.config.json` carries `\"match_all\": true`" | read the file and compare the literal value |
  | A file carries a snippet | "`.claude/settings.json` holds `autoMemoryEnabled: false`" | grep the file for it |
  | A count or inventory | "4 vendor responses", "3 vendor calls" | count the folders and compare |
  | A named skill or command exists | "emptied via `/para-triage`" | the skill must resolve; a renamed one is repointed, a removed one dropped |

  **Quoted literals are the ones that rot fastest**, because a config key outlives the sentence that describes it: `match_all` survived a revision in a live vault after the key itself had been deleted, and nothing read it as wrong because nobody opened the config. Any backticked value in the prose is a claim - treat it as one. The check runs **in both directions** for inventories: prose naming something absent is stale, and disk holding something the prose never names is undocumented, which reads as "not installed" to the next session.

## Installed integration scripts

Every script a para-os integration ships carries `para-os-integration: <name> <revision>` in its header. **Grep the whole vault for that marker, not just `resources/scripts/`** - a flavor may install its scripts elsewhere (the readonly-ipad render pipeline sits at the vault root), and a folder-scoped grep would never see them.

**Compare the content, never the marker string.** The marker says which integration a file came from; it does not say what the file contains. A copy whose header was bumped by hand while the code stayed old reports clean under a string compare, permanently - that is a real failure this check shipped with, and the whole point of the phase is to catch exactly that. So for each marked script:

```bash
git show <ref>:integrations/<name>/<file> | diff - "<vault>/<path-to-copy>"
```

**Resolving `<name>` to a master, in this order:** `integrations/<name>/<file>` first, then `flavors/<name>/pipeline/<file>`. A flavor's render pipeline is a shipped, installed, drifting copy exactly like an integration, so it carries the same marker and is checked the same way - it just lives under `flavors/`. If neither path exists at the ref but the *folder* does, the file was **renamed upstream**: when that folder ships exactly one non-test script, that is the master - diff against it and report the rename as part of the verdict, since a rename is the one drift a filename match can never find. If the folder ships several, name them and ask which. Only when the folder itself is absent is the marker unresolvable: report it, leave the script alone, and never match it to a folder with a similar name.

Normalize line endings before reading anything into the verdict (`git show` emits LF; a Windows checkout of the same file is CRLF, and a whole-file diff of nothing but line endings is noise). Then report from the diff:

- *Identical* - say so and move on. This is the only verdict that needs no follow-up, and it is worth printing: silence reads the same as "not checked".
- *Behind* - the copy lacks changes the master has. Name the script, the marker revision on each side, the changelog entries in between, and **what the diff actually shows**. A diff that touches only a config block is a different conversation from one that touches logic.
- *Ahead* - the copy has changes the master lacks. Say so and suggest folding them back into `integrations/` rather than touching the vault. Four render-pipeline copies carrying a feature the product never got is how this verdict earns its place.
- *Both* - the two diverged. The commonest real case, and the one a marker compare renders invisible: the copy is behind on the master's changes and ahead on its own. Report it as divergence, not as "behind".
- *Marker matches, content differs* - **two very different cases, and calling both an alarm is how the alarm stops being read.** Say which one this is before saying anything else:
  - *Within-revision drift.* The copy was taken from that revision's branch before its tip settled, so both sides honestly carry the same marker. This is the **normal** state while a revision is in development and the expected verdict on a test upgrade: report it as "behind within `<revision>`", describe the diff, and move on. It is not evidence that anything is wrong.
  - *A hand-bumped marker.* The copy carries a revision whose content it never had - someone edited the header instead of the file. **This** is the loud one: the marker is now known to be lying, so every earlier run that trusted it reported a false clean.

  Nothing in the two files distinguishes them, so **do not guess from the diff**. The separator is provenance: if the ref is an unmerged or recently-moved branch, or the vault's copy plausibly predates the tip, it is the first case. Ask the user which when it matters, and prefer the benign reading during a pre-release pass - a released revision is immutable, so within-revision drift can only exist before the release, and after it the second case is the only one left.
- *No marker* - an older copy, or a script written for that vault alone. Never guess which integration it came from: that is how a hand-merge destroys a one-off. Name it, ask the user which shipped integration it is (if any), and stamp the copy at the revision they say they installed from. A script the user says is theirs stays unmarked and is named as skipped.

**Report, never overwrite** - this is the one read-only item in an otherwise applying skill. These scripts carry the vault's own config and local fixes, so re-syncing one is a merge the user makes with the diff in front of them.

### The one sanctioned overwrite

A user who reads the diff and says "sync it" is making exactly the decision the rule reserves for them. An overwrite needs **all four**:

1. **The user asked**, in this session, for that script or for the integrations generally. Never infer it from a general "upgrade the vault".
2. **Equivalence is proven mechanically, not read.** For Python, parse both sides and compare the trees with docstrings stripped (`ast.dump` after removing each module's, class's and function's leading string expression); a byte-identical dump means the only differences are comments, docstrings and formatting. For another language, use that language's equivalent, and where there is none, say so and fall back to reporting. **Print the verdict** - an unproven claim of equivalence is worse than no claim, because it launders a guess into a result.
3. **The copy is not *ahead*.** Divergence means local work exists, and only the user can decide what survives; proven-equivalent-but-behind is the sole safe shape.
4. **It is verified after the write**, by re-diffing against the master and running the integration's own test suite (`integrations/<name>/test_*.py`) against the installed copy, not against the master. A sync that silently broke the copy is the failure this whole phase exists to prevent.

## The prose that documents an integration

A script and the prose describing it drift apart, and **only the script is checked by anything**. The vault's `resources/scripts/README.md`, its `## Triage sources` row, and any `## MCP integration intent` block are hand-written descriptions of behaviour the integration owns; when that behaviour changes, a straight file copy updates the script and leaves every sentence about it untouched. The result passes the diff above cleanly while telling the next session that login uses a flow it abandoned, or that a record is a message when it is now a thread. A wrong README is worse than a missing one: it is read, believed, and acted on.

So for every integration whose changelog entries fall inside this migration's delta, **read the entry for caller-visible changes and grep the vault's prose for the claims they invalidate.** Caller-visible means: what the tool reads, what a record represents, how a count is arrived at, how authentication happens, which flags exist, and anything the entry itself frames as a Reaction for the operator. Wording changes and internal refactors are not.

- Search the vault, not just `resources/scripts/README.md` - the same claim is usually restated in `CLAUDE.md` (a triage-source row is a description of a fetch) and sometimes in a project brief.
- Report each stale sentence with its file, its line, and **what the entry says is now true**. Fixing prose is an ordinary Phase 4 content edit in the vault's own words and language, not a script overwrite, so it is applied under normal approval rather than the four-condition gate above.
- An entry whose Reaction is an action **outside** the vault (register a redirect URI, add a tenant permission, re-consent an account) cannot be verified from disk. Report it as an open operator action and say plainly that you could not check it - do not let a documentation pass imply the environment was configured.

## Edge case

- **A script's marker resolves to no folder at the ref** - neither `integrations/<name>/` nor `flavors/<name>/pipeline/` exists. The integration was removed, or the marker was hand-typed. Report it as unresolvable and leave the script alone. Never match it to a folder with a similar name: a wrong match turns the next hand-merge into a rewrite of a script that was doing its job.
