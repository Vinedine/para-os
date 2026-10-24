# para-os

**Run your work out of one structured place, with an AI assistant on top.**

para-os is a free, open kit for building a knowledge base of a business, a practice, a project or a household. It's a folder you copy, not a program you install.

The hard part of AI assistance isn't the assistant. It's that everything it needs is scattered across drives, inboxes and people's heads. Bring it into one structured place, connect your sources, and the questions that used to mean an afternoon of digging just get answered:

- "What's the full history with this client, across email and our files?"
- "What did we agree with the bank in March, and where's the document?"
- "Pull every order this supplier sent and flag what's still open."

If you can use email and a file explorer, you can run this.

## What you get

- **One obvious place for everything**, following [PARA](https://fortelabs.com/blog/para/), the filing method, hence the name, plus a triage inbox for whatever is not filed yet.
- **House rules** in plain language, in one file the assistant reads every session.
- **Skills for the recurring chores:** `/para-triage` empties the inbox, `/para-daily-brief` says what is due, `/para-new` starts a project or contact in the right place, `/para-pipeline` tracks anything that moves through stages ([all skills](docs/skills.md)).
- **Connections** to your mail, calendar and meeting notes ([how](docs/how-it-works.md#reaching-beyond-your-files)), **add-ons** for property and sales, and an **upgrade path** to each new release.

```
your-vault/
├── CLAUDE.md      # the house rules
├── README.md      # the master document
├── triage/        # the inbox
├── projects/      # time-bound work, one folder each
├── areas/         # ongoing responsibilities, contacts included
├── resources/     # reference, and ideas not yet started
└── archive/       # anything inactive
```

To see a lived-in vault first, open [`examples/belfoot-vault/`](examples/belfoot-vault/), a fictional consulting engagement.

## Quickstart

1. **Install [Git](https://git-scm.com/downloads) and [Python 3](https://www.python.org/downloads/)** if you don't have them, accepting the defaults. On a Mac, macOS offers both the first time they are needed.
2. **Make an empty folder and open it in the [Claude desktop app](https://claude.com/download).** In the **Code** tab, click **New**, keep **Local**, click **Select folder**. Not the `+` beside a folder already in the sidebar: that puts the new vault inside the old one.
3. **Paste this**, exactly as it is:

   ```text
   Set up a new para-os vault in this folder: read https://raw.githubusercontent.com/Vinedine/para-os/stable/INSTALL.md and follow it.
   ```

It downloads the kit, asks a few short questions, and ends by filing a few of your own papers and your current to-do list, so keep them at hand. Then come back with `/para-daily-brief`. The steps are in [`INSTALL.md`](INSTALL.md); other setups and the full requirements in [Getting started](docs/getting-started.md).

## What makes it different

- **Plain files on your own storage.** No app, no database, no lock-in: para-os adds no server of its own and never copies your vault anywhere ([data and privacy](docs/data-and-privacy.md)).
- **Any AI, Claude recommended today.** The Quickstart uses Claude (the AI itself needs a paid plan), but the structure is plain files any capable AI can read, and vaults built with it have run on Google Antigravity. When a better assistant appears, you point it at the same folders and keep everything.
- **Portable by rule.** Where an AI platform ships one of the kit's features built in, the kit uses it only if your knowledge stays in your own files and keeps working when you switch AI. Otherwise it keeps its own.
- **Free and open.** MIT-licensed, and kept up because the maintainer's own daily work runs on it.

> **Rather have it done for you?** para-os is the open method I work by: I set it up for a business, connect it and train the team, then take the work wherever the business needs to get working with AI. [trotstar.tech](https://trotstar.tech)

## More

- [Getting started](docs/getting-started.md): requirements, a terminal or VS Code, synced drives, version history.
- [How it works](docs/how-it-works.md), [skills](docs/skills.md), [add-ons](addons/README.md), [integrations](integrations/README.md), [several vaults](multi-vault/README.md).
- [Data and privacy](docs/data-and-privacy.md), [what the assistant may do on its own](docs/autonomy-tiers.md), and [reporting a vulnerability](SECURITY.md).
- [`RELEASES.md`](RELEASES.md): what each revision changes, and whether you need to act.
- Contributing: [`CLAUDE.md`](CLAUDE.md), [`tools/check.py`](tools/check.py), [`evals/`](evals/README.md).

## License

[MIT](LICENSE). Copy it, adapt it, build your own.
