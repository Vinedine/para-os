# Getting started

> **You need** the [Claude desktop app](https://claude.com/download), [Git](https://git-scm.com/downloads) and [Python 3](https://www.python.org/downloads/), on Windows or macOS.

## Quickstart

**1. Install Git and Python 3** if you don't have them. On Windows, download Git from [git-scm.com](https://git-scm.com/downloads/win) and Python from [python.org](https://www.python.org/downloads/), accepting the defaults; on a Mac, macOS offers to install both the first time they are needed. The setup uses Git to fetch para-os and your vault uses it to keep its history; the skills use Python to read the vault.

**2. Make an empty folder** for the vault, wherever you keep your files (your cloud drive is fine), and not inside an existing vault.

**3. Open it in the Claude desktop app.** In the **Code** tab, click **New** at the top of the sidebar, keep **Local**, click **Select folder** and pick the folder. Don't use the `+` beside a folder already in the sidebar: that opens the session inside *that* folder, which is how a new vault ends up inside an old one.

**4. Paste this**, exactly as it is:

```text
Set up a new para-os vault in this folder: read https://raw.githubusercontent.com/Vinedine/para-os/stable/INSTALL.md and follow it.
```

It downloads the kit, copies [`base/`](../base/) in, and runs the bootstrap interview: a few short questions about the vault, then it fills `CLAUDE.md` and `README.md` and creates a self-retiring `vault-setup` project that walks you through the rest. It ends by filing a few of your own papers and your current to-do list, so keep them at hand. The steps are in [`INSTALL.md`](../INSTALL.md): read what it will do before you paste it, or follow it by hand.

**5. Come back with `/para-daily-brief`.** The vault answers from day one, and better once you run the short brainstorm the `vault-setup` project starts with.

To see a lived-in vault first, open [`examples/belfoot-vault/`](../examples/belfoot-vault/), a fictional consulting engagement; [`examples/`](../examples/README.md) says how to run the skills against it.

## Requirements

Beyond the list at the top:

- **Claude Code in a terminal** works the same as the desktop app: start it in the empty folder and paste the same line. Linux has no desktop app, so this is the route there.
- **Python 3.9 or later** does not come with Claude Code. Every skill that reads the vault hands its mechanical half to a script beside it, and stops, saying so, where Python is missing. On Windows the skills call `py -3`, since a bare `python` is often a Microsoft Store stub. `/para-upgrade` and `/para-audit` also need a local clone of this repository.
- **Account skills come along:** Claude Code syncs the skills and plugins enabled on your claude.ai account into sessions (the document skills are what a vault needs for the files it receives); `syncClaudeAiSkills: false` and `syncClaudeAiPlugins: false` in your settings keep a vault to its own.
- **Real, readable files.** On a synced drive (OneDrive/iCloud/Drive), set the vault to *always keep on this device* so on-demand sync doesn't hand the agent a placeholder stub instead of the file. Keep files in open formats (Markdown, PDF, CSV, readable Office files); convert cloud-native stubs (Google Docs/Sheets) and closed proprietary formats first.
- **Storage that can undo.** Keep the vault in a git repo or on a drive with version history (OneDrive, Google Drive, Dropbox all qualify). The skills edit many files in one pass, and version history is the only thing that makes a bad pass reversible. A vault on a synced drive keeps no `.git`, which the drive can corrupt, and takes its git history from [`vault-mirror`](../integrations/vault-mirror/), a repository kept outside the drive. What the agent may change on its own, and what enforces it, is in [the autonomy tiers](autonomy-tiers.md).

## You don't need to be a programmer

You work in one free app: the [Claude desktop app](https://claude.com/download), which runs [Claude Code](https://claude.com/claude-code), Anthropic's AI assistant, in its Code tab (the AI itself needs a paid Claude plan). Point it at your vault folder and you get your files on one side and a chat box on the other. You type plain English; the assistant handles the files. Those files are **Markdown** (the `.md` ending): plain text with a few simple marks, readable on any device. If you can use email and a file explorer, you can run this.

If you already live in a code editor, [VS Code](https://code.visualstudio.com/) runs the same assistant over the same folders, and it's the better window when you're working on code as well as documents. It's the power-user path, not the starting point: the desktop app is a nicer place to work for everyone else, which is most people.
