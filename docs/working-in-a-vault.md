# Working in a vault

For anyone who works in a vault someone else set up. Print it and keep it beside you.

## One session per job

- **Start a new session for each job, and close it the same day.** The vault's files are its memory, not the chat: a new session starts from what is filed now, including what the others changed.
- **Name what it is about in your first sentence**: "For the <name> project, ..." or "About <person>, ...". The assistant then opens the right files first.

## Finding and adding documents

- **Filed documents live with what they are about**, in that project's or area's `sources/` folder (for example `projects/<name>/sources/`), under a name the vault's own rule gives them.
- **To find one, ask**: "Where is the signed contract for <name>?" The assistant tells you where it is filed; open it there. Don't ask for a copy in your own folders: it falls out of date, and nobody else sees it.
- **New documents go into `triage/` first.** Save or drag the file (a PDF, a scan, a saved email) into the vault's `triage/` folder, then type `/para-triage`. It reads each file, proposes where it goes and what to call it, and moves nothing until you agree.
- **Don't attach a file from elsewhere** on your computer: the assistant may not be able to open a file outside the vault, and nothing outside it gets filed.

## Four commands

Type one at the start of a message, or ask in your own words ("what is overdue?").

- `/para-daily-brief`: what is due and where things stand. Add a project's or area's name for that one alone.
- `/para-triage`: files what is waiting in `triage/`.
- `/para-new`: starts a project, area, idea or contact in the right place.
- `/para-prep`: prepares a meeting: who is coming, what is open, what to ask. Add a person's name, or `today`.

## Drafts

- **Give an example**: a message you liked, or the earlier one to follow. It works better than a description.
- **Check before you send.** The assistant writes the draft and never sends it. Read every name, date and figure; anything the vault does not hold is marked, like `[date: not in the vault]`.

## Keep the vault for the work

- **Ask private questions elsewhere**, in a chat not opened on the vault folder. What a vault session settles can be written into files the others read.
- **Never ask for or paste a password, code or key.** Sign-ins to mailboxes and other services are set up outside the chat; the assistant never needs yours.
