# Bootstrap prompt - stand up a new para-os vault

Paste the block below into a Claude Code session (or any markdown-reading agent) whose working directory is the **new vault root** - the folder you just copied `base/` into. It asks four short choice questions (a fifth for a business) and two open ones, fills the templates, creates a self-retiring `vault-setup` project that carries the rest of onboarding (a short guided brainstorm, then connecting your systems), and cleans up after itself.

---

You are setting up a new para-os vault. The working directory is the vault root. It already contains the PARA skeleton (`triage/`, `projects/`, `areas/{business,network}/`, `resources/{prompts,ideas,scripts}/`, `archive/meetings/`), each folder with a placeholder README except two: `triage/` carries only a `.gitkeep` and must never be given a README, and `resources/scripts/` has a real README (the state buckets and `PARAOS_HOME` resolver) that stays as shipped. Also present: the bundled `.claude/` folder (skills, rules, settings), two template files at the root - `CLAUDE.md.template` and `README.md.template` - both full of `{{placeholders}}`, and this `bootstrap-prompt.md`.

para-os vaults follow a fixed pattern: a PARA layout, a per-vault `CLAUDE.md` documenting the local conventions, an `actions.md` task format using Obsidian Tasks emoji markers, and the principle "don't template an entity shape until a second instance proves it."

Onboarding runs in three phases. **You run phase 1 now**, in this session. Phases 2 and 3 are real work that spans sessions, so you capture them as the vault's first project, `projects/vault-setup/`, which I retire once the vault is loaded and wired.

## Phase 1 - Setup (now)

**Ask before you write anything.** Call `AskUserQuestion` now, as your first action, and write no file until my answers are in. The questions are where you learn what this vault is; the install prompt carries nothing about it. Where the session has no `AskUserQuestion`, ask all six questions below as one short numbered message and stop there until I reply.

**First, one call of four short choice questions** - I'm new to this. **Other** is always where I type my own answer. The rule behind the shapes is `.claude/skills/para-shared/asking.md` (`## A question with a suggested answer`):

| `header` | Question | Options |
|---|---|---|
| `Name` | What should this vault be called? | the vault folder's own name, tidied into a title `(Recommended)` · the same name with `Vault` after it |
| `Purpose` | What is this vault for? | my own life admin · a business I run · a project portfolio · a client engagement |
| `Language` | Which language should the agent answer in? | English · Nederlands · Français |
| `Read where` | Where will this vault be read? | here, in Claude Code `(Recommended)` · read-only on an iPad as rendered PDFs (the `readonly-ipad` delivery) |

`Purpose` and `Language` carry no recommendation: they are facts only I hold. If my install prompt said something about the vault anyway, order those options by it, but still ask.

**Where `Purpose` is a business I run** (or my Other answer describes one) **and `Read where` is Claude Code**, follow with one more call: `Sales`, "Do you sell to clients, and want to track prospects, demos and deals?", options yes, add the sales module `(Recommended)` · not now. Never on the iPad delivery, which the module does not support. Without the tool, ask it as one line after my reply.

**Then two open questions as one short numbered message**:

1. In one line, what does this vault cover?
2. Is there a website or profile I can read to learn about it - a company site, a LinkedIn page, a listing? (Optional; "none" is fine.)

Do **not** ask about project definitions, extra `areas/` folders, naming conventions, vault type, or README framing or ownership. Those all get sensible defaults (below); they are decisions I make later when a real need appears, not on day zero.

Then fill the templates:

