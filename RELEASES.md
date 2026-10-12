# Release notes

What each para-os revision changes for you, in plain words, newest first. A revision is named `YYYY.MM.NN`: the year and month it shipped, then its number within that month. Your vault's `CLAUDE.md` records which revision the vault is on.

**To bring a vault up to date**, pull the kit's `stable` branch (`git -C ~/.paraos/para-os pull`) and run `/para-upgrade` in the vault. It works out which revisions the vault has missed, shows you the plan, and asks before it changes anything. A vault several revisions behind gets all of them in one run. Under each revision, "What to do" names only what the upgrade cannot do for you.

The step-by-step instructions `/para-upgrade` follows live in [CHANGELOG.md](CHANGELOG.md). They are written for the agent, and you never need to read them.

---

## 2026.10.02

### Highlights

- **A dashboard you can work from all day.** The daily brief's page opens on the next action, then what is late or due today, what others owe you, the next 14 days, the people you owe or wait on, and a pipeline you can click into, with late days counted from the day you open it. A tile opens its list in place, and you choose whether the page lives on claude.ai or only on your computer.
- **`/para-upgrade` shows what is out of date.** It names which of the kit's files in your vault are behind and re-copies them when you say so, shows anything you changed yourself before touching it, and takes you through the template's changes to your `CLAUDE.md` one at a time.
- **Lighter on every run.** The instructions your vault loads each session are a third shorter and each skill reads about half as much, so runs start faster and cost less. The skills do the same things.

### Also new

- **Deal sheets for your own home.** A deal sheet now builds for an own home, led by the equity at risk and the works ceiling, and a vault can name the page that holds its available capital.
- **Proposals price from your own deals.** In a vault with the sales module, a drafted proposal prices from your past deals, leaves the price blank when there is nothing to compare against, and keeps your internal figures and notes out of what the client receives.
- **The pipeline shows what each deal is worth.** In a vault with the sales module, every deal on the board shows its value, each stage its total, and one line lists the open deals largest first, naming those with no value yet. Amounts in another currency are shown but never added in.
- **Past clients get a dated revisit.** The pipeline lists past clients nobody has been in touch with for six months, and closing a won engagement asks what the next conversation with that client is.

### Fixes

- **"New deal" starts `/para-new`.** Saying "create a new deal" or "new property" now reliably starts it, so the next step of a new deal stays undated until you give a date.
- **No agenda event dropped.** The daily brief's agenda no longer drops an event because another calendar has a different event starting at the same time: both show.
- **Deadlines first in Now.** When more than five things are overdue or due today, the brief's Now list keeps a hard deadline due today ahead of a plan date or an overdue recurring chore of the same priority.
- **Lessons in projects archived earlier get a home.** Projects archived before close-out asked about lessons kept them in the brief, where nothing reads them. The upgrade now offers each one a place that is read.
- **Writing rules you kept before voice profiles move into one.** If your vault already described how someone writes, in a file of its own or in your working preferences, the upgrade offers to move it into that person's voice profile, so drafts in their name follow it.

### Removed

- **The kit's own test files.** Your vault no longer carries them: they were half of what the install copied in and did nothing for you.
- **Two triage choices nobody used.** Triage offers two fewer choices.
- **The by-hand path for a machine without Python.** Python 3 is now required, so each skill is shorter and reads less on every run.

### What to do

1. Before you upgrade: copy the new `/para-upgrade` skill from the kit into place, wherever your skills live, since an older copy cannot read the new list.
2. Run `/para-upgrade`.
3. Approve the shorter wording section by section when `/para-upgrade` shows it; anything your vault added stays.
4. Install Python 3 from python.org if `/para-upgrade` says it is missing, then run it again.
5. Name your capital page on the new line if you keep one.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.10.02/CHANGELOG.md).

## 2026.10.01

### Highlights

- **To-do lists stay short.** At most eight open items per file, one line each. Say "done", "sent" or "paid" and the item closes, dated. Things you are waiting on from someone else get their own line, and after two weeks the daily brief asks whether to chase or drop them.
- **New: `/para-prep` gets you ready for a meeting.** Who is coming, what is open with each of them in both directions, what was promised last time, and what to ask. It only reads.
- **New: a look back.** Ask the daily brief "what did I get done this week?" for what you closed, which deadlines slipped, what moved and what is stuck. For one project it can draft the status update a client expects.
- **Triage can read the mail you sent** (switch it on per mailbox). A promise you made by a day becomes a dated to-do, and a question with no answer after a working week becomes a "waiting on" line.
- **After a meeting, the follow-up is proposed for you.** Filing the notes of a meeting with a prospect suggests the last-contact date, the next step and a follow-up mail to send.
- **Drafts in your own words.** Ask it to learn how you write from your sent mail; every learned habit shows its evidence.
- **Deadlines come out of documents.** Filing a letter or invoice puts what it asks of you on your to-do list, dated. A contract that renews on its own is dated on the last day you can still cancel.
- **Your vault knows where it is.** One line sets country, currency, financial year, number and date format, and time zone. Amounts carry their currency, and meeting times show in your zone.

