# Installing a para-os vault

The steps an agent follows when an operator pastes the Quickstart prompt from [README.md](README.md#quickstart) into a Claude Code session: set up a new vault in the session's folder from this repository, then hand over to the bootstrap interview. A person can follow them by hand too.

**Needs:** Claude Code and git, which the README's Quickstart has the operator install first (the zip below is a fallback only, since `/para-upgrade` needs the clone); Python 3 optional (`py -3` on Windows), each skill falling back to a by-hand procedure without it.

The operator's prompt says nothing about the vault itself: Step 4's questions ask for it.

## 1. Check the folder

The session's working directory becomes the vault root. Look at it before writing anything:

- **Empty, or holding only files the operator just put there**: go on.
- **It already holds a `CLAUDE.md`**: this is an existing vault, not a new one. Stop, say so, and name `/para-upgrade` as the way to bring a vault up to date.
- **It holds anything else**: list what is there and ask whether this really is the folder for the new vault. A session started from a folder already in the Claude desktop sidebar opens *in that folder*.

## 2. Get the kit, outside the folder

Into `$PARAOS_HOME/para-os` (default `~/.paraos/para-os`), where it stays: the bootstrap offers add-ons from it and `/para-upgrade` reads it later. The kit's `stable` branch is what users get.

```bash
git clone --branch stable https://github.com/Vinedine/para-os.git ~/.paraos/para-os
```

Where it is already there, `git -C ~/.paraos/para-os pull` instead. A clone not on `stable` (`git -C ~/.paraos/para-os branch --show-current`) switches once first: `git -C ~/.paraos/para-os fetch origin`, then `git -C ~/.paraos/para-os checkout stable`.

Where git is not installed, download `https://github.com/Vinedine/para-os/archive/refs/heads/stable.zip` and extract its `para-os-stable/` folder to that path.

## 3. Copy the skeleton in

Copy everything inside the kit's `base/` folder into the vault root, **hidden items included**: the `.claude` folder (the `/para-*` skills, the rule files and the settings) and the `.gitignore` file. Leave out any `__pycache__` and `.pytest_cache` folders. Check that `.claude/skills/para-daily-brief/SKILL.md`, `.gitignore` and `bootstrap-prompt.md` arrived.

Copy `base/` alone. Nothing else in the repository is vault content: an add-on is adopted later, by name, when the vault needs one, and the example vault is there to be read, not copied.

## 4. Run the bootstrap

Read `bootstrap-prompt.md` in the vault root and follow the block below its `---` line, start to finish. Its first action is one `AskUserQuestion` call of three short choice questions (the vault's name, its purpose, the answer language), then two open ones as a short message (what it covers, a website to read). **Ask them before writing any file, and write nothing until the answers are in.** From the answers it fills `CLAUDE.md` and `README.md`, creates `projects/vault-setup/` for the rest of onboarding, and deletes itself when it is done.

## 5. Hand over

The bootstrap's [Finish](base/bootstrap-prompt.md#finish) ends on the operator's own material, filed, and a first `/para-daily-brief`. Tell them where the kit is, and that the brief is how to come back in. If a skill is not recognised when they type it, open a new session in the same folder.

Say once where the skills live: bundled in the vault's own `.claude/skills/`. An operator who runs several vaults can move them to `~/.claude/skills/` instead, so one copy serves them all.

## Upgrading

Pull the kit (`git -C ~/.paraos/para-os pull`, after the one-time switch to `stable` in [step 2](#2-get-the-kit-outside-the-folder) where the clone is not on it), then run `/para-upgrade` in the vault, giving it that path. [RELEASES.md](RELEASES.md) says what each revision changes and whether you need to do anything first.

## Uninstalling

Delete the vault's `.claude/skills/para-*` folders and the rule files para-os put in `.claude/rules/` (`filing.md`, `figures.md`, `working-preferences.md` (copy its preferences out first if you want to keep them), and any an add-on added), and optionally `~/.paraos/`, which also holds every integration's state. The vault stays ordinary Markdown files.
