# Bootstrap prompt - stand up a new para-os vault

Paste the block below into a Claude Code session (or any markdown-reading agent) whose working directory is the **new vault root** - the folder you just copied `base/skeleton/` into. It interviews you, fills the templates, seeds a starter `actions.md`, and cleans up after itself.

---

You are setting up a new para-os vault. The working directory is the vault root. It already contains the PARA skeleton (`triage/`, `projects/`, `areas/{business,network}/`, `resources/{prompts,ideas}/`, `archive/meetings/`), each folder with a placeholder README, plus three template files at the root - `CLAUDE.md.template`, `README.md.template`, and `actions.md.template` - all full of `{{placeholders}}`, and this `bootstrap-prompt.md`.

para-os vaults follow a fixed pattern: a PARA layout, a per-vault `CLAUDE.md` documenting the local conventions, an `actions.md` task format using Obsidian Tasks emoji markers, and the principle "don't template an entity shape until a second instance proves it."

Interview me briefly - one round of questions, don't over-ask - then fill the templates:

1. **Vault name** and a one-line description of what it covers.
2. **What this vault is for** - a person's life admin, a business, a project portfolio, a client engagement?
3. **What a "project" means here** - time-bound deliverable with a deadline (the default), or something domain-specific?
4. **Extra `areas/` subfolders** beyond `business/` and `network/` (e.g. `properties/`, `clients/`, `health/`)?
5. **Source-document naming convention**, if you have one (e.g. `YYYYMMDD <Who> <Description>.<ext>`). `/triage` applies it literally; leave it blank and `/triage` will ask before renaming.
6. **README framing** - what the master document should emphasise (identity, operating model, track record / portfolio). Any legal-entity or ownership details for the Identity section.
7. **Anything that does NOT belong in this vault** - it goes in the "Do not add" list (e.g. accounting kept in a separate finance vault).

Then:

- Fill every `{{placeholder}}` in `CLAUDE.md.template` and `README.md.template` with the answers, keeping the invariant blocks (Obsidian Tasks markers, filing rules, Language, the standing "Do not add" items) exactly as written - only fill the vault-specific slots. **Rename each to drop the `.template` suffix** (`CLAUDE.md`, `README.md`).
- Seed a starter strategic actions file at `areas/business/actions.md` from `actions.md.template`, with 1-3 real first tasks drawn from the interview (or just the empty `## Next actions` / `## Recurring` headings if there's nothing concrete yet). Per-project and per-contact `actions.md` files get created later, where the work actually lands.
- Leave the PARA placeholder READMEs in place - they self-delete as real content arrives.
- Do **not** add entity templates or a "## README structures" section yet; those come once a second instance of an entity type exists.
- When done, delete the leftover `actions.md.template` and this `bootstrap-prompt.md`, then confirm the vault is clean: a filled `CLAUDE.md` + `README.md`, a seeded `areas/business/actions.md`, and no remaining `.template` files.
- Finally, tell me to install the skills (`base/skills/` -> `~/.claude/skills/`) and run `/daily-brief`, and ask whether I want the read-only / iPad flavor instead of the default editable one (see the repo's `flavors/`).
