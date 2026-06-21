# para-os

**Run your work out of one structured place, with an AI assistant on top.**

para-os is a free kit for anyone whose information is scattered across drives, inboxes, and people's heads: a practice, a business you run, a project, a household. You bring your files and connect your systems (mail, calendar, accounting). para-os gives them one structured home and an AI assistant that reads across all of it, so the questions that used to mean digging just get answered:

- "What's still open with this client?"
- "What did we agree with the bank in March?"
- "Where did that contract end up?"

Your files stay ordinary files (PDFs, scans, spreadsheets) in ordinary folders on your own computer. The assistant does the part that never sticks: it files what comes in, drafts what goes out, tracks what's due, and answers across everything you keep.

> **Want it set up for you?** The kit is free and do-it-yourself. If you'd rather have your business structured and the assistant wired in for you, that's a service I offer - [get in touch](https://trotstar.tech).

## What it is

A folder you copy, not a program you install. Inside: a ready-made set of folders with one obvious place for everything, house rules in plain language that tell the assistant how to behave, and three routines for the recurring chores (process the inbox, brief me each morning, tidy up). The folders follow [PARA](https://fortelabs.com/blog/para/), the filing method, hence the name.

Everything stays plain files and Markdown on your own disk. No app, no database, no sync service, nothing locked inside one program. That keeps it portable: run it with one AI assistant today and a different one tomorrow, and the data outlives them all.

## What it looks like in practice

**Running a business.** A scanned letter from the tax office lands in the inbox. You ask the assistant to process it: it reads the letter, files it in the right dossier under a proper name, and adds "respond before 1 July" to the to-do list. With your mail connected, it checks whether you've corresponded before and notes what it finds ("the accountant requested a postponement on 12 May"). Next morning you ask for your daily brief: one page with everything due or overdue, plus today's meetings.

**IT projects.** Connect Jira, Azure DevOps, and your mail through the standard connectors (MCP). The morning brief now checks your to-do list against the live sprint board. A steering-meeting transcript you drop in the inbox gets filed, its decisions linked to the tickets they affect. "What's still blocking the release?" is answered from the board plus everything in your own files.

**At home.** School letters, insurance renewals, the contractor's quote: same folders, same routines. One list of what needs an answer, and it remembers what the insurer wrote last year, so you don't have to.

## You don't need to be a programmer

You work in two free-to-install tools: [VS Code](https://code.visualstudio.com/), an editor, and [Claude Code](https://claude.com/claude-code), Anthropic's AI assistant (the AI itself needs a paid Claude plan). Both were built for software work, but here they are just a window onto your folders with a chat box beside it. You type plain English; the assistant handles the files. Those files are **Markdown** (the `.md` ending): plain text with a few simple marks, like `#` for a heading and `-` for a list, readable on any device. If you can use email and a file explorer, you can run this.

## Why not Claude Cowork?

[Claude Cowork](https://www.anthropic.com/product/claude-cowork) is Anthropic's same idea in app form: an AI assistant pointed at a folder. What it doesn't ship is the part para-os exists for: a sensible folder structure, written house rules the assistant re-reads every session, and routines to keep it consistent over months. Point an assistant at a shapeless folder and you get a clever helper in a messy cabinet. para-os is the cabinet.

## Why this exists

I ran my working life out of one paper notebook per year, for years. The digital replacements never stuck: Notion and Obsidian turned into admin overhead that pulled me off the real work, and chat-based AI workspaces came close but broke down past small topics. The failure mode was always the same: keeping the structure current cost more than it gave back.

In early 2026, three things clicked together: PARA for the folder structure, VS Code as the workbench, Claude Code as the assistant. The agent absorbs exactly the overhead that killed every earlier attempt, so the structure finally pays back more than it costs. I now run a business, client engagements, and family admin this way; wired into my bookkeeping, a vault answers questions I used to pay an accountant for.

For technical readers, the thesis underneath: **clean file structures are the substrate for AI.** An agent is only as good as the files you point it at. Give it `Documents/Misc` and it can search, at best. Give it a predictable layout with documented conventions and every "where does this go?" has one answer, so it files, cross-references, audits, and briefs you reliably. And the files are the memory: no memory features, no chat-history dependence. The folder on disk is the durable state, the agent reads it fresh every session, and the git diff is the audit log. Durable, inspectable, portable, yours.

## The vault

A vault is one folder tree per life context: a client engagement, a business you run, family admin, financial records. Keep contexts in separate vaults so the agent stays focused and nothing leaks across boundaries.

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

- **`CLAUDE.md` is the contract.** Each vault documents its own rules: what a "project" means here, the file naming convention, language policy, an explicit "do not add" list. The skills read it at runtime; nothing is hardcoded. A new agent session, or a new human, orients from one file.
- **One source of truth.** The root `README.md` is the master document; decks, web copy, and summaries regenerate from it and are never edited as separate sources.
- **Ideas are not projects.** A concept stays in `resources/ideas/` until someone is waiting on a deliverable or money is committed. Then it promotes to `projects/`, same folder shape.
- **Actions live with their context.** Tasks sit in the project, idea, or contact file they belong to, as markdown checkboxes with [Obsidian Tasks](https://publish.obsidian.md/tasks/) emoji markers (`📅` due, `🛫` start, `🔁` recurring, `🔺🔼🔽⏬` priority). Trivially regex-parseable; Obsidian itself optional. `/daily-brief` reassembles the global view at read time.
- **Don't template prematurely.** Wait until a second instance proves a shape, then document it in `CLAUDE.md`.

## Quickstart

1. **Copy [`base/skeleton/`](base/skeleton/)** as the root of your new vault: a folder in your cloud drive, a git repo, anywhere.
2. **Run the bootstrap.** Open a Claude Code session in the vault root and paste the prompt from `bootstrap-prompt.md`. It asks three short questions, fills the `CLAUDE.md` and `README.md` templates, seeds a starter `actions.md`, and creates a self-retiring `vault-setup` project that walks you through the rest of onboarding (a braindump, then connecting your systems) before cleaning up after itself.
3. **Install the skills.** The three routines are agent tooling shared across *all* your vaults, so they install once, globally: copy the folders under [`base/skills/`](base/skills/) into `~/.claude/skills/`, then run `/daily-brief`. (Prefer to keep them with a single vault? Drop them in `<vault>/.claude/skills/` instead.)

To see a lived-in vault first, open [`examples/belfoot-vault/`](examples/belfoot-vault/): a fictional consulting engagement with projects, contacts, actions, and meeting records. Run `/daily-brief` or `/triage` in its root to watch the skills work.

## The skills

| Skill | What it does |
|---|---|
| [`/triage`](base/skills/triage/SKILL.md) | Empties `triage/`: identifies each loose file, proposes a destination and a convention-conform rename, executes after your approval, updates the receiving READMEs. |
| [`/daily-brief`](base/skills/daily-brief/SKILL.md) | One-pass dashboard of every open task in the vault, bucketed by urgency against today, plus a meetings agenda and a triage count. |
| [`/deep-clean`](base/skills/deep-clean/SKILL.md) | Periodic multi-phase maintenance: structural audit, README normalisation, closing documented open items by actually reading the source PDFs. |

All three read the vault's own `CLAUDE.md` for conventions; no paths are hardcoded. `/daily-brief` against the example vault (fragment, links abridged):

```
# Daily Brief - 2026-06-11

## 🔴 Overdue (4)
- 🔺 Finalise the RFP evaluation matrix with Thomas Vermeulen - [ticketing-platform-replacement:7] · *This week* · 📅 2026-05-29 (13d ago)
- 🔼 Pre-brief Jan on the 4G fallback hardware delay - [network/jan-claes:27] · *Next actions* · 📅 2026-05-27 (15d ago)
- 🔼 Map dependencies between cashless rollout and ticketing replacement - [stadium:12] · *Open* · 📅 2026-06-10 (1d ago)

## 🟡 This week (2)
- Review open ADRs in the Structurizr workspace - [stadium:13] · *Open* · 📅 2026-06-15 (in 4d)
```

If no calendar connector is wired in, a root `meetings.md` (one line per meeting: `- 🗓 2026-06-12 14:00 · Title`) feeds the agenda.

## Connectors

A vault the agent can only read is a tidy filing cabinet. Wired into the systems your work actually lives in, it becomes an operator. MCP servers (Gmail, Calendar, Drive, Slack, Atlassian, Azure DevOps, ...) and anything scriptable (`az`, a REST API, your accounting tool) compose: `/daily-brief` shows your real meetings, attachments get filed straight from mail, action lists reconcile against live tickets, and "what's still outstanding on this client?" is answered from the live ledger instead of a stale export.

The connectors live in the agent, not in para-os; the vault stays plain files.

## The read-only flavor

The base assumes you read and write the markdown yourself. [`flavors/readonly-ipad/`](flavors/readonly-ipad/) packages a second consumption model: you maintain the vault, a non-technical reader consumes generated PDFs on an iPad through Google Drive. A Puppeteer render pipeline produces PDF siblings, a flip script keeps the markdown sources out of the reader's view, and `actions.md` is dropped (next steps live as prose). Setup and the edit cycle are in the flavor's README.

## What's in the repo

- [`base/skeleton/`](base/skeleton/) - the vault skeleton: PARA folders, placeholder READMEs, the three templates, the bootstrap prompt.
- [`base/skills/`](base/skills/) - the three skills, installable into `~/.claude/skills/`.
- [`flavors/readonly-ipad/`](flavors/readonly-ipad/) - the render pipeline and setup for the read-only consumption model.
- [`examples/belfoot-vault/`](examples/belfoot-vault/) - a fictional, fully populated vault to poke at.

## Requirements

- [Claude Code](https://claude.com/claude-code), or adapt the skills to your agent of choice; they are plain markdown instructions.
- Read-only flavor only: Windows PowerShell, Node.js, and `npm install -g puppeteer marked github-markdown-css`.

## License

[MIT](LICENSE). Copy it, adapt it, build your own.
