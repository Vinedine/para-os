# How it works

Point a capable assistant at a shapeless folder and you get a clever helper rummaging through a messy cabinet: it can search, at best. **para-os is the cabinet.** You bring your files and connect your sources (your inbox and its archive, calendar, meeting recordings, accounting); the assistant reads across *all of it at once*, cross-referenced into one answer instead of leaving you to check each silo by hand.

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

**Running a business.** A scanned letter from the tax office lands in the inbox. You ask the assistant to process it: it reads the letter, files it under a proper name, and adds "respond before 1 July" to the to-do list. With your mail connected, it cross-references what it finds ("the accountant requested a postponement on 12 May") - and then does the next bit too: drafts the reply [for you to paste and send](../base/.claude/skills/para-shared/drafting.md), and when the figures it needs are buried in a spreadsheet it can't parse cleanly, it writes a throwaway script on the spot to pull them. Next morning, your daily brief is one page of everything due, plus today's meetings.

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

## Reaching beyond your files

A vault the agent can only read is a tidy filing cabinet. Wire in a source and the *same* assistant folds it into the answer: `/para-daily-brief` shows your real meetings, attachments get filed straight from mail, action lists reconcile against live tickets. Your mailbox alone is your richest untapped record - years of customers, suppliers, decisions, orders, and attachments - and the assistant mines structure out of it rather than keyword-searching it. There are three ways to wire a source in, by how much lives in the vault:

- **Connectors** - authorized once in your agent (Gmail, Calendar, Drive, Slack). Nothing lands in the vault; every vault benefits automatically. The skills find a connector by its tool name wherever it is wired in, but pre-approve only the names they were written against: Claude's own Gmail connector (`mcp__claude_ai_Gmail__*`) and a Google Workspace server named `google-workspace`. A connector under another name works the same, and asks permission for each call.
- **MCP servers** - wiring as a config declaration, scopeable to one vault or shared globally, for a source with no built-in connector (a self-hosted Google Workspace server, Jira, Azure DevOps).
- **Integrations** - wiring as code: a small script in `resources/scripts/` that pulls a source into the vault as Markdown the assistant reads like everything else. This is the only tier para-os ships: [`integrations/`](../integrations/README.md) packages them as drop-in folders (e.g. [`granola/`](../integrations/granola/) syncs your Granola meeting notes into `triage/`).
