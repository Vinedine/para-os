# Bootstrap prompt - stand up a new para-os vault

Paste the block below into a Claude Code session (or any markdown-reading agent) whose working directory is the **new vault root** - the folder you just copied `base/` into. It asks three short questions, fills the templates, creates a self-retiring `vault-setup` project that carries the rest of onboarding (your braindump, then connecting your systems), and cleans up after itself.

---

You are setting up a new para-os vault. The working directory is the vault root. It already contains the PARA skeleton (`triage/`, `projects/`, `areas/{business,network}/`, `resources/{prompts,ideas,scripts}/`, `archive/meetings/`), each folder with a placeholder README except two: `triage/` carries only a `.gitkeep` and must never be given a README, and `resources/scripts/` has a real README (the state buckets and `PARAOS_HOME` resolver) that stays as shipped. Also present: the bundled `.claude/` (skills + settings) and `.vscode/` folders, three template files at the root - `CLAUDE.md.template`, `README.md.template`, and `actions.md.template` - all full of `{{placeholders}}`, and this `bootstrap-prompt.md`.

para-os vaults follow a fixed pattern: a PARA layout, a per-vault `CLAUDE.md` documenting the local conventions, an `actions.md` task format using Obsidian Tasks emoji markers, and the principle "don't template an entity shape until a second instance proves it."

Onboarding runs in three phases. **You run phase 1 now**, in this session. Phases 2 and 3 are real work that spans sessions, so you capture them as the vault's first project, `projects/vault-setup/`, which I retire once the vault is loaded and wired.

## Phase 1 - Setup (now)

Interview me with **exactly these three questions, nothing more** - keep it short, I'm new to this:

1. **Vault name** and a one-line description of what it covers.
2. **What this vault is for** - my own life admin, a business I run, a project portfolio, or a client engagement?
3. **Any websites or profiles you can read** to learn about it - a company site, a LinkedIn page, a listing. (Optional; I may have none.)

Do **not** ask about project definitions, extra `areas/` folders, naming conventions, or README framing or ownership. Those all get sensible defaults (below); they are decisions I make later when a real need appears, not on day zero.

Then fill the templates:

- If I gave URLs, **read them** (WebFetch) and draft the four `README.md` sections (Identity, Operating model, Track record, Vision) from what you find. Flag anything you inferred so I can correct it. If I gave none, leave them as short, obvious stubs for the braindump (phase 2) to fill; the four headings stay exactly as the template names them.
- Fill every `{{placeholder}}` in `CLAUDE.md.template` and `README.md.template`. Keep the invariant blocks (the PARA sorting test, Lifecycle, Archive hygiene, Actions, Filing and naming, Language, Memory, File formats, the standing "Do not add" items) exactly as written. A **flavor** skeleton's header comment lists which of these it drops; treat the rest as invariant. For the taxonomy slots, use these **defaults** verbatim unless I volunteered otherwise:
  - **project** = time-bound work with a committed deliverable and deadline.
  - **extra `areas/` subfolders** = none. `business/` + `network/` only; more emerge later.
  - **source-document naming** = `YYYYMMDD <Who> <Description>.<ext>`.
  - **archive `projects/`** = omit unless I said the vault archives finished projects.
  - **"Do not add"** = the three standing items only, plus the accounting line if this is a business or financial vault.
  - **`{{vault-type}}`** = ask me, or default to `vault`. It's a stable label for telling one class of vault from another when I run several; my own tooling may key off it. Leave the `<!-- para-os-template: -->` comment above it exactly as it is - it records which template revision this vault was built from, and `/para-upgrade` reads it later.
- **Rename each template to drop the `.template` suffix** (`CLAUDE.md`, `README.md`).
- **Keep the skeleton's `.gitignore`** as-is. It is not a template and needs no rename. It looks redundant and is not: a machine-wide gitignore that hides `CLAUDE.md` and `.claude/` (common for anyone keeping agent config out of client repos) hides them here too, and a vault whose conventions file is untracked loses the one thing its history is for. It also carries a defensive secret guard, the last line of defence for the rule that credentials live in `~/.paraos/`, never inside a folder that syncs.

**Do not add any of the optional sections below at setup.** They are shapes a vault grows *into*, and one added early costs tokens every session to describe something that isn't there. Add a `## Context` section only if this vault needs scope boundaries or cross-vault context. The rest come later, when the need is real:

