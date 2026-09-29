# Autonomy tiers

What the agent may do on its own depends on where the change lands. Three tiers, from most to least freedom, and what can enforce each one. para-os states the tiers; it enforces none of them.

| Tier | The agent may | Undo, or enforcement, in a typical setup |
|---|---|---|
| **The vault's own files** | Edit, move and create, after the operator approves the proposal. Deletes are recoverable and approved one file at a time | Version history: a git repo, or a synced drive's file history |
| **A code repository** | Read and change files. Commit only where the operator's instructions allow it. Never push | A git `pre-push` hook that refuses, or a permission rule in the agent harness that asks before `git push` |
| **External systems** (mail, calendars, trackers, cloud accounts) | Read only | The connector's read-only mode, or deny rules in the harness on every write tool the connector offers |

## Why the tiers differ

The first tier has an undo, so the agent works freely inside it and version history catches a bad pass. The other two do not: a pushed commit reaches other people, and a sent mail or a changed ticket cannot be taken back. There the agent stops at a proposal and the operator acts.

## What para-os does not enforce

- **Every rule above is prose** the agent reads each session: the approval discipline and the delete rule in `para-shared/operating-discipline.md`, the commit rule beside them, and each skill's read-only contract. A model follows them reliably, but prose is not a lock.
- **para-os ships no hooks and no permission rules.** Its only shipped setting turns off auto-memory. A hook or a deny rule belongs to the operator's own harness configuration, because it names the operator's own remotes and connectors.
- **Version history is the operator's to keep.** A vault on a folder with no history has no undo, and [the requirements](../README.md#requirements) ask for one for that reason.

A demo that needs a hard guarantee sets up the enforcement column before it starts.
