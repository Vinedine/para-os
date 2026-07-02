# Bootstrap prompt - stand up a new para-os vault

Paste the block below into a Claude Code session (or any markdown-reading agent) whose working directory is the **new vault root** - the folder you just copied `base/skeleton/` into. It asks three short questions, fills the templates, creates a self-retiring `vault-setup` project that carries the rest of onboarding (your braindump, then connecting your systems), and cleans up after itself.

---

You are setting up a new para-os vault. The working directory is the vault root. It already contains the PARA skeleton (`triage/`, `projects/`, `areas/{business,network}/`, `resources/{prompts,ideas}/`, `archive/meetings/`), each folder with a placeholder README, plus three template files at the root - `CLAUDE.md.template`, `README.md.template`, and `actions.md.template` - all full of `{{placeholders}}`, and this `bootstrap-prompt.md`.

para-os vaults follow a fixed pattern: a PARA layout, a per-vault `CLAUDE.md` documenting the local conventions, an `actions.md` task format using Obsidian Tasks emoji markers, and the principle "don't template an entity shape until a second instance proves it."

Onboarding runs in three phases. **You run phase 1 now**, in this session. Phases 2 and 3 are real work that spans sessions, so you capture them as the vault's first project, `projects/vault-setup/`, which I retire once the vault is loaded and wired.

## Phase 1 - Setup (now)

Interview me with **exactly these three questions, nothing more** - keep it short, I'm new to this:

1. **Vault name** and a one-line description of what it covers.
2. **What this vault is for** - my own life admin, a business I run, a project portfolio, or a client engagement?
3. **Any websites or profiles you can read** to learn about it - a company site, a LinkedIn page, a listing. (Optional; I may have none.)

Do **not** ask about project definitions, extra `areas/` folders, naming conventions, or README framing or ownership. Those all get sensible defaults (below); they are decisions I make later when a real need appears, not on day zero.

Then fill the templates:

- If I gave URLs, **read them** (WebFetch) and draft the `README.md` Identity / Operating model / Track record sections from what you find. Flag anything you inferred so I can correct it. If I gave none, leave those sections as short, obvious stubs for the braindump (phase 2) to fill.
- Fill every `{{placeholder}}` in `CLAUDE.md.template` and `README.md.template`. Keep the invariant blocks (Obsidian Tasks markers, filing rules, Language, Memory, File formats, the standing "Do not add" items) exactly as written. For the taxonomy slots, use these **defaults** verbatim unless I volunteered otherwise:
  - **project** = time-bound work with a committed deliverable and deadline.
  - **extra `areas/` subfolders** = none. `business/` + `network/` only; more emerge later.
  - **source-document naming** = `YYYYMMDD <Who> <Description>.<ext>`.
  - **archive `projects/`** = omit unless I said the vault archives finished projects.
  - **"Do not add"** = the three standing items only, plus the accounting line if this is a business or financial vault.
- **Rename each template to drop the `.template` suffix** (`CLAUDE.md`, `README.md`).
- Seed `areas/business/actions.md` from `actions.md.template` with empty `## Next actions` / `## Recurring` headings - real strategic actions emerge from the braindump, not now.

## Phases 2 + 3 - the vault-setup project

Create `projects/vault-setup/` - the vault's first project, since standing the vault up is itself a time-bound deliverable. It holds two files:

**`brief.md`** - a short plan covering:

- **Phase 2, Braindump.** I tell you about this vault in my own words - typed, or as a voice memo / notes I drop into `triage/` for you to read. You fold it into `README.md` and spin out the first real projects, contacts, and actions from it.
- **Phase 3, Inventory & connect.** Two tables to fill together:
  - *Systems* - one row per system my work lives in (mail, calendar, drive, accounting, tickets, ...): what it holds · which connector (MCP / API) reaches it · status (pending / connected). Connectors live in the agent, not the vault, so this table only plans and tracks them.
  - *Data sources* - one row per existing folder or inbox to pull from: where it is · what to extract into the vault.

**`actions.md`** (Obsidian Tasks markers) - the concrete next steps:

- `- [ ] Braindump: describe this vault (type it, or drop a recording / notes in triage/)`
- `- [ ] List the systems my work lives in`
- `- [ ] Connect each system - plan the MCP / API wiring`
- `- [ ] Extract existing data from each folder / inbox`

## Finish

- Leave the PARA placeholder READMEs in place - they self-delete as real content arrives.
- Do **not** add entity templates or a "## README structures" section yet; those come once a second instance of an entity type exists.
- Delete the leftover `actions.md.template` and this `bootstrap-prompt.md`. Confirm the vault is clean: filled `CLAUDE.md` + `README.md`, a seeded `areas/business/actions.md`, a `projects/vault-setup/` with `brief.md` + `actions.md`, and no remaining `.template` files.
- Tell me the skills are already bundled in this vault (`.claude/skills/`) so I can run `/para-daily-brief` right away, and ask whether I want the read-only / iPad flavor instead of the default editable one (see the repo's `flavors/`).
- Offer to start the braindump (phase 2) right now if I have a few minutes. Once every action in the vault-setup project is done, I retire it - archive or delete `projects/vault-setup/`.
