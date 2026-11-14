# Release notes

What each para-os revision changes for you, in plain words, newest first. A revision is named `YYYY.MM.NN`: the year and month it shipped, then its number within that month. Your vault's `CLAUDE.md` records which revision the vault is on.

**To bring a vault up to date**, pull the kit's `stable` branch (`git -C ~/.paraos/para-os pull`) and run `/para-upgrade` in the vault. It works out which revisions the vault has missed, shows you the plan, and asks before it changes anything. A vault several revisions behind gets all of them in one run. Under each revision, "What to do" names only what the upgrade cannot do for you.

The step-by-step instructions `/para-upgrade` follows live in [CHANGELOG.md](CHANGELOG.md). They are written for the agent, and you never need to read them.

---

## 2026.11.02

### Highlights

- **Your vault's rules now live in two files.** The fixed para-os rules are one file that an upgrade copies whole, and your `CLAUDE.md` holds only what is true of your vault. An upgrade no longer walks through your `CLAUDE.md` section by section, and never edits it without asking line by line.
- **Deep clean suggests a return to the standard.** It reads the rules your vault added in its own `CLAUDE.md` and proposes, line by line, which can go because para-os already says them and which are truly yours. Nothing is removed without your yes.
- **Meetings recorded after the morning ingest reach triage the same day.** Triage used to skip a meeting-notes import whenever the ingest had already run it, so a meeting held that afternoon waited for the next morning. It now runs the import every time, and its record of what was imported keeps it to what is new.

### Fixes

- **Scripts of a vault pulled on another machine now show in the Command Center.** When that vault's folder also syncs to your machine, its scripts are read and linked to it, each to the connection listed for that machine.
- **"Proposal waiting" no longer sticks after triage.** The daily brief kept flagging an unattended triage proposal whose items had all been handled, and older proposals piled up unread. Triage now closes every proposal nothing is left waiting on, and the brief flags one only while an item it holds is still in triage.
- **The Command Center shows how each scheduled run went.** Its Scheduled runs card read a run log no scheduled task wrote, so every run showed as unknown. It now reads each task's last run from the desktop app, which keeps them, and a paused task shows as paused. The ingest also names the tool for its work files, so an unattended run no longer skips that step for want of an approval.
- **Archiving no longer flags a correct link as left behind.** When another archived folder linked into the one being archived, the check after the move read the updated link as a mention of the old location, so you had to approve keeping a link that was fine. A link that leads to the new location now passes.
- **The restore command triage shows you now runs as pasted.** It used to leave out the Python launcher and the script's folder, and broke on a vault whose name has a space. It is now the whole command, with the name in quotes.
- **`/para-prep` finds a "Do not raise" point however it is worded.** A brief that says "don't raise", "avoid raising" or "do not bring up" used to give a prep with no Do not raise section. Those wordings now count, as a label, a heading or a sentence, which is listed whole.
- **An idea whose status sits in a quote block shows the right stage.** When an idea's brief opened on a quoted status line, the daily brief showed the idea's first paragraph or the raw markup as its stage. It now reads the status from the quoted line.
- **The overdue total counts a late recurring item.** A recurring action past its date was listed under Overdue while the totals line said none were overdue. The total now counts it, and a line that waits on someone else is no longer counted as upcoming.
- **A long list of pipeline flags is cut short.** Past fifteen flags the board shows ten and counts the rest, and a pipeline with no closing stage no longer prints a closed count of zero.
- **A meeting prep reads the last meeting, a closed lead and dated facts correctly.** "Last time" is now the newest meeting the person attended, not a newer one that only mentions them. A lead in the closed part of a register no longer shows a stage and days in stage as if it were open, a person with no card whom your records already name is no longer asked about, and every date on a stage line counts, not only the first in each part.
- **Deep clean names the right owner for loose archive files and meeting records.** A file sitting directly in an archive folder now belongs to that folder, so its copies there are no longer reported as spread over several entities. A meeting record that links a contact card is no longer proposed for a move into the contacts folder.
- **Deep clean reports fewer false findings.** Your own scripts no longer add to the audit count. A link inside a folder you declared as templates, a name in a note's properties block, a first name that is part of another contact's full name, and an address your own contact card already holds are no longer reported.
- **A converted vault is no longer shown as behind.** After the move to two files, the daily brief and deep clean still looked for the revision in your `CLAUDE.md` and reported the vault as out of date. They now read it where it lives.

