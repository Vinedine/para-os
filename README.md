# para-os

**Run your work out of one structured place, with an AI assistant on top.**

The hard part of AI assistance isn't the assistant. It's that everything it needs is scattered across drives, inboxes, and people's heads. Point a capable assistant at a shapeless folder and you get a clever helper rummaging through a messy cabinet: it can search, at best.

**para-os is the cabinet.** A free, do-it-yourself kit for anyone whose information is scattered: a practice, a business you run, a project, a household. You bring your files and connect your systems (mail, calendar, accounting); para-os gives them one structured home and an AI assistant that reads across *all of it at once* - your files plus every connected system, cross-referenced into one answer instead of leaving you to check each silo by hand. So the questions that used to mean an afternoon of digging just get answered:

- "What's the full history with this client, across email and our files?"
- "What did we agree with the bank in March, and where's the document?"
- "Pull every order this supplier sent and flag what's still open."

Your mailbox alone is your richest untapped record - years of customers, suppliers, decisions, orders, and attachments - and the assistant mines structure out of it rather than keyword-searching it. Your files stay ordinary files (PDFs, scans, spreadsheets) in ordinary folders on your own computer. The assistant does the part that never sticks: it files what comes in, drafts what goes out, writes the small tool it needs when it gets stuck, and answers across everything you keep.

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

