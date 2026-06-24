# para-os

**Run your work out of one structured place, with an AI assistant on top.**

The hard part of AI assistance isn't the assistant. It's that everything it needs is scattered across drives, inboxes, and people's heads. Point a capable assistant at a shapeless folder and you get a clever helper rummaging through a messy cabinet: it can search, at best.

**para-os is the cabinet.** A free, do-it-yourself kit for anyone whose information is scattered: a practice, a business you run, a project, a household. You bring your files and connect your systems (mail, calendar, accounting); para-os gives them one structured home and an AI assistant that reads across all of it, so the questions that used to mean digging just get answered:

- "What's still open with this client?"
- "What did we agree with the bank in March?"
- "Where did that contract end up?"

Your files stay ordinary files (PDFs, scans, spreadsheets) in ordinary folders on your own computer. The assistant does the part that never sticks: it files what comes in, drafts what goes out, tracks what's due, and answers across everything you keep.

> **Want it set up for you?** The kit is free. If you'd rather have your business structured and the assistant wired in for you, that's a service I offer - [get in touch](https://trotstar.tech).

## What it is

A folder you copy, not a program you install. Inside: a ready-made set of folders with one obvious place for everything, house rules in plain language that tell the assistant how to behave, and three routines for the recurring chores (process the inbox, brief me each morning, tidy up). The folders follow [PARA](https://fortelabs.com/blog/para/), the filing method, hence the name.

Everything stays plain files and Markdown on your own disk. No app, no database, no lock-in - run it with one AI assistant today and a different one tomorrow, and the data outlives them all.

## What it looks like in practice

**Running a business.** A scanned letter from the tax office lands in the inbox. You ask the assistant to process it: it reads the letter, files it under a proper name, and adds "respond before 1 July" to the to-do list. With your mail connected, it notes what it finds ("the accountant requested a postponement on 12 May"). Next morning, your daily brief is one page of everything due, plus today's meetings.

**IT projects.** Connect Jira, Azure DevOps, and your mail (MCP). The morning brief checks your to-do list against the live sprint board; a steering transcript you drop in the inbox gets filed and its decisions linked to the tickets they affect. "What's still blocking the release?" is answered from the board plus your own files.

**At home.** School letters, insurance renewals, the contractor's quote: same folders, same routines. One list of what needs an answer, and it remembers what the insurer wrote last year.

## Three layers, and para-os owns the bottom one

Any "AI on top of my stuff" setup is three layers stacked. Naming them shows where para-os sits, and why it isn't competing with the tools it gets compared to:

1. **Substrate** - the files and how they're organised. **This is para-os.**
2. **Agent** - the model that reads and writes them: Claude Code, Cursor, Codex, Claude Cowork.
3. **Interface** - how you drive it: an editor, a notes app, a chat app, PDFs on an iPad.

para-os owns layer 1 and is agnostic about 2 and 3 - **bring your own agent**. Almost nobody does the layer-1 work because it feels like filing, not engineering. That's exactly why it pays off: an agent is only as good as the files you point it at, and that leverage grows as agents get better. The files are the memory - the folder on disk is the durable state, the agent reads it fresh each session, and the git diff is the audit log. No memory features, no chat-history dependence.

## You don't need to be a programmer

You work in two free-to-install tools: [VS Code](https://code.visualstudio.com/), an editor, and [Claude Code](https://claude.com/claude-code), Anthropic's AI assistant (the AI itself needs a paid Claude plan). Both were built for software work, but here they're just a window onto your folders with a chat box beside it. You type plain English; the assistant handles the files. Those files are **Markdown** (the `.md` ending): plain text with a few simple marks, readable on any device. If you can use email and a file explorer, you can run this.

## The vault

A vault is one folder tree per life context: a client engagement, a business, family admin. Keep contexts in separate vaults so the agent stays focused and nothing leaks across boundaries.

```
your-vault/
├── CLAUDE.md      # the contract: local conventions, read by the agent at runtime
├── README.md      # master document; derived outputs regenerate from it
├── triage/        # capture inbox; /triage empties it
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

## Quickstart

1. **Install the skills once, up front.** The three routines are shared across *all* your vaults, so they live globally: copy the folders under [`base/skills/`](base/skills/) into `~/.claude/skills/`. (Prefer per-vault? Drop them in `<vault>/.claude/skills/`.)
2. **Copy [`base/skeleton/`](base/skeleton/)** to become the root of your new vault - a folder in your cloud drive, a git repo, anywhere:
   ```
   cp -r base/skeleton ~/my-vault                # macOS / Linux / Git Bash
   Copy-Item base/skeleton ~/my-vault -Recurse   # Windows PowerShell
   ```
3. **Run the bootstrap.** Open a Claude Code session **in the new vault root** and paste the prompt from `bootstrap-prompt.md`. It asks three short questions, fills the `CLAUDE.md` and `README.md` templates, and creates a self-retiring `vault-setup` project that walks you through the rest.
4. **Run `/daily-brief`.** The vault answers from day one - and richer as you feed it your braindump.

To see a lived-in vault first, open [`examples/belfoot-vault/`](examples/belfoot-vault/): a fictional consulting engagement with projects, contacts, actions, and meeting records. Run `/daily-brief` or `/triage` in its root to watch the skills work.

## The skills

| Skill | What it does |
|---|---|
| [`/triage`](base/skills/triage/SKILL.md) | Empties `triage/`: identifies each loose file, proposes a destination and a convention-conform rename, executes after your approval. |
| [`/daily-brief`](base/skills/daily-brief/SKILL.md) | One-pass dashboard of every open task, bucketed by urgency against today, plus a meetings agenda and a triage count. |
| [`/deep-clean`](base/skills/deep-clean/SKILL.md) | Periodic maintenance: structural audit, README normalisation, closing documented open items by reading the source files. |

All three read the vault's own `CLAUDE.md` for conventions; no paths are hardcoded. `/daily-brief` against the example vault (fragment):

```
# Daily Brief - 2026-06-24

## 🔴 Overdue (2)
- 🔺 Get Jan's decision on the three Q3 cost-recovery options - [network/jan-claes:26] · 📅 2026-06-22 (2d ago)
- 🔼 Pre-brief Pieter on the Q3 cost issues before the walk-through - [network/pieter-de-ryck:19] · 📅 2026-06-23 (1d ago)

## 🟡 This week (4)
- 🔺 Finalise the RFP evaluation matrix with Thomas Vermeulen - [ticketing-platform-replacement:7] · 📅 2026-06-26
```

If no calendar connector is wired in, a root `meetings.md` (one line per meeting: `- 🗓 2026-06-12 14:00 · Title`) feeds the agenda.

## Connectors

A vault the agent can only read is a tidy filing cabinet. Wired into the systems your work lives in, it becomes an operator. MCP servers (Gmail, Calendar, Drive, Slack, Atlassian, Azure DevOps, ...) and anything scriptable compose: `/daily-brief` shows your real meetings, attachments get filed straight from mail, action lists reconcile against live tickets. The connectors live in the agent, not in para-os; the vault stays plain files.

## The read-only flavor

The base assumes you read and write the markdown yourself. [`flavors/readonly-ipad/`](flavors/readonly-ipad/) packages a second model: you maintain the vault, a non-technical reader consumes generated PDFs on an iPad through Google Drive. A Puppeteer pipeline produces PDF siblings, a flip script keeps the markdown out of the reader's view, and `actions.md` is dropped (next steps live as prose). Setup is in the flavor's README.

## Why this exists

Notion and Obsidian never stuck for me: keeping the structure current cost more than it gave back. The agent absorbs exactly that overhead - so the structure finally pays for itself. I now run a business, client engagements, and family admin this way; wired into my bookkeeping, a vault answers questions I used to pay an accountant for. The thesis underneath, for technical readers: **clean file structures are the substrate for AI.** Give an agent `Documents/Misc` and it can search, at best; give it a predictable layout with documented conventions and it files, cross-references, audits, and briefs you reliably.

## What's in the repo

- [`base/skeleton/`](base/skeleton/) - the vault skeleton: PARA folders, placeholder READMEs, templates, bootstrap prompt.
- [`base/skills/`](base/skills/) - the three skills, installable into `~/.claude/skills/`.
- [`flavors/readonly-ipad/`](flavors/readonly-ipad/) - the render pipeline for the read-only model.
- [`examples/belfoot-vault/`](examples/belfoot-vault/) - a fictional, fully populated vault to poke at.

## Requirements

- [Claude Code](https://claude.com/claude-code), or adapt the skills to your agent of choice; they're plain markdown instructions.
- Read-only flavor only: Windows PowerShell, Node.js, and `npm install -g puppeteer marked github-markdown-css`.

## License

[MIT](LICENSE). Copy it, adapt it, build your own.