### Removed

- **Three skills are gone.** `/para-audit`, `/para-brainstorm` and `/para-activity-review` leave the kit, and the upgrade offers to delete your copies. The Command Center still shows how each vault stands against the kit, and a vault that records its use keeps recording it.

### What to do

1. Run `/para-upgrade`.
2. If a scheduled task's prompt ends by recording its run with `paraos_runs.py record`, delete that step and the command from the task's allowed list: the command is gone.
3. Read what the upgrade proposes to remove from your `CLAUDE.md` before you approve it: a rule you reworded on purpose stays yours.
4. The upgrade also proposes renames: an area's `README.md` to `brief.md` and a contact card to first name then last name. In a vault several people write, tell the others first.
5. Renaming your existing dated documents to the one naming pattern is offered as a separate job. You can leave it for later: it needs a plan you have read, and new documents take the pattern either way.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.11.02/CHANGELOG.md).

## 2026.11.01

### Highlights

- **You can see when a session is safe to close.** Every reply now ends with a Close line saying whether closing would lose anything, such as a decision not yet written down or a question still open, and the vault writes what it learns by the end of each turn rather than at a session's end it cannot see. In the Claude desktop app and terminal, a band above the prompt shows that verdict beside how long the session has been open, what waits in triage and the vault's health, and turns amber while closing would lose something.
- **A health card for every vault.** The daily brief's page and the Command Center now say whether a vault is being kept: when it was last edited, how long triage has waited, the last deep clean, how far its template is behind, waits past two weeks, and which skills have not been reviewed against the model you run. Each line opens on what it measures, why it matters and what to do.
- **A mail that tries to give the assistant instructions is held, not filed.** Triage already quoted such an instruction and ignored it, but still filed the item and added its actions. Whoever hides an instruction in a mail may have forged the rest, so the item now stays in triage until you confirm it through a contact you already have.
- **Mail that skips the inbox is no longer missed.** The ingest and triage now read every message received in the window, archived or filtered ones included, as the Outlook reader already did, so a mailbox kept at inbox zero no longer looks empty.
- **One page shows every vault at once.** For operators running several vaults, the Command Center draws each vault as a building in a neighbourhood you name, with its health grade, what waits in its triage folder and what is held for you; what came in over the week, grouped by kind, and where it went; the scheduled runs, the repos and the websites; and the weeks ahead. A script builds it from your files, with no judgment from the model, so the same files always give the same page. It replaces the global brief and the triage funnel page, which are retired.

### Safer by default

- **Your exclusions are applied by the script, not by the assistant.** An excluded sender used to depend on the assistant remembering the list at every run, and once it did not. The ingest now drops those threads in code and reports each entry's count from code. One entry can now cover every mailbox (`*`), several senders under one label (a group), or everyone writing to a group address (`to` and `list`).
- **The agent can no longer open the integrations' tokens.** The vault's Claude Code settings refuse the agent's file tools the folder where the integration scripts keep their tokens, on every machine that opens the vault, with no setting of your own. The scripts keep working.

### Also new