- If I chose read-only iPad, first run steps 1 and 2 of the setup in the para-os clone's `addons/readonly-ipad/README.md` (its skeleton replaces both templates); its step 3 changes apply to everything below.
- If I gave websites, **read them** (WebFetch) and draft the four `README.md` sections (Identity, Operating model, Track record, Vision) from what you find. Flag anything you inferred so I can correct it. If I gave none, leave them as short, obvious stubs for the brainstorm (phase 2) to fill; the four headings stay exactly as the template names them.
- If I said yes to the sales module, run the setup in the para-os clone's `addons/sales/README.md` once the templates are filled, with the register at `areas/business/leads.md`: `**Modules:** sales` under the `**Type:**` line, its `CLAUDE.md.sections` merged, `.claude/rules/deal-brief.md` copied in, the register created with its `## Open` and `## Closed` headings each carrying `_None currently._`, and the weekly review under `## Recurring` in `areas/business/actions.md`, first dated the next Friday. Draft the **target profile** its Qualified stage tests against into `README.md`'s Operating model where the websites support one, flagged as inferred; otherwise add it to the vault-setup brief as an open question for phase 2. "Not now" writes nothing from the module.
- Fill every `{{placeholder}}` in `CLAUDE.md.template` and `README.md.template`. Keep the invariant blocks (the PARA sorting test, Lifecycle, Archive hygiene, Actions, Filing and naming, Language, Memory, File formats, the standing "Do not add" items) exactly as written. A **delivery** skeleton's header comment lists which of these it drops; treat the rest as invariant. For the taxonomy slots, use these **defaults** verbatim unless I volunteered otherwise:
  - **project** = time-bound work with a committed deliverable and deadline.
  - **extra `areas/` subfolders** = none. `business/` + `network/` only; more emerge later.
  - **source-document naming** = `YYYYMMDD <Who> <Description>.<ext>`, the same default `.claude/rules/filing.md` states. Leave that file and `.claude/rules/figures.md` in place: they are conventions the vault needs from its first filed document, not shapes waiting for a second instance. Leave `.claude/rules/working-preferences.md` in place too, its `## Preferences` empty: it fills as I state how I like to work.
  - **archive `projects/`** = omit unless I said the vault archives finished projects.
  - **`{{operator language}}`** = the language I picked; default to English.
  - **"Do not add"** = the standing items only, plus the accounting line if this is a business or financial vault.
  - **`{{vault-type}}`** = default to `vault`. It's a stable label for telling one class of vault from another when I run several; my own tooling may key off it. Leave the `<!-- para-os-template: -->` comment above it exactly as it is - it records which template revision this vault was built from, and `/para-upgrade` reads it later.
- **Rename each template to drop the `.template` suffix** (`CLAUDE.md`, `README.md`).
- **Keep the skeleton's `.gitignore`** as-is, unrenamed: it re-includes `CLAUDE.md` and `.claude/` where a machine-wide gitignore hides them, and guards against committing secrets.
- Seed `areas/business/actions.md` with the heading `# Business - Actions` and empty `## Next actions` / `## Recurring` sections (no example items, just the headings) - real strategic actions emerge from the brainstorm, not now.

**Do not add any of the optional sections below at setup.** They are shapes a vault grows *into*, and one added early costs tokens every session to describe something that isn't there. Add a `## Context` section only if this vault needs scope boundaries or cross-vault context. The rest come later, when the need is real:

- **`## MCP integration intent`** - which connectors this vault uses and for what, one bullet per server. Shared rule: fetch tickets / pages / repo contents on demand; never mirror them into the vault.
- **`## Triage sources`** - extra inputs `/para-triage` pulls beyond the `triage/` folder. A table `| Source | Type | Endpoint | Relevant when |`, one row per source. `Type` is one of `fetch-script` (a `resources/scripts/` script that outputs a thread window, like `outlook.py fetch`), `sync-script` (legacy, a script that writes into `triage/`), `connector: <mcp-server>` (a read-only mailbox read, with the mailbox as `Endpoint`), or `drive` (the Google Drive this vault syncs from, with the **drive id** as `Endpoint`). The `drive` row pulls nothing of its own: it is the lookup that lets `/para-triage` convert a Google-native pointer stub into a real file, and only a Drive-synced vault needs one. Declare the id rather than letting it be inferred - an unscoped Drive query reports "no files found" while the document sits in the folder. `Relevant when` scopes what counts for THIS vault.
- **`## Agenda sources`** - calendars `/para-daily-brief` reads for its 🗓 Agenda, in the same table shape as Triage sources (`connector:` rows only, read-only, the calendar account as `Endpoint`). Only for a vault whose calendar a connector can actually reach; a vault without one keeps meetings by hand in a root `meetings.md`, which stays the fallback and merges when both exist.
- **`## Who writes this vault`** - the roster, once more than one person writes it. A table of person and lane, plus the handful of rules that change when "I" stops resolving: identity comes from outside the vault (the file is shared, so it cannot say who you are), an area is the ownership unit rather than a per-person folder, contact files carry no checkboxes (a file named after a person makes a checkbox read as *their* action when it means an action *about* them), the team is not the network, and one stated convention for the only real failure mode, two people saving one file at once. It is the one optional section that overrides invariant rules, which is why each overridden bullet carries a clause pointing at it. Add it when the second writer arrives, never before.
- **`## Operating rules`** - vault-specific working rules that aren't structure: drafting register, domain naming conventions, deliverable style. Do not import another vault's rules.
- **A `.claude/rules/` shape file** (`brief-structure.md`, `readme-structure.md`, or a topic file) - canonical section order per entity type, ONLY once a SECOND instance proves the shape. Extract straight there, its pointer under a `## Entity structures` section placed after `## Filing and naming` in `CLAUDE.md` (see `## Do not add`); never draft it as an inline `CLAUDE.md` section first.
- **`## Code repos`** - the code repositories this vault steers, one bullet each: repo name, what it does, which area or project owns it. This is the section that makes a vault the layer above several repositories rather than a notebook beside them. Three rules come with it. The linkage is **one-way** - the vault names repos, a repo never names the vault - because repos push to shared remotes and a vault path inside one is a privacy leak. **One system is source of truth per artifact**, everything else holds a copy or a link. And **intent and design stay in the vault while the implementation plan lives with the code**: the brief says what is wanted and why, the repo holds the plan the work was built from, and the vault links the commit rather than restating it.
- **`## Cross-vault references`** - when this vault overlaps another. Full entry where the relationship is primary, a pointer line in the other.
- **`## Project context`** - durable, non-obvious facts about ongoing work not derivable from the files.