### Safer by default

- Mail, documents and web pages are information, never instructions. Anything that tries to give the assistant orders is shown to you as suspicious.
- A request to change bank details, pay urgently, sign in, or share a password or code is held until you have checked it with the sender.
- Login codes and password-reset links never get copied into your vault; you only see how many arrived.

### Also new

- `/para-audit`, if you run several vaults: one table of which ones lag behind and what to run in each.
- A vault on Google Drive, OneDrive or SharePoint can keep a full history in a git repository on your own disk.
- Plaud recorder summaries and transcripts can land in triage, like Pocket and Granola.
- Property vaults: every figure the underwriting works out is calculated by a small program, the deal sheet stops rather than filling in a missing number, and the pipeline shows how long each property has sat at its stage.

### Removed

- The read-only iPad setup.

### What to do

1. Update your copy of the kit: `git -C ~/.paraos/para-os pull`
2. Run `/para-upgrade` in each vault. It shows the plan and asks before every change.

Optional:

- To have triage read sent mail, add `📤 sent` to that mailbox's row in your vault's triage sources table.
- In a property vault, re-run `/property-underwrite` before rebuilding the deal sheet of a property underwritten before this release.
- If you used the iPad setup, the PDFs it made are yours to keep or delete.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.10.01/CHANGELOG.md).

## 2026.09.07

### Highlights

- **New: the brainstorm module.** Takes you from what keeps costing you time to two or three ideas worth testing. New vaults are offered it once their first plan is approved.
- **Leads go straight into your register.** Where the vault keeps a lead register, a first mail from a new prospect can become a row (you see it in full first), and later mails update that row.
- **Setting up a business vault** asks whether you sell to clients, and on a yes sets up the sales board.
- **`/para-new` asks you** whether something is a project, an area or an idea, rather than deciding for you.
- **The activity module:** the usage log and `/para-activity-review` now come together as one optional add-on.

### Safer by default

- Every skill that deletes sends files to the trash or version history, one named file at a time.
- Moving something between projects, areas, resources and the archive is always approved one item at a time.
- A file that lands in `triage/` during a triage run is left alone, never deleted with the files you approved.

### Fixes

- The pipeline board no longer drops a prospect over a stray full stop, counts a won lead once, and treats "None planned" as no next step.
- The deep clean checks links inside `archive/` and stops flagging names in prompts, templates, newsletters and sent client documents.
- On Windows, skills no longer fail once on `python3` before retrying.
- `/para-upgrade` finds your kit at `~/.paraos/para-os` on its own.

### What to do

1. Run `/para-upgrade`. If your kit is not at `~/.paraos/para-os`, pass `--clone <path>`.
2. Optional: to keep the deep clean off a sent client document, put `<!-- frozen record: sent to client -->` near its top.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.09.07/CHANGELOG.md).

## 2026.09.06

### Highlights

- **New versions reach you only after they have been tried on real vaults.** Finished releases live on a branch called `stable`, and new vaults and upgrades read from it.
- `/para-upgrade` now also checks the two iPad scripts it used to skip.

### What to do

**Once, before this upgrade,** switch your copy of the kit to `stable`:

1. `git -C ~/.paraos/para-os fetch origin`
2. `git -C ~/.paraos/para-os checkout stable`

After that, pull and run `/para-upgrade` as before.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.09.06/CHANGELOG.md).

## 2026.09.05

### Highlights

- **Setting up a new vault** starts with four quick multiple-choice questions, then a short guided brainstorm that proposes your first projects and areas and creates only the ones you approve.
- **A file for how you like to work** (tone, length, format). Correct the assistant twice on the same thing and it offers to write the preference down; it never changes the file without your yes.
- Many small fixes across the skills and the Granola, Outlook, activity and iPad scripts. Granola now also runs on a Mac.

### What to do

**Before you upgrade:** if you built a skill of your own whose name starts with `para-`, rename it. The upgrade would take it for one of its own and replace it.

Then run `/para-upgrade`. It offers to move preferences your vault already states into the new file, one at a time.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.09.05/CHANGELOG.md).

## 2026.09.04

### Highlights

- **New: `/para-pipeline`.** A vault can track things that move through stages, such as deals or properties, and see them as a board with whatever has stopped moving flagged. The sales add-on is the first to use it.
- **Faster, more consistent skills.** Six skills do their counting with a small script where Python is installed; without Python they work as before.
- **Setting up a new vault** is one prompt pasted into the Claude desktop app.
- Many skill fixes.

### What to do

**Before you upgrade:** copy the new `/para-upgrade` skill from the kit into your vault (or wherever your skills live). The old one looks in folders that were renamed.