- **`## MCP integration intent`** - which connectors this vault uses and for what, one bullet per server. Shared rule: fetch tickets / pages / repo contents on demand; never mirror them into the vault.
- **`## Triage sources`** - extra inputs `/para-triage` pulls beyond the `triage/` folder. A table `| Source | Type | Endpoint | Relevant when |`, one row per source. `Type` is one of `fetch-script` (a `resources/scripts/` script that outputs a thread window, like `outlook.py fetch`), `sync-script` (legacy, a script that writes into `triage/`), `connector: <mcp-server>` (a read-only mailbox read, with the mailbox as `Endpoint`), or `drive` (the Google Drive this vault syncs from, with the **drive id** as `Endpoint`). The `drive` row pulls nothing of its own: it is the lookup that lets `/para-triage` convert a Google-native pointer stub into a real file, and only a Drive-synced vault needs one. Declare the id rather than letting it be inferred - an unscoped Drive query reports "no files found" while the document sits in the folder. `Relevant when` scopes what counts for THIS vault.
- **`## Agenda sources`** - calendars `/para-daily-brief` reads for its 🗓 Agenda, in the same table shape as Triage sources (`connector:` rows only, read-only, the calendar account as `Endpoint`). Only for a vault whose calendar a connector can actually reach; a vault without one keeps meetings by hand in a root `meetings.md`, which stays the fallback and merges when both exist.
- **`## Who writes this vault`** - the roster, once more than one person writes it. A table of person and lane, plus the handful of rules that change when "I" stops resolving: identity comes from outside the vault (the file is shared, so it cannot say who you are), an area is the ownership unit rather than a per-person folder, contact files carry no checkboxes (a file named after a person makes a checkbox read as *their* action when it means an action *about* them), the team is not the network, and one stated convention for the only real failure mode, two people saving one file at once. It is the one optional section that overrides invariant rules, which is why each overridden bullet carries a clause pointing at it. Add it when the second writer arrives, never before: a one-operator vault would pay tokens every session to describe a team that does not exist.
- **`## Operating rules`** - vault-specific working rules that aren't structure: drafting register, domain naming conventions, deliverable style. Do not import another vault's rules.
- **`## README structures`** - canonical section order per entity type, ONLY once a SECOND instance proves the shape.
- **`## Code repos`** - the code repositories this vault steers, one bullet each: repo name, what it does, which area or project owns it. This is the section that makes a vault the layer above several repositories rather than a notebook beside them. Three rules come with it. The linkage is **one-way** - the vault names repos, a repo never names the vault - because repos push to shared remotes and a vault path inside one is a privacy leak. **One system is source of truth per artifact**, everything else holds a copy or a link. And **intent and design stay in the vault while the implementation plan lives with the code**: the brief says what is wanted and why, the repo holds the plan the work was built from, and the vault links the commit rather than restating it.
- **`## Cross-vault references`** - when this vault overlaps another. Full entry where the relationship is primary, a pointer line in the other.
- **`## Project context`** - durable, non-obvious facts about ongoing work not derivable from the files.
- Seed `areas/business/actions.md` from `actions.md.template` with empty `## Next actions` / `## Recurring` headings - real strategic actions emerge from the braindump, not now.

## Phases 2 + 3 - the vault-setup project

Create `projects/vault-setup/` - the vault's first project, since standing the vault up is itself a time-bound deliverable. It holds two files:

**`brief.md`** - a short plan covering:

- **Phase 2, Braindump.** I tell you about this vault in my own words - typed, or as a voice memo / notes I drop into `triage/` for you to read. You fold it into `README.md`, every section real and Vision included (ask where this should end up if I didn't say), and spin out the first real projects, contacts, and actions from it (one `/para-new` run each, so every one gets the sorting test rather than a bare folder).
- **Phase 3, Inventory & connect.** Two tables to fill together:
  - *Systems* - one row per system my work lives in (mail, calendar, drive, accounting, tickets, ...): what it holds · how it's wired in (connector authorized in the agent · MCP server declared in config · integration script in `resources/scripts/`) · status (pending / connected). Only the integration scripts live in the vault; connectors and MCP servers are agent-side, so this table plans and tracks them.
  - *Data sources* - one row per existing folder or inbox to pull from: where it is · what to extract into the vault.

**`actions.md`** (Obsidian Tasks markers) - the concrete next steps:

- `- [ ] Braindump: describe this vault and where it should end up (type it, or drop a recording / notes in triage/)`
- `- [ ] List the systems my work lives in`
- `- [ ] Connect each system - plan the MCP / API wiring`
- `- [ ] Extract existing data from each folder / inbox`

## Finish

- Leave the PARA placeholder READMEs in place - they self-delete as real content arrives. `triage/` is the exception: it gets a `.gitkeep`, never a README.
- Do **not** add entity templates or a "## README structures" section yet; those come once a second instance of an entity type exists.
- Delete the leftover `actions.md.template` and this `bootstrap-prompt.md`. Confirm the vault is clean: filled `CLAUDE.md` + `README.md`, a seeded `areas/business/actions.md`, a `projects/vault-setup/` with `brief.md` + `actions.md`, and no remaining `.template` files.
- Tell me the skills are already bundled in this vault (`.claude/skills/`) so I can run `/para-daily-brief` right away, and that `.claude/settings.json` ships with Claude Code's auto memory turned off (the vault itself is the memory, see `## Memory` in CLAUDE.md); leave that in place. Ask whether I want the read-only / iPad flavor instead of the default editable one (see the repo's `flavors/`).
- Offer to start the braindump (phase 2) right now if I have a few minutes. Once every action in the vault-setup project is done, I retire it - archive or delete `projects/vault-setup/`.
