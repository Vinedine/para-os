# para-os

**Run your work out of one structured place, with an AI assistant on top.**

> **You need** the [Claude desktop app](https://claude.com/download) and [Git](https://git-scm.com/downloads), on Windows or macOS. **Start at the [Quickstart](#quickstart).**

The hard part of AI assistance isn't the assistant. It's that everything it needs is scattered across drives, inboxes, and people's heads. Point a capable assistant at a shapeless folder and you get a clever helper rummaging through a messy cabinet: it can search, at best.

**para-os is the cabinet.** A free, do-it-yourself kit for anyone whose information is scattered: a practice, a business you run, a project, a household. It's a folder you copy, not a program you install: a ready-made set of folders with one obvious place for everything (following [PARA](https://fortelabs.com/blog/para/), the filing method, hence the name), house rules in plain language that tell the assistant how to behave, and a handful of routines for the recurring chores (process the inbox, brief me each morning, tidy up, archive what's done).

You bring your files and connect your sources (your inbox and its archive, calendar, meeting recordings, accounting); the assistant reads across *all of it at once*, cross-referenced into one answer instead of leaving you to check each silo by hand. The questions that used to mean an afternoon of digging just get answered:

- "What's the full history with this client, across email and our files?"
- "What did we agree with the bank in March, and where's the document?"
- "Pull every order this supplier sent and flag what's still open."

And it does more than answer: what arrives gets filed by the assistant, not by you, so the vault grows into a fuller picture every week; it drafts what goes out, and writes the small throwaway tool it needs when it hits a wall.

Everything stays ordinary files (PDFs, scans, spreadsheets, Markdown) in ordinary folders on your own disk. No app, no database, no lock-in - the data outlives every assistant you point at it.

```text
  Scattered today          →          One structured home with para-os
  ───────────────                     ────────────────────────────────
  drives                              Projects
  inboxes                             Areas
  people's heads                      Resources
  ERP · Jira · files                  Archive
  external systems                    + triage inbox

  the assistant can                   the assistant does the work,
  search, at best                     across all of it
```

## What it looks like in practice

**Running a business.** A scanned letter from the tax office lands in the inbox. You ask the assistant to process it: it reads the letter, files it under a proper name, and adds "respond before 1 July" to the to-do list. With your mail connected, it cross-references what it finds ("the accountant requested a postponement on 12 May") - and then does the next bit too: drafts the reply for you to send, and when the figures it needs are buried in a spreadsheet it can't parse cleanly, it writes a throwaway script on the spot to pull them. Next morning, your daily brief is one page of everything due, plus today's meetings.

**IT projects.** Connect Jira, Azure DevOps, and your mail. The morning brief checks your to-do list against the live sprint board; "what's still blocking the release?" is answered from the board plus your own files.

**At home.** School letters, insurance renewals, the contractor's quote: same folders, same routines. One list of what needs an answer, and it remembers what the insurer wrote last year.

## Three layers, and para-os owns the bottom one

Any "AI on top of my stuff" setup is three layers stacked. Naming them shows where para-os sits, and why it isn't competing with the tools it gets compared to:

1. **Substrate (your files)** - the files and how they're organised. **This is para-os.**
2. **Agent (the assistant)** - the model that reads and writes them: Claude Code, Cursor, Codex, Gemini CLI, Claude Cowork.
3. **Interface (how you work with it)** - how you drive it: the Claude desktop app, an editor like VS Code, a notes app, a chat app, PDFs on an iPad.

para-os owns layer 1 and is built for Claude Code: the conventions are plain Markdown any agent can read, but the skills and the `CLAUDE.md` contract are Claude Code formats. Almost nobody does the layer-1 work because it feels like filing, not engineering. That's exactly why it pays off: an agent is only as good as the files you point it at, and that leverage grows as agents get better. The files are the memory - the folder on disk is the durable state, the agent reads it fresh each session, and the git diff is the audit log. No memory features, no chat-history dependence.

You stay the operator: you hold the goals, the assistant does the work - and when something is ambiguous or it can't do a step reliably, it says so and asks, rather than confidently handing you the wrong thing.

## You don't need to be a programmer