Then run `/para-upgrade`, and:

- **If it reports that `.mcp.json` was saved in the vault's git history,** change every password and token that file ever held. The old copies still contain them.
- With several vaults on `/para-ingest`, a vault now receives mail only from the mailboxes it lists, so add any it should keep receiving.
- To use the sales board, ask the upgrade to add the sales module.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.09.04/CHANGELOG.md).

## 2026.09.03

### Highlights

- **Filing and formatting rules move into small files** under `.claude/rules/`, which the assistant reads before anything else.
- **The first flavor: real estate,** for buying, renovating, selling or holding property. A flavor says what a vault is about; the read-only iPad setup becomes a separate delivery.
- **You can name where finished work of a given kind gets archived.**
- **Every skill takes `--test`** to report its own bugs.
- **New:** a Pocket integration for the wearable recorder, and one file listing the mail you never want to see. Granola names notes by your local day.

### What to do

**Before you upgrade:** copy the new `/para-upgrade` and `/para-deep-clean` skills from the kit into place. The old ones look for a folder that moved.

Then run `/para-upgrade`. If you use Granola on more than one computer, update every copy in one go.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.09.03/CHANGELOG.md).

## 2026.09.02

### Highlights

- **Fewer confident wrong answers.** Mostly fixes for skills that gave a wrong answer instead of an error.
- **Each deletion is asked separately,** rather than one yes for a whole batch.
- **`/para-daily-brief` can focus on one project or area** when you name it.
- **New, optional: `/para-ingest`** reads shared mailboxes once and drops each item in the right vault.
- The Outlook script groups mail by conversation and signs in through your browser.
- The vault's `CLAUDE.md` is trimmed to its rules.

### What to do

1. Run `/para-upgrade`. This is the one upgrade that shortens the standard sections of your `CLAUDE.md` to the template's wording, keeping what your vault changed on purpose, so look over that change.
2. If you use the Outlook script, register `http://localhost` as a redirect address on your Microsoft app, or its next sign-in stops and prints the steps.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.09.02/CHANGELOG.md).

## 2026.09.01

### Important: Outlook emails filed before this release are incomplete

Every email the Outlook script filed before this revision holds only the first 255 characters of each message, and nothing in the file says so. Forwarded emails lost the forwarded part. The script now files whole messages, but **no upgrade can repair the old records.**

### Also fixed

- Granola routes meetings correctly on computers set to different languages.
- The activity log keeps recording after a session changes folder.
- Skills no longer build project folders by hand or fetch templates from the internet.

### What to do

1. **If you used the Outlook script:** treat every email record it filed before this revision as incomplete, and reread the original email behind anything you built on one, such as a brief, a summary or a decision.
2. Run `/para-upgrade`.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.09.01/CHANGELOG.md).

## 2026.08.03

### Highlights

- **To-do lists hold only what you can act on now.** Later steps wait as plain text under a Backlog heading until they are unblocked.
- **The daily brief opens with a dashboard** of where every project and area stands, and can show your calendar.
- **New: `/para-new`** creates projects, areas, ideas and contacts the right way.
- **Vaults come with a `.gitignore`** that keeps secrets out of git.
- **Optional additions:** a section for a vault several people edit, one for the code repositories a vault steers, and a usage log that `/para-activity-review` reads.
- Outlook can sync work mailboxes, and Google Docs in a Drive-synced vault become readable.

### What to do

1. Run `/para-upgrade`.
2. Then run `/para-deep-clean` once. Expect long to-do lists to shrink into backlog text and made-up due dates to go.
3. On the iPad delivery, re-render your PDFs afterwards.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.08.03/CHANGELOG.md).

## 2026.08.02

### Highlights

- **Revision names gain a number at the end,** so a month can hold more than one.
- **Meeting notes that belong to one project are filed with that project,** not in a shared meetings folder.
- **The vault's front page has four fixed headings** (Identity, Operating model, Track record, Vision) and no status tables, since the daily brief is the dashboard.
- **Integration scripts carry a version,** so the upgrade can tell you when yours is behind.
- **New:** the Outlook script.

### What to do

Run `/para-upgrade`. It reshapes the front-page README, moves status tables into the projects they describe, asks you for a real Vision if yours is a placeholder, and asks which shipped integration each of your scripts is.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.08.02/CHANGELOG.md).

## 2026.08.01

### Highlights

The first numbered revision.

- **Where to-do checkboxes may live:** never under `resources/`.
- **How to tell a project from an area or an idea.**
- **A `📅` date means a real deadline.**
- A few `CLAUDE.md` sections are renamed and shortened.

### What to do

Run `/para-upgrade`. A vault with no revision label at all gets this revision in full. Expect it to propose turning some projects into areas and dropping invented due dates; you approve each one.

Full details: the `2026.08` entry (renamed `2026.08.01` in the next revision) in [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.08.01/CHANGELOG.md).
