# Routing (Step 4)

The only question this skill answers: **which vaults does this thread belong to?** Not what it means, not what to do about it, not how urgent it is. Those are `/para-triage`'s, in the vault the thread lands in, with the operator present.

The candidate set for a thread is **the vaults that declared the mailbox it came from**, from the grouping in [gather.md](gather.md).

## Rules, in order

1. **A contact hit decides, on a counterparty and never on the mailbox owner.** If any participant's address appears in a candidate vault, route there.

   **Skip the owner's own addresses before anything else.** The owner is the mailbox's own address plus any other addresses the source declares for them (a `fetch-script` marks these per record; for a connector it is the endpoint address).

   Grep each candidate vault for each remaining address. **A hit in one vault decides. Hits in several narrow the choice without deciding it:** a participant known to just one of those vaults settles it for that vault; otherwise apply rule 2 among those vaults only, and route to all of them only when subject and snippet cannot separate them. **Where to grep:**

   - **`areas/network/` and `resources/mds/`, both, always**, since a vault on the [read-only iPad delivery](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery) keeps its contact files collected there.
   - **Take a hit in a contact file or in an entity's own document under those roots**, such as the README of the entity an address concerns.
   - **Never take a hit in a staged triage note or a source document**: nothing in `triage/`, no `resources/mds/triage__*`, nothing under a `sources/` folder or its `resources/mds/*__sources__*` form. A staged note carries every participant of the thread it came from; a source document names people who are not the vault's correspondents.
   - **Do not count a match inside a PDF**, which `grep` finds only sometimes.
2. **Otherwise judge subject and snippet** against each candidate vault's `Relevant when` text and its `purpose` from the registry, with the `## Operating model` as the tiebreak on what the vault's business actually is. Read the snippet, not the body.
3. **The result is zero to many vaults.** Not one. Both ends are normal, and most threads route to none.

## When the evidence cannot separate two vaults, stage in both

Do not guess. A thread in two vaults costs the operator one extra dismissal; a thread in the wrong single vault costs them the item.

The same holds for a genuinely ambiguous thread with no clear winner: route to every vault that plausibly fits, and let the count of those show up in the run log. **A rising rate of multi-routed threads is a signal to tighten the `Relevant when` rules, not to make the router cleverer.**

## Unrouted is a normal outcome

Most of a working mailbox is not any vault's business: machine mail, newsletters, notifications, personal post in a work-scoped fleet. Ledger it as unrouted so it is not refetched, stage nothing. A rising unrouted rate means real correspondence is falling through, and the fix is in the vaults' `Relevant when` rules rather than here.

## Record why, on every decision

Every routed thread carries its reason into the staged note and the ledger; every unrouted one carries its reason into the ledger. One short phrase is enough: `contact: <address>`, `contact: <address> (<vault>, <vault>); rule: <vault> Relevant when` for a shared contact settled by content, `rule: <vault> Relevant when`, `purpose: <vault>`, `unrouted: no candidate matched`.

## Never

- **Never route to a vault outside the candidate set**, however well the content fits. Declaring the mailbox is the consent.
- **Never route on the recipient address alone.** A mailbox declared by six vaults says nothing about which one a given thread belongs to.
- **Never carry a judgment into the routing decision.** Whether the thread needs a reply, whether the ball is in the operator's court, whether it is urgent: all of it is triage's.
- **Never let routing read a vault's contents beyond its contact roots (`areas/network/` and `resources/mds/`), `CLAUDE.md` and the root `README.md`.**
