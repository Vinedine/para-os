# Security policy

para-os runs on your machine with your mail and files: its skills run shell commands, and its integration scripts hold tokens for your accounts. If you find a way to make it do something it should not, please report it privately rather than in a public issue.

## Reporting

Use GitHub's private vulnerability reporting: the **Report a vulnerability** button under this repository's **Security** tab. Only the maintainer sees the report.

In scope: the skills and rule files in `base/`, `addons/` and `multi-vault/`, the scripts they run, the integrations in `integrations/`, and the shipped `settings.json`. A model's own behaviour with no para-os file involved goes to its provider.

A useful report says:

- which file and revision (the `para-os-template` line in your vault's `CLAUDE.md`, or a commit);
- what an attacker controls (a mail, a document in `triage/`, a file in the vault) and what they get;
- the steps or the content that reproduce it, on a synthetic vault: never send real mail or client data.

## What to expect

A first reply within a week. A confirmed issue is fixed on `main`, released to `stable` as a hotfix when it is serious, and credited in `RELEASES.md` unless you ask otherwise. There is no bounty.
