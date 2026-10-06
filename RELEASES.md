# Release notes

What each para-os revision changes for you, in plain words, newest first. A revision is named `YYYY.MM.NN`: the year and month it shipped, then its number within that month. Your vault's `CLAUDE.md` records which revision the vault is on.

**To bring a vault up to date**, pull the kit's `stable` branch (`git -C ~/.paraos/para-os pull`) and run `/para-upgrade` in the vault. It works out which revisions the vault has missed, shows you the plan, and asks before it changes anything. A vault several revisions behind gets all of them in one run. Under each revision, "Do you need to do anything?" names only what the upgrade cannot do for you.

The step-by-step instructions `/para-upgrade` follows live in [CHANGELOG.md](CHANGELOG.md). They are written for the agent, and you never need to read them.

---

## 2026.10.01

**What changes for you.** The read-only iPad setup is gone: the kit no longer turns a vault into PDFs for someone else to read on an iPad. Add-ons now come in two kinds, a flavor (what a vault is about) and a module (something it does beside that). Every skill reads every vault the same way, which removes the special cases behind several bugs. The daily brief has one layout. Setting up a new vault asks three quick choices instead of four, and a business vault is always offered the sales board. The real-estate deal sheet stays a web page next to the property's dossier rather than becoming a PDF. Your working-preferences file gets the newer rule that a preference your own instructions already give everywhere is not copied into each vault. A vault that lists the code repositories it steers keeps that list in a small rules file, read only when a project, idea or area is, which shortens its `CLAUDE.md`. Documents piled up loose in `resources/` now get a proper home: the deep clean flags them and suggests the project, area or folder each one belongs in. On a property vault, the pipeline board now shows how long each property has sat at its stage, where it came from and why a dropped one was dropped, because each dossier opens on a few short header lines. The deep clean now points out a project that has had no dated commitment for six months and suggests making it an area; whether it moves is your call. The daily brief's dashboard can now stay current on its own: a small script, run at the end of each session turn, re-draws the numbers whenever your actions, triage or ideas change, without a brief run; the next action and the agenda still come from the brief itself. A project or area with nothing left open no longer drops out of the daily brief: it is flagged, so you can archive it if it is finished or give it a next step if it has stalled.

**Do you need to do anything?** Run `/para-upgrade`. To have the dashboard refresh on its own, wire the hook the refresh script's own notes describe; the upgrade does not do that for you. It tidies your rule files and the line in your vault's `CLAUDE.md` that listed the old delivery. A vault still on the iPad setup gets its files put back in their folders one last time and the iPad scripts removed; the PDFs it made are yours to keep or delete. It also offers to move each loose file in `resources/`, one at a time; say no to any you want to keep where it is.

## 2026.09.07

**What changes for you.** A fix to `/para-upgrade`: when it re-checks an installed script's own tests, it now runs all of them, not just the first. A fix to `/para-triage`: a file that lands in `triage/` while a triage run is going, from a mail sync for instance, is left alone and named at the end, never deleted with the files you approved. New in `/para-triage`: where the vault keeps a lead register, a first mail from a new prospect can go straight into it as a row, which you see in full before it is added, and a later mail from them updates that row. The daily brief puts overdue recurring items in Now. The pipeline board no longer drops a prospect over a full stop after its stage, counts a won lead once, and flags a lead whose next step reads "None planned" as having none. The deep clean checks links inside `archive/`, stops flagging names in prompts, templates, synced newsletters and sent client documents, no longer skips a file just because a word like "review" sits inside its name, and says which checks it does by hand. On Windows, skills no longer fail once on `python3` before trying again. Every skill that deletes sends files to the trash or version history, one named file at a time. `/para-upgrade` finds your copy of the kit at `~/.paraos/para-os` on its own, and brings module sections you copied in by hand up to the shipped wording. Mail notes staged from two mailboxes for one conversation are paired. The daily brief answers "what should I work on today?" with the full brief. Setting up a vault for a business now asks whether you sell to clients, and on a yes sets up the sales board for you. A new optional add-on, the brainstorm module, takes you from what keeps costing you time to two or three ideas worth testing, and new vaults are offered it once their first plan is approved. The pipeline asks which board you meant when you name one the vault does not have. `/para-new` asks you whether something is a project, an area or an idea rather than deciding for you. Archiving never force-deletes a leftover folder, and commits only where your own rules allow. Moving something between projects, areas, resources and the archive is always approved one item at a time, and the deep clean asks before installing anything. The activity review counts the skills people reach by asking in plain words, and it now comes with the usage log it reads as one optional add-on, the activity module: a vault that records its use gets the module, and one that does not loses a skill it could never run. Three house rules that contradicted each other now agree: a contact card may end on its backlog, a README inside a project's subfolder is not a project README, and two exports with the same name get a number.

**Do you need to do anything?** Run `/para-upgrade`. If your copy of the kit is not at `~/.paraos/para-os`, pass `--clone <path>`. To keep the deep clean off a sent client document, put `<!-- frozen record: sent to client -->` near its top.

## 2026.09.06

**What changes for you.** New versions of the kit now reach you only once they have been tried on real vaults. The kit keeps finished releases on a branch called `stable`, and new vaults and upgrades read from it. `/para-upgrade` now also checks the two iPad scripts it used to skip.

**Do you need to do anything?** Once, before this upgrade: switch your copy of the kit to `stable` with `git -C ~/.paraos/para-os fetch origin`, then `git -C ~/.paraos/para-os checkout stable`. After that, pull and run `/para-upgrade` as before.