You work in one free app: the [Claude desktop app](https://claude.com/download), which runs [Claude Code](https://claude.com/claude-code), Anthropic's AI assistant, in its Code tab (the AI itself needs a paid Claude plan). Point it at your vault folder and you get your files on one side and a chat box on the other. You type plain English; the assistant handles the files. Those files are **Markdown** (the `.md` ending): plain text with a few simple marks, readable on any device. If you can use email and a file explorer, you can run this.

If you already live in a code editor, [VS Code](https://code.visualstudio.com/) runs the same assistant over the same folders, and it's the better window when you're working on code as well as documents. It's the power-user path, not the starting point: the desktop app is a nicer place to work for everyone else, which is most people.

## The vault

A vault is one folder tree per life context: a client engagement, a business, family admin. Keep contexts in separate vaults so the agent stays focused and nothing leaks across boundaries.

```
your-vault/
├── CLAUDE.md      # the contract: local conventions, read by the agent at runtime
├── README.md      # master document; derived outputs regenerate from it
├── triage/        # capture inbox; /para-triage empties it
├── projects/      # time-bound work; one folder per project: brief.md + actions.md + sources/
├── areas/         # ongoing responsibilities; contacts in areas/network/, one file per person
├── resources/     # reusable reference; not-yet-projects in resources/ideas/
└── archive/       # anything inactive; cross-cutting dated records in archive/meetings/
```

`triage/` is para-os's addition to stock PARA: a capture inbox for anything you can't file in ten seconds. Capture stays frictionless because filing is delegated to the agent.

The conventions the templates encode:

- **`CLAUDE.md` is the contract.** Each vault documents its own rules - what a "project" means here, the naming convention, an explicit "do not add" list. The skills read it at runtime; nothing is hardcoded.
- **One source of truth.** The root `README.md` is the master document; decks, web copy, and summaries regenerate from it.
- **Ideas are not projects.** A concept stays in `resources/ideas/` until someone's waiting on a deliverable or money is committed, then it promotes to `projects/`.
- **Actions live with their context.** Tasks sit in the project, idea, or contact file they belong to, as markdown checkboxes with [Obsidian Tasks](https://publish.obsidian.md/tasks/) emoji markers (`📅` due, `🛫` start, `🔁` recurring, `🔺🔼🔽⏬` priority). Regex-parseable; Obsidian itself optional.
- **Scripts live in the vault, their secrets don't.** A persistent tool the agent writes goes in `resources/scripts/`; its credentials, caches, and bulk data live outside the vault under `~/.paraos/` (resolved via `PARAOS_HOME`), so nothing sensitive syncs to a cloud drive or git remote and no large file bloats the vault.
- **Briefs don't rot.** Stable facts (decisions, dates, commitments) are append-only; only the volatile "where things stand" notes get rewritten - so a brief never degrades into summaries of summaries.

## Quickstart

**1. Install Git** if you don't have it. On Windows, download it from [git-scm.com](https://git-scm.com/downloads/win) and accept the defaults; on a Mac, macOS offers to install it the first time it is needed. The setup uses it to fetch para-os, and your vault uses it to keep its history.

**2. Make an empty folder** for the vault, wherever you keep your files (your cloud drive is fine), and not inside an existing vault.

**3. Open it in the Claude desktop app.** In the **Code** tab, click **New** at the top of the sidebar, keep **Local**, click **Select folder** and pick the folder. Don't use the `+` beside a folder already in the sidebar: that opens the session inside *that* folder, which is how a new vault ends up inside an old one.

**4. Paste this**, exactly as it is:

```text
Set up a new para-os vault in this folder: read https://raw.githubusercontent.com/Vinedine/para-os/stable/INSTALL.md and follow it.
```

It downloads the kit, copies [`base/`](base/) in, and runs the bootstrap interview: a few short questions about the vault, then it fills `CLAUDE.md` and `README.md` and creates a self-retiring `vault-setup` project that walks you through the rest. The steps are in [`INSTALL.md`](INSTALL.md): read what it will do before you paste it, or follow it by hand.

**5. Run `/para-daily-brief`.** The vault answers from day one, and better once you run the short brainstorm the `vault-setup` project starts with.

To see a lived-in vault first, open [`examples/belfoot-vault/`](examples/belfoot-vault/), a fictional consulting engagement; [`examples/`](examples/README.md) says how to run the skills against it.

> **Want it set up for you?** The kit is free. If you'd rather get your business working with AI without doing the setup yourself, that's the **AI Workspace** engagement I offer - [get in touch](https://trotstar.tech).

## The skills

| Skill | What it does |
|---|---|
| [`/para-triage`](base/.claude/skills/para-triage/SKILL.md) | Empties `triage/`: identifies each loose file, proposes a destination and a convention-conform rename, executes after your approval. |
| [`/para-daily-brief`](base/.claude/skills/para-daily-brief/SKILL.md) | Where the vault stands: vault state, what is due now (capped at five), health flags, ideas, agenda and triage, closing on one next action. |
| [`/para-deep-clean`](base/.claude/skills/para-deep-clean/SKILL.md) | Periodic maintenance: structural audit, README normalisation, closing documented open items by reading the source files. |
| [`/para-new`](base/.claude/skills/para-new/SKILL.md) | Starts one project, area, idea, or contact: sorts it first, so committed work becomes a project, a maintained responsibility becomes an area, and a concept stays an idea, asks the two or three questions that shape needs, and scaffolds it. Also promotes an idea. |
| [`/para-archive`](base/.claude/skills/para-archive/SKILL.md) | Closes out one finished project, shelved idea, or an area the vault names an archive destination for: reconciles open actions, validates its records, moves it to `archive/`, and repoints links in both directions - references to it, and the relative links written inside it, which change depth on the move. |
| [`/para-pipeline`](base/.claude/skills/para-pipeline/SKILL.md) | The board for anything that moves through stages (deals, properties, applications): each one at its stage, its next dated step, what has stopped moving, and what the quarter did. Reads the stages a vault declares for them in its `CLAUDE.md` ([the format](base/.claude/skills/para-shared/lifecycles.md)); a vault that declares none needs nothing here. |
| [`/para-upgrade`](base/.claude/skills/para-upgrade/SKILL.md) | Migrates a vault to a newer template revision: reads the marker in its `CLAUDE.md`, applies the intervening [`CHANGELOG.md`](CHANGELOG.md) entries, and re-stamps it. Run before a deep clean, which otherwise audits against a stale contract. |

Beyond base:

- The [real-estate](addons/real-estate/) add-on adds [`/property-reconcile`](addons/real-estate/.claude/skills/property-reconcile/SKILL.md) (checks a property dossier against its sources), [`/property-underwrite`](addons/real-estate/.claude/skills/property-underwrite/SKILL.md) (brings it to decision-ready) and [`/property-dealsheet`](addons/real-estate/.claude/skills/property-dealsheet/SKILL.md) (renders the deal sheet).
- The [activity](addons/activity/) module adds [`/para-activity-review`](addons/activity/.claude/skills/para-activity-review/SKILL.md), which reads the vault's usage ledger and reports which skills nobody invokes, where sessions stall and which conventions people work around, each finding naming a change.
- The [brainstorm](addons/brainstorm/) module adds [`/para-brainstorm`](addons/brainstorm/.claude/skills/para-brainstorm/SKILL.md), which takes you from what keeps costing you time to two or three ideas worth testing, your own ideas before the agent's, and creates only the ones you approve.
- [`multi-vault/`](multi-vault/) adds [`/para-ingest`](multi-vault/para-ingest/SKILL.md), which reads shared sources once and stages each item in the vault it belongs to.

**Your own skills.** A vault can grow skills of its own, and three rules keep them supportable. A request starts as a prompt in `resources/prompts/` and becomes a skill after its third use, the same wait-until-proven rule the vault applies to templates. It is built with Anthropic's `skill-creator` skill, so it stays well-formed. And it never takes the `para-` prefix, which belongs to para-os: `/para-upgrade` treats a skill with a name para-os ships as its own copy and replaces it.

`/para-daily-brief` against the example vault (fragment):

````
# Daily Brief - 2026-06-24 - BelFoot

## 📊 Vault state
```
[P] cashless-stadium-rollout       ██████████  9 open
[A] stadium                        ████████░░  7 open ·         1 undated
[A] network (4 files)              ███████░░░  6 open · 2 🔴
[P] ticketing-platform-replacement ████░░░░░░  4 open
```
**Totals:** 26 open · 2 🔴 overdue · 25 dated · 4% undated

## 🎯 Now (5 of 26)
1. 🔺 Get Jan's decision on the three Q3 cost-recovery options - [network/jan-claes:26] · 📅 2026-06-22 (2d ago)
2. 🔼 Pre-brief Pieter on the Q3 cost issues before the walk-through - [network/pieter-de-ryck:19] · 📅 2026-06-23 (1d ago)
3. 🔺 Finalise the RFP evaluation matrix with Thomas Vermeulen - [ticketing-platform-replacement:7] · 📅 2026-06-26
**Later:** 3 this week · 6 next 30 days · 5 later · 5 recurring · 1 waiting · 1 undated

---
**Next action:** Open Jan's May 29 cost-recovery mail and pick the option you would defend - [network/jan-claes:26]
````

If no calendar connector is wired in, a root `meetings.md` (one line per meeting: `- 🗓 2026-06-12 14:00 · Title`) feeds the agenda.

## Reaching beyond your files

A vault the agent can only read is a tidy filing cabinet. Wire in a source and the *same* assistant folds it into the answer: `/para-daily-brief` shows your real meetings, attachments get filed straight from mail, action lists reconcile against live tickets. Your mailbox alone is your richest untapped record - years of customers, suppliers, decisions, orders, and attachments - and the assistant mines structure out of it rather than keyword-searching it. There are three ways to wire a source in, by how much lives in the vault:

- **Connectors** - authorized once in your agent (Gmail, Calendar, Drive, Slack). Nothing lands in the vault; every vault benefits automatically. The skills find a connector by its tool name wherever it is wired in, but pre-approve only the names they were written against: Claude's own Gmail connector (`mcp__claude_ai_Gmail__*`) and a Google Workspace server named `google-workspace`. A connector under another name works the same, and asks permission for each call.
- **MCP servers** - wiring as a config declaration, scopeable to one vault or shared globally, for a source with no built-in connector (a self-hosted Google Workspace server, Jira, Azure DevOps).
- **Integrations** - wiring as code: a small script in `resources/scripts/` that pulls a source into the vault as Markdown the assistant reads like everything else. This is the only tier para-os ships: [`integrations/`](integrations/README.md) packages them as drop-in folders (e.g. [`granola/`](integrations/granola/) syncs your Granola meeting notes into `triage/`).

## Add-ons

The base assumes you read and write the Markdown yourself. An add-on layers on it, as one of [three kinds](addons/README.md): a **delivery** changes how a vault is read, a **flavor** what it is about, a **module** adds a function beside that. [`readonly-ipad/`](addons/readonly-ipad/) is a delivery: you maintain the vault, a non-technical reader consumes generated PDFs on an iPad through Google Drive, and next steps live as prose instead of `actions.md`. [`real-estate/`](addons/real-estate/) is a flavor for buying, renovating, selling and holding property; [`sales/`](addons/sales/) is a module for prospects, demos and deals. A vault declares its add-ons under the `**Type:**` line of its `CLAUDE.md`.

## Data and privacy

A vault is just files on storage you already control - a local disk, a company cloud drive, or a git repo. para-os adds no server or database of its own and never copies your vault anywhere. Content leaves your storage only when the agent reads part of a file to answer a request: the same exposure as sending an email through a cloud provider, and per-request, not a standing copy.

For GDPR or data-sovereignty needs there's a ladder: a provider plan whose commercial terms exclude training and minimise retention (for a business, a Team or Enterprise plan rather than a personal one; on a personal Pro or Max plan, turn off the setting that lets your chats be used to improve the models); regional processing; or the model running inside a cloud tenant you control, for a hard "data must not leave our cloud" requirement. Because the root `CLAUDE.md` is read every session, it is also where you encode data-handling rules - what to redact, retention expectations, who the data subjects are - so the agent follows them by construction.

## Why this exists

Notion and Obsidian never stuck for me: keeping the structure current cost more than it gave back. The agent absorbs exactly that overhead, so the structure finally pays for itself. I now run a business, client engagements, and family admin this way; wired into my bookkeeping, a vault answers questions I used to take to my accountant. The thesis underneath, for technical readers: **clean file structures are the substrate for AI.** Point an agent at `Documents/Misc` and search is all it can do; give it a predictable layout with documented conventions and it files, cross-references, audits, and briefs you reliably.

## What's in the repo

- [`base/`](base/) - the vault skeleton you copy: PARA folders, placeholder READMEs, templates, the bootstrap prompt, the skills and rule files under `.claude/`, and agent and editor settings.
- [`INSTALL.md`](INSTALL.md) - the setup steps the Quickstart prompt runs.
- [`RELEASES.md`](RELEASES.md) - what each `YYYY.MM.NN` revision changes for you, in plain words, and whether you need to do anything.
- [`CHANGELOG.md`](CHANGELOG.md) - the same revisions as step-by-step instructions `/para-upgrade` applies to a vault.
- [`addons/`](addons/README.md) - the delivery, flavor and module add-ons.
- [`integrations/`](integrations/README.md) - drop-in scripts that pull an outside system into a vault.
- [`multi-vault/`](multi-vault/) - optional layer for several vaults drawing on the same inboxes.
- [`examples/`](examples/README.md) - fictional, fully populated vaults to poke at.
- For contributors: [`tools/check.py`](tools/check.py), the contract checks every revision passes, and [`evals/`](evals/README.md), the skill evals.

## Requirements

Beyond the list at the top:

- **Claude Code in a terminal** works the same as the desktop app: start it in the empty folder and paste the same line. Linux has no desktop app, so this is the route there.
- **Python 3 is optional** and does not come with Claude Code: install it from [python.org](https://www.python.org/downloads/) if you want it. It lets `/para-daily-brief`, `/para-pipeline`, `/para-deep-clean`, `/para-archive`, `/para-triage`, `/para-upgrade` and `/para-activity-review` hand their mechanical half to a script beside the skill; without it they fall back to a slower by-hand procedure and say so. On Windows use `py -3`, since a bare `python` is often a Microsoft Store stub. `/para-upgrade` also needs a local clone of this repository.
- **Account skills come along:** Claude Code syncs the skills and plugins enabled on your claude.ai account into sessions (the document skills are what a vault needs for the files it receives); `syncClaudeAiSkills: false` and `syncClaudeAiPlugins: false` in your settings keep a vault to its own.
- **Real, readable files.** On a synced drive (OneDrive/iCloud/Drive), set the vault to *always keep on this device* so on-demand sync doesn't hand the agent a placeholder stub instead of the file. Keep files in open formats (Markdown, PDF, CSV, readable Office files); convert cloud-native stubs (Google Docs/Sheets) and closed proprietary formats first.
- **A substrate that can undo.** Keep the vault in a git repo or on a drive with version history (OneDrive, Google Drive, Dropbox all qualify). The skills edit many files in one pass, and version history is the only thing that makes a bad pass reversible. What the agent may change on its own, and what enforces it, is in [the autonomy tiers](docs/autonomy-tiers.md).
- **Add-ons and integrations bring their own:** the read-only delivery needs Windows PowerShell and Node.js 18+ ([setup](addons/readonly-ipad/README.md)), and each integration's runtime and platform are in the [integrations table](integrations/README.md#available).

## Running several vaults

Each vault carries its own copy of the skills, which works but means one copy per vault. To keep a single source, move the skills to `~/.claude/skills/` (Claude Code loads them there for every vault, and `/para-upgrade` checks that install too) and delete the per-vault `.claude/skills/`. Keep one or the other: a skill in `~/.claude/skills/` wins over a vault's own copy of the same name, so a vault that keeps both runs the global one, however old it is.

If those vaults also draw on the same inboxes, see [`multi-vault/`](multi-vault/).

## License

[MIT](LICENSE). Copy it, adapt it, build your own.