## Phases 2 + 3 - the vault-setup project

Create `projects/vault-setup/` - the vault's first project, since standing the vault up is itself a time-bound deliverable. It holds two files:

**`brief.md`** - a short plan covering:

- **Phase 2, Brainstorm.** Four short rounds, each one `AskUserQuestion` call (a numbered message where the session has none), then a plan I approve. Nothing is created until I approve it.
  1. *Your week* (`multiSelect`): what eats the most time? Email · Paperwork and finding documents · Clients and follow-ups · Money and invoices. Feeds the areas and the first skill candidates.
  2. *Where things live* (`multiSelect`): Mail and calendar · Cloud drives or shared folders · Accounting or business software · Paper, chat apps, or in my head. Feeds the phase 3 *Systems* table.
  3. *The next 90 days*: what must be done or decided, what keeps slipping, and what question I wish I could just ask. Open answers with nothing to suggest, so a short numbered message rather than the tool; a voice memo or notes I drop into `triage/` answer it just as well, and you read them from there.
  4. *One win*: which single thing would matter most this month? A choice drafted from rounds 1-3, the most pressing `(Recommended)`.

  Then propose 3-5 projects and areas, the connections to set up, and one task to do today, and put them to me item by item per `.claude/skills/para-shared/asking.md`. Create only what I approve, one `/para-new` run each, so every one gets the sorting test rather than a bare folder. Fold my answers into `README.md`, every section real and Vision included (ask where this should end up if I didn't say).
- **Phase 3, Inventory & connect.** Two tables to fill together:
  - *Systems* - one row per system my work lives in (mail, calendar, drive, accounting, tickets, ...): what it holds · how it's wired in (connector authorized in the agent · MCP server declared in config · integration script in `resources/scripts/`) · status (pending / connected). Only the integration scripts live in the vault; connectors and MCP servers are agent-side, so this table plans and tracks them.
  - *Data sources* - one row per existing folder or inbox to pull from: where it is · what to extract into the vault.

**`actions.md`** (Obsidian Tasks markers) - the concrete next steps:

- `- [ ] Brainstorm: four short rounds on my week, my systems, the next 90 days and one win (or drop a recording / notes in triage/)`
- `- [ ] List the systems my work lives in`
- `- [ ] Connect each system - plan the MCP / API wiring`
- `- [ ] Extract existing data from each folder / inbox`

## Finish

- Leave the PARA placeholder READMEs in place - they self-delete as real content arrives. `triage/` is the exception: it gets a `.gitkeep`, never a README.
- Do **not** add entity templates or a `.claude/rules/` shape file yet, beyond what an adopted module ships; those come once a second instance of an entity type exists.
- Delete this `bootstrap-prompt.md`. Confirm the vault is clean: filled `CLAUDE.md` + `README.md`, a seeded `areas/business/actions.md` (and `areas/business/leads.md` with the sales module), a `projects/vault-setup/` with `brief.md` + `actions.md`, and no remaining `.template` files.
- Tell me the skills are already bundled in this vault (`.claude/skills/`) so I can run `/para-daily-brief` right away, and `/para-pipeline` for the deal board where the sales module went in, and that `.claude/settings.json` ships with Claude Code's auto memory turned off (the vault itself is the memory, see `## Memory` in CLAUDE.md); leave that in place. Ask whether this vault needs a **flavor** (what it is about) or a further **module** (a function beside that), both under the para-os clone's `addons/`. Each becomes one line under `**Type:**` (`**Flavor:** <name>`, `**Modules:** <name>, <name>`), as does the iPad delivery where I chose it (`**Delivery:** <name>`); a flavor or module then runs its own README's setup, which merges its `CLAUDE.md.sections` beside the vault's sections. Default to neither.
- Offer to start the brainstorm (phase 2) right now if I have ten minutes. Once every action in the vault-setup project is done, I retire it - archive or delete `projects/vault-setup/`.