## 2026.09.05

**What changes for you.** Setting up a new vault starts with four quick multiple-choice questions, then a short guided brainstorm that proposes your first projects and areas and creates only the ones you approve. Every vault gets a file for how you like to work (tone, length, format): when you correct the assistant twice on the same thing, it offers to write the preference down, and it never changes the file without your yes. Many small fixes across the skills and the Granola, Outlook, activity and iPad scripts; Granola now also runs on a Mac.

**Do you need to do anything?** Run `/para-upgrade`. It offers to move preferences your vault already states into the new file, one at a time. If you built a skill of your own whose name starts with `para-`, rename it first: the upgrade would take it for one of its own and replace it.

## 2026.09.04

**What changes for you.** A vault can track things that move through stages, such as deals or properties, and the new `/para-pipeline` shows them as a board with whatever has stopped moving flagged. A sales add-on is the first to use it. Six skills do their counting with a small script, so they are faster and more consistent where Python is installed; without Python they work as before. Setting up a new vault is one prompt pasted into the Claude desktop app. Many skill fixes.

**Do you need to do anything?** Yes, before you upgrade: copy the new `/para-upgrade` skill from the kit into your vault (or wherever your skills live), since the old one looks in folders that were renamed. Then run it. If it reports that a file called `.mcp.json` was saved in the vault's git history, change every password and token that file ever held, because the old copies still contain them. With several vaults on `/para-ingest`, a vault now receives mail only from the mailboxes it lists, so add any it should keep receiving. To use the sales board, ask the upgrade to add the sales module.

## 2026.09.03

**What changes for you.** Filing and formatting rules move into small files under `.claude/rules/`, which the assistant reads before anything else. The read-only iPad setup is now called a delivery, separate from a flavor, which says what a vault is about; the first flavor is real estate, for buying, renovating, selling or holding property. You can name where finished work of a given kind gets archived. Every skill takes `--test` to report its own bugs. New: a Pocket integration for the wearable recorder, and one file listing the mail you never want to see. Granola names notes by your local day.

**Do you need to do anything?** Before you upgrade, copy the new `/para-upgrade` and `/para-deep-clean` skills from the kit into place: the old ones look for a folder that moved. Then run `/para-upgrade`. If you use Granola on more than one computer, update every copy in one go.

## 2026.09.02

**What changes for you.** Mostly fixes for skills that gave a confident wrong answer instead of an error. Skills ask you about each deletion separately rather than taking one yes for a whole batch. `/para-daily-brief` can focus on a single project or area when you name it. The Outlook script groups mail by conversation and signs in through your browser. An optional multi-vault layer, `/para-ingest`, reads shared mailboxes once and drops each item in the right vault. The vault's `CLAUDE.md` is trimmed to its rules.

**Do you need to do anything?** Run `/para-upgrade`. This is the one upgrade that shortens the standard sections of your `CLAUDE.md` to the template's wording, keeping what your vault changed on purpose, so look over that change. If you use the Outlook script, register `http://localhost` as a redirect address on your Microsoft app, or its next sign-in stops and prints the steps.

## 2026.09.01

**What changes for you.** An important fix to the Outlook script: every email it filed before this revision holds only the first 255 characters of each message, and nothing in the file says so. Forwarded emails lost the forwarded part. It now files whole messages. Granola routes meetings correctly on computers set to different languages, and the activity log keeps recording after a session changes folder. Skills no longer build project folders by hand or fetch templates from the internet.

**Do you need to do anything?** If you used the Outlook script: yes. Treat every email record it filed before this revision as incomplete, and reread the original email behind anything you built on one, such as a brief, a summary or a decision. No upgrade can repair them. Then run `/para-upgrade`.

## 2026.08.03

**What changes for you.** A to-do list holds only what you could act on now; later steps wait as plain text under a Backlog heading until they are unblocked. The daily brief opens with a dashboard of where every project and area stands, and can show your calendar. The new `/para-new` creates projects, areas, ideas and contacts the right way. Vaults come with a `.gitignore` that keeps secrets out of git. Optional additions: a section for a vault several people edit, one for the code repositories a vault steers, and a usage log that `/para-activity-review` reads. Outlook can sync work mailboxes, and Google Docs in a Drive-synced vault become readable.

**Do you need to do anything?** Run `/para-upgrade`, then `/para-deep-clean` once: expect long to-do lists to shrink into backlog text and made-up due dates to go. On the iPad delivery, re-render your PDFs afterwards.

## 2026.08.02

**What changes for you.** Revision names gained a number at the end, so a month can hold more than one. Meeting notes that belong to one project are filed with that project, not in a shared meetings folder. The vault's front-page README has four fixed headings (Identity, Operating model, Track record, Vision) and no status tables, since the daily brief is the dashboard. Integration scripts carry a version, so the upgrade can tell you when yours is behind. New: the Outlook script.

**Do you need to do anything?** Run `/para-upgrade`. It reshapes the front-page README and moves status tables into the projects they describe, and asks you for a real Vision if yours is a placeholder. It also asks which shipped integration each of your scripts is.

## 2026.08.01

**What changes for you.** The first numbered revision. It sets where to-do checkboxes may live (never under `resources/`), how to tell a project from an area or an idea, and that a `📅` date means a real deadline. A few `CLAUDE.md` sections are renamed and shortened.

**Do you need to do anything?** Run `/para-upgrade`. A vault with no revision label at all gets this revision in full. Expect it to propose turning some projects into areas and dropping invented due dates; you approve each one.