- **Roles on a shared vault's roster.** Each person who writes a shared vault is now its keeper, a member or a steward, and triage reads which one is you from a small file instead of asking each time.
- **Keep your own words out of a shared usage log.** Each person can switch off recording what they type, on their own machine, whatever the vault's setting says. A file path outside the vault is recorded only as being outside it, and the usage review counts conversations unrelated to the vault without quoting them.
- **The fleet audit reads each vault's rule files, not just their names.** For operators running several vaults, `/para-audit` now reports a rule file with no list of the paths it governs, which loads into every session of its vault, and a shape file with no Placeholders section, each with its fix.
- **Triage offers to stop a sender it keeps dismissing.** When you dismiss mail from the same sender, or from several addresses at one domain, as noise a second time, triage offers to add it to your exclusions and says what else that would hide. It writes nothing without your yes, and backs the file up first. Routing between vaults also stops treating a club or company named on a contact card as a reason to send its mail there.
- **Scheduled triage can file documents.** In a vault kept in git, once you switch `File it` on for it, an unattended run moves a document into the sources folder of the project, area or idea it belongs to, repoints any link to it, and commits each run on its own, so one revert undoes it. A restore moves it back and switches `File it` off again.
- **The upgrade checks your CLAUDE.md against the template, section by section.** A vault on the latest revision whose CLAUDE.md still carries an older revision's wording, or has lost a section, now gets each such section shown as a difference, to re-copy or keep, the same way as a kit file someone changed. The values you filled in and your own sections are never part of it.
- **The fleet audit shows which vaults' CLAUDE.md has fallen behind the template.** A new Sections column counts, per vault, the sections that still carry an older revision's wording or are missing, so a vault on the latest revision no longer passes when its CLAUDE.md does not match it. The fix it names is the upgrade, which shows each section to re-copy or keep.
- **Every page a skill publishes is listed in one place.** The pages index records each page with the skill or vault that publishes it, and a page another one replaces is marked retired, with what replaced it, before its artifact is deleted. The page records each skill kept on its own are read into the index the first time it is used, and left where they were.
- **The vault registry says who pulls a vault.** A vault another machine pulls is left out of this machine's ingest and shows its health on the Command Center with no triage count. A vault whose work is over is deleted from the registry rather than marked retired.
- **Scheduled runs are listed and leave a record.** A task registry beside the vault registry says what each scheduled task reads and through which connection, each run of the shipped routine records how it went, kept for 90 days, and the audit reports a scheduled task the registry misses or whose schedule differs.
- **The code repos a vault steers are one table.** Each repo now says whether the vault owns it, keeps it for reference or only consults it, where its work lives in the vault, and, for a repo that builds a website, which site and which vault it serves. The upgrade turns the list you have into the table, each repo's description kept word for word, and asks only what it cannot tell from the text.
- **Every connection to an outside source is listed once.** A connections file in your para-os folder names each mail connector, recorder sync, script, command-line tool and browser task, with the vaults it serves, the name of its secret and what it writes, plus a label for every mailbox. What your vaults already declare is read from them rather than listed again, the vault audit reports anything the file misses or gets wrong, and the machine manifest opens on a table built from it.
- **The audit flags a retired script still listed as a connection.** Mark a script you keep but no longer run, and the vault audit tells you to take it off the connections file.
- **A script nobody listed is still seen.** The connections registry now reads the code of the scripts in each vault, and of the ones your own skills run from a code repo, and counts any that calls an outside host or a command-line tool you listed, so the page draws it under the system it reaches and `/para-audit` names it until it has an entry.

### Fixes