> **Want it set up for you?** The kit is free. If you'd rather have your business structured and the assistant wired in for you, that's the **AI Workspace** service I offer - [get in touch](https://trotstar.tech).

## What it is

A folder you copy, not a program you install. Inside: a ready-made set of folders with one obvious place for everything, house rules in plain language that tell the assistant how to behave, and a handful of routines for the recurring chores (process the inbox, brief me each morning, tidy up, archive what's done). The folders follow [PARA](https://fortelabs.com/blog/para/), the filing method, hence the name.

Everything stays plain files and Markdown on your own disk. No app, no database, no lock-in - run it with one AI assistant today and a different one tomorrow, and the data outlives them all.

## What it looks like in practice

**Running a business.** A scanned letter from the tax office lands in the inbox. You ask the assistant to process it: it reads the letter, files it under a proper name, and adds "respond before 1 July" to the to-do list. With your mail connected, it cross-references what it finds ("the accountant requested a postponement on 12 May") - and then does the next bit too: drafts the reply for you to send, and when the figures it needs aren't in the letter but buried in a spreadsheet it can't parse cleanly, it writes a throwaway script on the spot to pull them. Next morning, your daily brief is one page of everything due, plus today's meetings. The point isn't that it *finds* things; it's that it produces finished work across everything you keep.

```text
 messy input  ──▶  reads every source  ──▶  writes its own tool  ──▶  finished output
  (a letter,        (mail + drive +          (hits a wall, scripts      (a drafted reply
   a request)        accounting, joined)      its way past it)           you can send)
```

**IT projects.** Connect Jira, Azure DevOps, and your mail (MCP). The morning brief checks your to-do list against the live sprint board; a steering transcript you drop in the inbox gets filed and its decisions linked to the tickets they affect. "What's still blocking the release?" is answered from the board plus your own files.

**At home.** School letters, insurance renewals, the contractor's quote: same folders, same routines. One list of what needs an answer, and it remembers what the insurer wrote last year.

## Three layers, and para-os owns the bottom one

Any "AI on top of my stuff" setup is three layers stacked. Naming them shows where para-os sits, and why it isn't competing with the tools it gets compared to:

1. **Substrate (your files)** - the files and how they're organised. **This is para-os.**
2. **Agent (the assistant)** - the model that reads and writes them: Claude Code, Cursor, Codex, Claude Cowork.
3. **Interface (how you work with it)** - how you drive it: an editor, a notes app, a chat app, PDFs on an iPad.

para-os owns layer 1 and is agnostic about 2 and 3 - **bring your own agent**. Almost nobody does the layer-1 work because it feels like filing, not engineering. That's exactly why it pays off: an agent is only as good as the files you point it at, and that leverage grows as agents get better. The files are the memory - the folder on disk is the durable state, the agent reads it fresh each session, and the git diff is the audit log. No memory features, no chat-history dependence.

Because it reasons over real files rather than a black box, the setup stays **agentic**: you hold the goals, the assistant does the work and surfaces its uncertainty - when something is ambiguous or it can't do a step reliably, it says so and asks, rather than confidently handing you the wrong thing. You stay the operator; the structure amplifies you.

## You don't need to be a programmer

You work in two free-to-install tools: [VS Code](https://code.visualstudio.com/), an editor, and [Claude Code](https://claude.com/claude-code), Anthropic's AI assistant (the AI itself needs a paid Claude plan). Both were built for software work, but here they're just a window onto your folders with a chat box beside it. You type plain English; the assistant handles the files. Those files are **Markdown** (the `.md` ending): plain text with a few simple marks, readable on any device. If you can use email and a file explorer, you can run this.

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
└── archive/       # anything inactive; dated records in archive/meetings/
```

`triage/` is para-os's addition to stock PARA: a capture inbox for anything you can't file in ten seconds. Capture stays frictionless because filing is delegated to the agent.

The conventions the templates encode:

- **`CLAUDE.md` is the contract.** Each vault documents its own rules - what a "project" means here, the naming convention, an explicit "do not add" list. The skills read it at runtime; nothing is hardcoded.
- **One source of truth.** The root `README.md` is the master document; decks, web copy, and summaries regenerate from it.
- **Ideas are not projects.** A concept stays in `resources/ideas/` until someone's waiting on a deliverable or money is committed, then it promotes to `projects/`.
- **Actions live with their context.** Tasks sit in the project, idea, or contact file they belong to, as markdown checkboxes with [Obsidian Tasks](https://publish.obsidian.md/tasks/) emoji markers (`📅` due, `🛫` start, `🔁` recurring, `🔺🔼🔽⏬` priority). Regex-parseable; Obsidian itself optional.
- **Scripts live in the vault, their secrets don't.** A persistent tool the agent writes goes in `resources/scripts/`; its credentials, caches, and bulk data live outside the vault under `~/.paraos/` (resolved via `PARAOS_HOME`), so nothing sensitive syncs to a cloud drive or git remote and no large file bloats the vault.

## Quickstart

1. **Copy [`base/skeleton/`](base/skeleton/)** to become the root of your new vault - a folder in your cloud drive, a git repo, anywhere. The skills come bundled inside it (`.claude/skills/`), so this one copy gives you a working vault:
   ```
   cp -r base/skeleton ~/my-vault                # macOS / Linux / Git Bash
   Copy-Item base/skeleton ~/my-vault -Recurse   # Windows PowerShell
   ```
2. **Run the bootstrap.** Open a Claude Code session **in the new vault root** and paste the prompt from `bootstrap-prompt.md`. It asks three short questions, fills the `CLAUDE.md` and `README.md` templates, and creates a self-retiring `vault-setup` project that walks you through the rest.
3. **Run `/para-daily-brief`.** The vault answers from day one - and richer as you feed it your braindump.

> **Running several vaults?** The bundled copy just works, but you'll then carry one skills copy per vault. If you'd rather maintain a single source, move the skills to `~/.claude/skills/` (Claude Code loads them there for every vault) and delete the per-vault `.claude/skills/`. One-vault users can ignore this.

To see a lived-in vault first, open [`examples/belfoot-vault/`](examples/belfoot-vault/): a fictional consulting engagement with projects, contacts, actions, and meeting records. Run `/para-daily-brief` or `/para-triage` in its root to watch the skills work.

## The skills

| Skill | What it does |
|---|---|
| [`/para-triage`](base/skills/para-triage/SKILL.md) | Empties `triage/`: identifies each loose file, proposes a destination and a convention-conform rename, executes after your approval. |
| [`/para-daily-brief`](base/skills/para-daily-brief/SKILL.md) | One-pass dashboard of every open task, bucketed by urgency against today, plus a meetings agenda and a triage count. |
| [`/para-deep-clean`](base/skills/para-deep-clean/SKILL.md) | Periodic maintenance: structural audit, README normalisation, closing documented open items by reading the source files. |
| [`/para-archive`](base/skills/para-archive/SKILL.md) | Closes out one finished project or shelved idea: reconciles open actions, validates its records, moves it to `archive/`, and repoints every inbound link. |

They all read the vault's own `CLAUDE.md` for conventions; no paths are hardcoded. `/para-daily-brief` against the example vault (fragment):

```
# Daily Brief - 2026-06-24

## 🔴 Overdue (2)
- 🔺 Get Jan's decision on the three Q3 cost-recovery options - [network/jan-claes:26] · 📅 2026-06-22 (2d ago)
- 🔼 Pre-brief Pieter on the Q3 cost issues before the walk-through - [network/pieter-de-ryck:19] · 📅 2026-06-23 (1d ago)

## 🟡 This week (4)
- 🔺 Finalise the RFP evaluation matrix with Thomas Vermeulen - [ticketing-platform-replacement:7] · 📅 2026-06-26
```

If no calendar connector is wired in, a root `meetings.md` (one line per meeting: `- 🗓 2026-06-12 14:00 · Title`) feeds the agenda.

## Reaching beyond your files

A vault the agent can only read is a tidy filing cabinet. Wire in a source and the *same* assistant can see it and fold it into the answer - so reach compounds: `/para-daily-brief` shows your real meetings, attachments get filed straight from mail, action lists reconcile against live tickets, a question gets answered from your files *and* every system at once. There are three ways to wire one in, by how much lives in the vault:

- **Connectors** - authorized once in your agent (Gmail, Calendar, Drive, Slack). Nothing lands in the vault; every vault benefits automatically.
- **MCP servers** - wiring as a config declaration, scopeable to one vault or shared globally, for a source with no built-in connector (a self-hosted Google Workspace server, Jira, Azure DevOps). A connector is really just a pre-authorized remote MCP server - the line between the two is *authorized-in-the-agent* vs *declared-in-config*, not different plumbing.
- **Integrations** - wiring as code: a small script that pulls a source into the vault as Markdown. This is the only tier para-os ships (see below); the other two live in the agent, and the vault stays plain files.

## Integrations

Integrations are the scriptable tier: a small script drops into a vault's `resources/scripts/` and pulls a source in as Markdown the assistant reads like everything else. [`integrations/`](integrations/) packages them as drop-in folders - [`granola/`](integrations/granola/) syncs your Granola meeting notes and transcripts into `triage/`. Secrets and caches stay outside the vault under `~/.paraos/`; the [folder's README](integrations/) has the full contract.

## The read-only flavor

The base assumes you read and write the markdown yourself. [`flavors/readonly-ipad/`](flavors/readonly-ipad/) packages a second model: you maintain the vault, a non-technical reader consumes generated PDFs on an iPad through Google Drive. A Puppeteer pipeline produces PDF siblings, a flip script keeps the markdown out of the reader's view, and `actions.md` is dropped (next steps live as prose). Setup is in the flavor's README.

## Why this exists

Notion and Obsidian never stuck for me: keeping the structure current cost more than it gave back. The agent absorbs exactly that overhead - so the structure finally pays for itself. I now run a business, client engagements, and family admin this way; wired into my bookkeeping, a vault answers questions I used to pay an accountant for. The thesis underneath, for technical readers: **clean file structures are the substrate for AI.** Give an agent `Documents/Misc` and it can search, at best; give it a predictable layout with documented conventions and it files, cross-references, audits, and briefs you reliably.

## What's in the repo

- [`base/skeleton/`](base/skeleton/) - the vault skeleton: PARA folders, placeholder READMEs, templates, bootstrap prompt, the bundled skills (`.claude/skills/`), and editor settings (`.vscode/settings.json`) that open `.md` files in clean rendered preview.
- [`base/skills/`](base/skills/) - the skills, kept here as the canonical source. They ship inside the skeleton by default; copy them to `~/.claude/skills/` if you run several vaults and want a single source.
- [`flavors/readonly-ipad/`](flavors/readonly-ipad/) - the render pipeline for the read-only model.
- [`integrations/`](integrations/) - drop-in connectors that pull an outside system into a vault (e.g. `granola/` for meeting sync).
- [`examples/belfoot-vault/`](examples/belfoot-vault/) - a fictional, fully populated vault to poke at.

## Requirements

- [Claude Code](https://claude.com/claude-code), or adapt the skills to your agent of choice; they're plain markdown instructions.
- The core (skeleton + skills) needs nothing else. Scripts here (the read-only flavor, integrations) that need a runtime assume **[Node.js](https://nodejs.org/) 18+** (for the built-in `fetch`).
- Read-only flavor only: Windows PowerShell and `npm install -g puppeteer marked github-markdown-css`.
- Some integrations add their own prerequisites (an app, an account, a platform); each states them in its README.

## License

[MIT](LICENSE). Copy it, adapt it, build your own.
