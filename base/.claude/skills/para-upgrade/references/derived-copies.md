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
- **The vault's own `CLAUDE.md` claims about itself**: folders it says exist, scripts it says are installed, files it says carry a given snippet. Check each against disk. These rot quietly and every one is cheap to verify.

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
- *Marker matches, content differs* - report it loudly and by name. The marker is now known to be wrong, so anything that trusted it was wrong too.
- *No marker* - an older copy, or a script written for that vault alone. Never guess which integration it came from: that is how a hand-merge destroys a one-off. Name it, ask the user which shipped integration it is (if any), and stamp the copy at the revision they say they installed from. A script the user says is theirs stays unmarked and is named as skipped.

**Report, never overwrite** - this is the one read-only item in an otherwise applying skill. These scripts carry the vault's own config and local fixes, so re-syncing one is a merge the user makes with the diff in front of them.

## Edge case

- **A script's marker resolves to no folder at the ref** - neither `integrations/<name>/` nor `flavors/<name>/pipeline/` exists. The integration was removed, or the marker was hand-typed. Report it as unresolvable and leave the script alone. Never match it to a folder with a similar name: a wrong match turns the next hand-merge into a rewrite of a script that was doing its job.