- **The write-time check no longer stops on the run's own work.** Naming the files a run moved or wrote over several `--done` flags now leaves all of them out, not only the last flag's.
- **A deep clean no longer proposes linking a name in the lead register.** Its Contact column holds a name, not a link, as the sales module's rules say, and the scan now reads that from the vault instead of waiting to be told.
- **Unattended triage no longer skips a vault after a decision with no recommendation.** One such decision made the status check fail, so every scheduled run passed that vault by with an error.
- **Two deals sharing a champion no longer show the same next step.** The board takes a deal's step from its champion's card only from an item that is not another live deal's, preferring one that links the deal itself.
- **The usage review counts a session left open for days as one session, and flags it.** It counted one per day, so a vault with long sessions now reports fewer sessions than an earlier review did.
- **A lead's next step keeps its own date.** A date written beside the step, such as the day a prospect's new site launched, no longer reads as the step's due date once the step carries the calendar marker. The upgrade offers to add the marker to the leads you already have.
- **A vault that carries its own skills gets every one, even one you also installed for yourself.** The upgrade skipped a skill missing from the vault's own copies when the same skill was installed on your machine, so the people who run the vault from theirs never had it. The next upgrade copies any such skill in.
- **A shared mailbox can be filtered by your lead register.** When several vaults read one mailbox, a thread from a company that is only a lead on your register, with no contact card yet, now reaches the vault that holds the lead instead of being routed nowhere.
- **Mail among the people who write a shared vault no longer lands in it on their cards alone.** When a vault several people write reads one writer's mailbox, a thread that includes another writer is routed by a client's card or by what it is about, not by that writer's own contact card.
- **A worktree copy of the vault no longer counts as the vault.** When a session ran in a worktree, its checkout inside the vault was read as vault content, so the briefs listed every open action in it twice and the cleanup and archive checks looked inside it too.
- **A misspelt name now gets a suggestion.** Naming a project or area with a letter dropped or swapped near the start left the daily brief with nothing to offer. It now suggests the closest folders, best match first.
- **A mailbox kept for one writer is no longer pulled on anyone else's triage.** A triage source marked `pulled by` a named writer was left out of the other writers' runs only when the session noticed the marker; the scan now plans it as skipped on their runs.
- **`/para-ingest` does its mechanical steps in code.** Planning the run, running the sync and fetch scripts under the volume gate, checking each thread against the ledger and settling a thread a known contact decides used to be worked out from instructions on every run, a little differently each time. A script now does all of it the same way every run, and the assistant judges only the threads no contact settles.
- **`/para-ingest` picks up where its last run left off.** Each mailbox is read from a day before the last write run that read it, so a machine closed for a long weekend no longer loses the mail in between, and a mailbox a run could not read is read again next time. Mail a vault was owed while it was unreachable is re-checked and delivered once it is back, and carry-over is worked out once, on a mailbox's first write run, instead of by hand on every run.
- **The deep clean no longer downloads a whole cloud-synced vault.** Its duplicate check now opens only files whose size another file shares, so on a vault that Google Drive or OneDrive streams on demand it finishes in minutes instead of fetching every file. An area archived whole as one folder is no longer reported as missing its record.
- **The actions a scheduled triage may take now sit with the vault they belong to.** They are a vault's `auto_triage` list in `vaults.json`, so renaming or adding a vault can no longer leave them silently unmatched. A restore writes only to the cache; `switch` is the one command that edits the registry, after a backup.
- **Mail and unattended triage fail safe.** A mailbox Outlook could not read no longer counts as read, so `/para-ingest` fetches what arrived during the outage once it is back. A scheduled triage run keeps one of two identical items, and what it moved can always be restored, even after a crash. Granola no longer imports a filed meeting twice, the Command Center survives a meeting repeat it cannot count, the close band sees edits in a vault below its repo root, and a saved `.eml` keeps its accents.
- **Six smaller repairs from the same review.** Outlook's token file stays readable only by you after every refresh. The Command Center reads a schedule that names its days, such as `MON-FRI`, so a weekend no longer shows as due. A sync that failed no longer counts as written, the activity review keeps a prompt holding an unusual line separator, and a vault mirror whose copy stopped partway finishes it on the next run instead of blaming someone for editing it.
- **`/para-prep` no longer takes one contact for another.** An email address counts as a contact's own only above the first heading of their card, so a card whose history or actions mention somebody else's address is no longer shown as that person. A "Do not raise" point written as one bullet in a list no longer pulls in the bullets after it.
- **`/para-prep` no longer loses the project of someone with no contact card.** When meeting records in a project, area or idea name the attendee, the prep now shows that entity's stage, what not to raise and its open items, including those naming the person by first name only, and no longer says the vault holds nothing more on them.
- **The triage routine no longer stops to ask while it publishes the page.** It pre-approves the two commands that record and find the page's link, so a scheduled run never waits on a permission prompt nobody is there to answer.

### Removed

- **CLAUDE.md no longer points at each voice profile.** A draft finds the sender's profile on its own, by the account it goes out from, so the paragraph naming each person's profile can go. The upgrade offers to delete yours.

### What to do

