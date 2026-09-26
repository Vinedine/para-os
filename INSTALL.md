# Installing a para-os vault

The steps an agent follows when an operator pastes the Quickstart prompt from [README.md](README.md#quickstart) into a Claude Code session: set up a new vault in the session's folder from this repository, then hand over to the bootstrap interview. A person can follow them by hand too.

**Needs:** Claude Code and git, which the README's Quickstart has the operator install first (the zip below is a fallback only, since `/para-upgrade` needs the clone); Python 3 optional (`py -3` on Windows), each skill falling back to a by-hand procedure without it.

The operator's prompt ends with `Context:` and what the vault is for. Carry it into Step 4, where it pre-fills the interview's options rather than replacing the questions.

## 1. Check the folder

The session's working directory becomes the vault root. Look at it before writing anything:

- **Empty, or holding only files the operator just put there**: go on.
- **It already holds a `CLAUDE.md`**: this is an existing vault, not a new one. Stop, say so, and name `/para-upgrade` as the way to bring a vault up to date.
- **It holds anything else**: list what is there and ask whether this really is the folder for the new vault. A session started from a folder already in the Claude desktop sidebar opens *in that folder*, which is how a new vault ends up inside an old one.

## 2. Get the kit, outside the folder

Into `$PARAOS_HOME/para-os` (default `~/.paraos/para-os`), where it stays: the bootstrap offers add-ons from it and `/para-upgrade` reads it later. Where it is already there, `git -C ~/.paraos/para-os pull` instead.

```bash
git clone https://github.com/Vinedine/para-os.git ~/.paraos/para-os
```

Where git is not installed, download `https://github.com/Vinedine/para-os/archive/refs/heads/main.zip` and extract its `para-os-main/` folder to that path.

## 3. Copy the skeleton in

Copy everything inside the kit's `base/` folder into the vault root, **hidden items included**: the `.claude` folder (the `/para-*` skills, the rule files and the settings) and the `.gitignore` file. Check that `.claude/skills/para-daily-brief/SKILL.md`, `.gitignore` and `bootstrap-prompt.md` arrived.

Copy `base/` alone. Nothing else in the repository is vault content: an add-on is adopted later, by name, when the vault needs one, and the example vault is there to be read, not copied.

## 4. Run the bootstrap

Read `bootstrap-prompt.md` in the vault root and follow the block below its `---` line, start to finish. Its first action is one `AskUserQuestion` call with four short choice questions (the vault, its purpose, the answer language, a website to read). **Call it before writing any file, and write nothing until it returns.** The prompt's `Context:` only pre-fills the options, offered as the recommended ones; it never answers a question for the operator. From the answers it fills `CLAUDE.md` and `README.md`, creates `projects/vault-setup/` for the rest of onboarding, and deletes itself when it is done.

## 5. Hand over

Tell the operator the vault is ready and to run `/para-daily-brief`, and where the kit is. If that skill is not recognised in this session, open a new session in the same folder.

Say once where the skills live: bundled in the vault's own `.claude/skills/`. An operator who runs several vaults can move them to `~/.claude/skills/` instead, so one copy serves them all.

## Upgrading

Pull the kit (`git -C ~/.paraos/para-os pull`), then run `/para-upgrade` in the vault, giving it that path.

## Uninstalling

Delete the vault's `.claude/skills/para-*` folders and the rule files para-os put in `.claude/rules/` (`filing.md`, `figures.md`, and any an add-on added), and optionally `~/.paraos/`, which also holds every integration's state. The vault stays ordinary Markdown files.
