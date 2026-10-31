# Autonomy tiers

What the agent may do on its own depends on where the change lands. Three tiers, from most to least freedom, and what can enforce each one. para-os states the tiers; it enforces none of them.

| Tier | The agent may | Undo, or enforcement, in a typical setup |
|---|---|---|
| **The vault's own files** | Edit, move and create, after the operator approves the proposal, item by item or by switching an action type on for unattended triage. Deletes are recoverable | Version history: a git repo, or a synced drive's file history. Unattended triage: its executor, which quarantines and keeps a kill switch, and the harness allowlist of a scheduled task |
| **A code repository** | Read and change files. Commit only where the operator's instructions allow it. Never push | A git `pre-push` hook that refuses, a permission rule in the agent harness that asks before `git push`, or [auto mode](#auto-mode), which blocks a force-push |
| **External systems** (mail, calendars, trackers, cloud accounts) | Read only | The connector's read-only mode, deny rules in the harness on every write tool the connector offers, or [auto mode](#auto-mode), which blocks sending data out |

## Why the tiers differ

The first tier has an undo, so the agent works freely inside it and version history catches a bad pass. The other two do not: a pushed commit reaches other people, and a sent mail or a changed ticket cannot be taken back. There the agent stops at a proposal and the operator acts.

## What para-os does not enforce

- **Every rule above is prose** the agent reads each session: the approval discipline and the delete rule in `para-shared/operating-discipline.md`, the commit rule beside them, and each skill's read-only contract. A model follows them reliably, but prose is not a lock.
- **Each skill pre-approves only the shell commands it runs**, one pattern each in its `allowed-tools` (`Bash(git mv *)`), so any other command asks first unless the operator's harness allows it.
- **para-os ships no hooks and one permission rule**, which denies the agent's file tools `~/.paraos/secrets/`, its own convention on every machine. Any other hook or deny rule belongs to the operator's own harness configuration, because it names the operator's own remotes and connectors.
- **Version history is the operator's to keep.** A vault on a folder with no history has no undo, and [the requirements](getting-started.md#requirements) ask for one for that reason.

A demo that needs a hard guarantee sets up the enforcement column before it starts.

## Auto mode

Claude Code's auto mode enforces much of this split by default: reads pass, edits inside the project folder pass because version control undoes them, and shell commands, web fetches and external tools go to a classifier with block rules for force-pushing, sending data out and scanning credential stores. Its authors report that it missed 17% of real overeager actions in a sample of 52, and that it does not replace careful review on high-stakes systems.

In an unattended run (scheduled triage, [the auto-triage routine](../multi-vault/auto-triage-routine.md)), a refused action goes back to the agent, and three refusals in a row or twenty in all end the run, so the run's report is where the operator sees one.