1. Run `/para-upgrade`.
2. If you share a vault with someone: create `operator.json` in your para-os folder holding your own contact card's file name, such as `{"card": "jane-doe"}`.
3. If you run several vaults: the `kind` field in your vault registry is no longer read, and you can delete it.
4. If you run several vaults: to have a busy vault of your own counted rather than listed on the Command Center, add `"brief": "summary"` to its entry in your vault registry.
5. If you write a vault that records its use and want what you type kept out of its log: create `activity.json` in your para-os folder holding `{"record_prompts": false}`.
6. If you run `/para-ingest`, copy its folder from the kit's multi-vault folder again, beside the other skills.
7. If a scheduled task runs the ingest, remove any step in its prompt that dry-runs the sync scripts or applies the volume gate itself: the ingest does that now.
8. After the upgrade, start a new session: the band loads when a session starts, and only in a vault folder Claude Code trusts.
9. If you run several vaults: in your vault registry, add `"machine"` naming who pulls each vault another machine ingests, and delete the entry of any vault marked `"retired"`, since the audit and the Command Center no longer skip it.
10. After you upgrade: run `py -3 ~/.claude/skills/para-triage/scripts/auto_execute.py migrate` once. It moves `auto-triage.json` into the registry and the cache and renames it `auto-triage.json.migrated`; until then the older file keeps working.
11. If you schedule tasks across your vaults: list each one in the task registry, from its template in the kit's multi-vault folder, and end each task's prompt with the record step the auto-triage routine shows.
12. If you use integrations or connectors: create the connections file in your para-os folder from the template beside the integrations, one entry per connection and one per mailbox, then run the vault audit, which names anything still missing.
13. If you run several vaults: point your morning scheduled task at `/para-command-center` instead of `/para-global-brief`, and take the funnel page step out of your ingest task's prompt.
14. If a scheduled task runs the triage routine, copy its prompt and its always-allowed commands again from the routine in the kit's multi-vault folder.
15. If you run several vaults: delete the old All Vaults and Triage funnel artifacts once the Command Center is published.
16. If a vault you set up is no longer read, such as one handed over to a client, and you want it on the page: list it in `past-vaults.json` in your para-os folder, from the template beside the multi-vault README.
17. If `/para-audit` or the Command Center names a script as not in the connections registry: give it an entry in `connections.json` in your para-os folder, or add its path to the `ignore` list there when it is not a connection, such as a sign-in helper.
18. If a contact card keeps the person's own email address under a heading, move it above the card's first heading.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.11.01/CHANGELOG.md).

## 2026.10.04

### Highlights

- **The upgrade stops skipping changes to your vault's instructions.** An upgrade could leave out what changed in the template between two releases, so this one goes through your vault's instructions section by section, once, and offers whatever an earlier upgrade missed.
- **The daily brief says what to run next.** The triage count names `/para-triage` beside it, and once a month has passed without a deep clean, or none has run on this computer, a health line names `/para-deep-clean`.
- **A new vault is offered unattended triage at setup.** The bootstrap offers to schedule the triage routine for a single vault too, at the cadence you name. It acts only on the kinds of item you switch on, which triage offers once your decisions repeat.
- **A shared inbox is read only where it belongs.** In a vault several people write, a source can say which writer pulls it, and the others skip it. Before reading a mailbox or recorder, triage checks that the connector is signed in to the account the source names, so one partner's private mail is never proposed into the shared vault.

### Safer by default

- **On Windows, upgrade soon: a delete keeps a file's name out of the command it runs.** A name holding certain characters could make the delete fail or reach that command. `/para-upgrade` brings the fix.
- **A failed copy during an upgrade leaves the file as it was.** The upgrade used to empty a file when the version it copied in could not be read; it now writes the new version whole or not at all.
- **Your sign-in tokens can stay out of the assistant's reach.** The sync scripts read their own tokens and no skill opens them, so one setting can keep the assistant out of that folder. [Data and privacy](docs/data-and-privacy.md#keep-the-secrets-folder-out-of-the-agents-reach) shows it.

### Also new

