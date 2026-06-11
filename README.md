# para-os

Plain folders, markdown, and an AI agent that operates them. para-os ships a [PARA](https://fortelabs.com/blog/para/) folder skeleton, the conventions that make it agent-operable, and three Claude Code skills that work in any vault built this way. The agent files what comes in, drafts what goes out, tracks what's due, and answers questions across everything you keep.

The thesis: **clean file structures are the substrate for AI.** An agent is only as good as the files you point it at. Give it `Documents/Misc` and it can search, at best. Give it a predictable layout with documented conventions and every "where does this go?" has one answer, so it can file, cross-reference, audit, and brief you reliably.

## Why this exists

I ran my working life out of one paper notebook per year, for years. The digital replacements never stuck: Notion and Obsidian both turned into admin overhead pulling me away from the real work, and chat-based AI workspaces came close but broke down past small topics. The failure mode was always the same: keeping the structure current cost more than the structure gave back.

Early 2026, three things clicked together: PARA for the structure, VS Code as the workbench, Claude Code as the agent. The agent absorbs exactly the overhead that killed every earlier attempt. I drop a call transcript or a scanned letter into `triage/` and it gets identified, renamed, filed, cross-linked, and the right action list updated. The structure finally pays back more than it costs. I now run client engagements, a business, family admin, and my finances this way, and maintain read-only vaults for non-technical people close to me. Wired into my bookkeeping system, a vault answers questions I used to pay an accountant for.

Three things worth noticing:

- **"Second brain" undersells it.** This is not a static knowledge store; it's closer to a personal assistant that keeps a tidy filing cabinet behind it.
- **Developer tools, almost no code.** VS Code and Claude Code were built for software work, but they are excellent general knowledge-work tools once you point them at the right folders.
- **The files are the memory.** No memory features, no chat-history dependence. The vault on disk is the durable state, the agent reads it fresh every session, and the git diff is the audit log. Durable, inspectable, portable, yours.

## The vault

A vault is one folder tree per life context: a client engagement, a business you run, family admin, financial records. Keep contexts in separate vaults; the agent stays focused and nothing leaks across boundaries.

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

No app, no database, no sync service. Plain folders and markdown are the lowest common denominator every agent, editor, and future tool can read; the data outlives all of them.

## Quickstart

1. **Copy [`base/skeleton/`](base/skeleton/)** as the root of your new vault: a folder in your cloud drive, a git repo, anywhere.
2. **Run the bootstrap.** Open a Claude Code session in the vault root and paste the prompt from `bootstrap-prompt.md`. It interviews you, fills the `CLAUDE.md` and `README.md` templates, seeds a starter `actions.md`, and cleans up after itself.
3. **Install the skills.** Copy the folders under [`base/skills/`](base/skills/) into `~/.claude/skills/`, then run `/daily-brief`.

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

The connectors live in the agent, not in para-os. The vault stays plain files, portable and tool-agnostic.

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
