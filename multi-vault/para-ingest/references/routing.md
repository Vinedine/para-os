# Routing (Step 4)

The only question: **which of its candidate vaults does this thread belong to?** Not what it means, not what to do about it, not how urgent it is. Those are `/para-triage`'s, in the vault the thread lands in, with the operator present.

A thread's candidates are the vaults that declared the mailbox it came from. Declaring is the consent: a vault opts out of a mailbox by deleting that row from its `## Triage sources` block. `route` has already applied rule 1, a counterparty's address found in one vault's contacts or lifecycle homes, so what reaches you is undecided or narrowed: `contacts` names the vaults each known address was found in, and `boards` a sender's domain a candidate's lifecycle homes hold. A board domain is evidence, never a decision on its own, and a free-mail domain is none.

## Judge subject and snippet

Against each candidate's `relevant_when` for that mailbox and its `purpose`, with the vault's root `README.md` `## Operating model` as the tiebreak on what its business actually is. Read the snippet, never the body; never read a vault's contents beyond `CLAUDE.md` and that README.

**The result is zero to many vaults.** Both ends are normal, and most threads route to none.

## When the evidence cannot separate two vaults, stage in both

Do not guess: a thread in two vaults costs one extra dismissal, one in the wrong vault costs the item. **A rising rate of those means a `Relevant when` rule to tighten, not a cleverer router.**

## Unrouted is a normal outcome

Most of a working mailbox is no vault's business: machine mail, newsletters, notifications, personal post in a work-scoped fleet. Decide it `routed: []`; the ledger then keeps it from being fetched again. A rising unrouted rate means real correspondence is falling through, and the fix is in the vaults' `Relevant when` rules.

## Record why, on every decision

One short phrase, never what to do: `rule: <vault> Relevant when`, `purpose: <vault>`, `contact: <address> (<vault>, <vault>); rule: <vault> Relevant when` for a shared contact settled by content, `unrouted: no candidate matched`.

## Never

- **Never route to a vault outside the thread's candidates**, however well the content fits; `stage.py` refuses it.
- **Never carry a judgment into the decision.** Whether the thread needs a reply or is urgent is triage's.
- **Never take an earlier routing of the same sender as evidence** for this thread.