- **A vault can give a skill a page of its own.** Name the skill and a script under Pages in the vault's instructions, and `/para-pipeline` builds that page from its board after every run and publishes it the way the daily brief publishes its dashboard.
- **Deep clean finds the copies a sync client leaves behind.** A file like `brief (1).md`, a "conflicted copy", or a copy named after another computer is listed beside the file it duplicates, and nothing is proposed until you have compared the two.
- **Moving a folder or a file fixes its links in the same step.** Archiving, promoting an idea and a deep clean's moves all go through one shared command that refuses to overwrite anything and rewrites every link into and out of what moved, so no session writes a script of its own for it.
- **An estimate says what it rests on.** A figure that is an estimate now carries its basis beside its date: a quote, a comparable, a rule of thumb or a guess.
- **A second vault on the same mailbox has a setup page.** Setting up a second vault beside your first now offers the steps that give each vault only its own mail, instead of both reading the whole mailbox.
- **The upgrade adds an add-on you ask for.** Name one, such as `/para-upgrade --add sales`, and it runs that add-on's setup in an existing vault, each step on your yes, where you used to follow the steps by hand.
- **Exclusions can name a whole sender domain or a word in the subject.** A school, a club or a booking platform that writes from many addresses is dropped with one entry instead of one per address.

### Fixes

- **The upgrade finds sync scripts installed before they carried a version line.** It used to skip them, so an old copy of the vault mirror kept a fault that could delete files from the mirror.
- **A kit file you added lines to takes the kit's later changes.** The upgrade used to treat it as your own edit and keep it as it was; it now updates the kit's part and keeps your lines where they stood, and names them when it cannot place them.
- **`/para-ingest` stages through one script.** Its notes, ledger and run log are written by `stage.py` instead of code each run wrote for itself, so every staged note has the same shape, says whether your own messages were fetched, and names the command that reads it at source.
- **The quarter's promoted count includes what has already moved on.** An entity promoted and moved to a later stage in the same quarter is counted by its Won date, where it used to drop out of the count.
- **A late weekly pipeline review no longer starts its successor overdue.** The next review is now dated a week after the one you tick, not a week after the date the late one carried.
- **Your own file naming lives in your vault's instructions, not in a kit file.** Saying how your vault names documents used to mean editing a kit file, which then stopped receiving the kit's later fixes. The upgrade moves your naming into your instructions and restores the kit's file.
- **A connection that fails gets repaired, not replaced.** When a shipped integration cannot connect, the assistant fixes or reports it instead of writing a script of its own, and the deep clean points out a second script reading the same source. Granola now says which step to run when its sign-in is missing or has expired.
- **A second computer no longer imports what the first already did.** The record of which meetings and recordings were imported now lives in the vault, beside its sync scripts, so it syncs with the vault. The old record on each computer is still read, and carried in on the next import. Getting started now says what to set up on each computer when one vault runs on two.
- **Property vaults get the deal sheet for a home you mean to live in.** It reached the kit after most property vaults were set up, and theirs never received it; the upgrade now offers it.
- **Answers follow the language you write in.** A request typed in another language than the vault's is answered in that language; the vault's language stays the default for unattended runs.

### Removed

- **Two leftover skill notes are deleted.** The shorter triage and pipeline skills no longer read their scan notes, so the upgrade offers to delete both.

### What to do

1. Run `/para-upgrade`.
2. If you run `/para-ingest`, copy its folder from the kit's multi-vault folder again, beside the other skills.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.10.04/CHANGELOG.md).

## 2026.10.03

### Highlights

- **Any mail, recording or calendar connector works.** A mailbox, a meeting recorder or a calendar can come from any connector, not only Google: declare it under your sources by kind (add `recording` after a recorder's name), and the skills find its reading tools. Nothing is ever sent, deleted or answered through it.
- **Triage can run on its own, one kind of action at a time.** `/para-triage auto` deletes duplicates or dismisses noise only for the kinds of action you switch on for a vault, and leaves everything else for your next session. Nothing is switched on until you say so. Every file it takes goes to a quarantine outside the vault, and one restore command brings it back and switches that kind off again. Mail is never touched. Your next `/para-triage` opens on what ran, and offers to switch a kind on once you have accepted nearly all of its last 50 recommendations unchanged.
- **What a conversation settles gets written down.** A date agreed, a decision and its reason, or an action finished or promised is written into the file it belongs in before the session ends, or you are asked about it once, instead of being left as an offer for next time.

### Also new

- **Triage in a shared vault leaves other people's items to them.** Where the vault lists who writes it, `/para-triage` asks you only about items in your own areas or in nobody's, and lists the rest as left for whoever owns them.
- **One brief across all your vaults.** If you run several vaults, `/para-global-brief` shows each one's open, overdue and due-this-week counts in one table, the urgent items across them with their vault named, and the one thing to do first. It changes nothing. Install it from the multi-vault folder beside the other skills.

### Fixes

- **Archiving stops asking about Backlog lines already settled.** A line whose outcome is written in italics, or one that says Dropped, now counts as settled, so `/para-archive` no longer asks about it again.
- **The write-time check no longer calls every file changed on Windows.** A snapshot whose paths use forward slashes now matches its files, so `changed` lists only what really changed.
- **The upgrade can say there is nothing to do.** It now adds the vault's own settings file where one is missing, instead of skipping it every time, so the setting travels with the vault to everyone who uses it.
- **The deep clean stops calling a hidden copy of the skills a duplicate.** Files in hidden folders, such as the copy of the skills another agent reads, are no longer listed as duplicates, so none can be deleted as one.
- **The upgrade stops proposing placeholder files.** It no longer offers the files a new vault starts with, such as a README for a folder the vault never created, so it never creates a folder the vault left out on purpose.
- **The deep clean stops reading a diagram as an unfilled placeholder.** It now looks for `{{...}}` only in the vault's root `CLAUDE.md` and `README.md`, the two files setup fills in, so a vault with a diagram can pass the final check.
- **The deep clean's final check no longer passes an open checkbox where the vault forbids one.** A checkbox in `resources/`, or on a contact card in a vault that keeps none there, now fails the final check, as the first phase already reported it.
- **The upgrade stops asking about your working preferences.** Once you add a preference, the file no longer reads as changed by you on every upgrade, and an upgrade can no longer replace your preferences with the empty template.
- **The upgrade no longer replaces a filled-in file that matches something else in the kit.** A file counts as an old, unchanged copy only when it matches what the kit once shipped in that same place; any other file is shown to you before it changes.
- **The daily brief stops asking whether an area is finished.** A project or area with nothing open is now flagged as just that, since an area is kept up rather than finished.
- **Triage proposes a delete where you would choose one.** An item whose outcome is kept elsewhere, such as in a shop's own account or a portal, is proposed for deletion instead of left waiting, nothing a portal, a direct debit or your calendar already tracks becomes an action, and the facts of a summary or another tool's export are copied into the projects and areas they concern, each naming where it came from. A contract, an invoice or a signed letter is still filed. A document no project or area owns is handled the same way: deleted when its outcome is kept elsewhere, or filed in the business area when it is worth keeping, such as a policy covering the whole business.
- **Properties no longer show as unknown deal stages.** In a vault with both the property and sales add-ons, the pipeline listed every property sharing a folder with the deals as a deal at an unknown stage. A stage another lifecycle declares now belongs to that lifecycle.
- **The deep clean no longer flags the archive's own index page.** A fresh vault's meetings archive ships with a short page describing the folder, and the deep clean listed it as an undated meeting record, so the archive never came out clean.
- **The brief names only a project's champion or contact as the one its tasks are owed to.** A card the project brief links for another reason, such as the agent who referred a property, no longer gets every unlinked task in that project.
- **Rewording a vault's heading no longer starts a second dashboard.** The daily brief names its dashboard after the vault's name in the vault registry, so editing the heading of the vault's instructions leaves the page it updates where it was.
- **The deep clean stops reporting false contacts and false phone numbers.** The contacts folder's own index page is no longer read as a person, and only numbers written the way phone numbers are (an international prefix, or a leading zero with grouped digits) are reported as phones to move onto a card, so bank account numbers, file references and identity numbers stay where they are.
- **The upgrade keeps your shared skill library in step with every skill that uses it.** Where some skills run from your user-level skills folder and others from the vault, the upgrade now checks the shared library in both places, so re-copying a skill can no longer leave it importing an older library and failing to start.

### Removed

- **The daily brief no longer counts long action lines.** An action's first line still stays under 120 characters, as your vault's rules say, but the brief stops flagging the ones that run over.

### What to do

1. Run `/para-upgrade`.

Full details: [CHANGELOG.md at this tag](https://github.com/Vinedine/para-os/blob/2026.10.03/CHANGELOG.md).

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
