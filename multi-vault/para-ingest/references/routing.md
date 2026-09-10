# Routing (Step 4)

The only question this skill answers: **which vaults does this thread belong to?** Not what it means, not what to do about it, not how urgent it is. Those are `/para-triage`'s, in the vault the thread lands in, with the operator present.

The candidate set for a thread is **the vaults that declared the mailbox it came from**, from the grouping in [gather.md](gather.md). A vault that never declared a mailbox is not expecting post from it, and routing one there on a keyword match would put mail in front of someone who asked not to see it.

## Rules, in order

1. **A contact hit decides, on a counterparty and never on the mailbox owner.** If the sender's address appears in a candidate vault, route there.

   **Skip the owner's own addresses before anything else.** Every message in a mailbox is to or from the person who owns it, and their address is in the contact files of every vault they work in, so a rule matching on contact identity matches *the entire mailbox* unless it knows to step over them. It is not a rare edge: measured on a real personal inbox, **126 of 220 contact hits were the owner writing**, and one vault's every single hit was that. The owner is the mailbox's own address plus any other addresses the source declares for them (a `fetch-script` marks these per record; for a connector it is the endpoint address). This is the oldest known trap in filtering a personal mailbox and it is invisible when it fires, because the run looks productive.

   Past that, contacts are the strongest signal a vault owns a correspondent, and they are cheap to check: one grep for the address per candidate vault. If the address hits in more than one, route to all of them, since two vaults genuinely both know this person. **Where to grep, and it is not only `areas/network/`:**

   - **`areas/network/` and `resources/mds/`, both, always.** A read-only-flavor vault runs a flip pipeline that moves every `.md` out of the browsable tree into `resources/mds/` under flattened names (`areas__network__someone.md`) and leaves rendered PDFs behind in `areas/network/`. Grepping only the obvious folder finds nothing at all in such a vault, and finds it silently: the run reports clean routing while the strongest rule never fired once.
   - **Take a hit anywhere under those two roots, not only in a contact file.** An address often lives in the README of the entity it concerns rather than in a card of its own, and that is a *better* signal, not a worse one, because it names the thing the correspondence is about.
   - **Do not count a match inside a PDF.** `grep` will sometimes find an address in a PDF's uncompressed byte stream and sometimes not, for reasons that have nothing to do with whether the vault knows the person. A rule that fires on luck is worse than one that does not fire, because it looks like it is working.
2. **Otherwise judge subject and snippet** against each candidate vault's `Relevant when` text and its `purpose` from the registry, with the `## Operating model` as the tiebreak on what the vault's business actually is. Read the snippet, not the body: routing is a coarse decision and does not earn a full fetch.
3. **The result is zero to many vaults.** Not one. Both ends are normal, and most threads route to none.

## When two vaults both fit, stage in both

Do not pick. A thread in two vaults costs the operator one extra dismissal in one of them; a thread in the wrong single vault costs them the item. The asymmetry is the whole reason this skill stages rather than files.

The same holds for a genuinely ambiguous thread with no clear winner: route to every vault that plausibly fits, and let the count of those show up in the run log. **A rising rate of multi-routed threads is a signal to tighten the `Relevant when` rules, not to make the router cleverer.**

## Unrouted is a normal outcome

Most of a working mailbox is not any vault's business. Machine mail, newsletters, notifications, personal post in a work-scoped fleet: none of it routes. Ledger it as unrouted so it is not refetched, stage nothing.

What matters is the *trend*. A stable unrouted rate is a mailbox behaving normally. A rising one means real correspondence is falling through, and the fix is in the vaults' `Relevant when` rules rather than here.

## Record why, on every decision

Every routed thread carries its reason into the staged note and the ledger; every unrouted one carries its reason into the ledger. One short phrase is enough: `contact: <address>`, `rule: <vault> Relevant when`, `purpose: <vault>`, `unrouted: no candidate matched`.

This is not bookkeeping. It is what makes the preview week reviewable: a run log of decisions with no reasons attached can only be checked by re-deriving every one of them, which nobody does, so the router goes unverified and gets trusted anyway.

## Never

- **Never route to a vault outside the candidate set**, however well the content fits. Declaring the mailbox is the consent.
- **Never route on the recipient address alone.** A mailbox declared by six vaults says nothing about which one a given thread belongs to; that is precisely the judgment being made here.
- **Never carry a judgment into the routing decision.** Whether the thread needs a reply, whether the ball is in the operator's court, whether it is urgent: all of it is triage's, and a router that starts weighing it will start dropping things that are merely quiet.
- **Never let routing read a vault's contents beyond its contact roots (`areas/network/` and `resources/mds/`), `CLAUDE.md` and the root `README.md`.** Those answer the question. Anything more is one vault's content reaching a decision about another's, which is the wall this layer exists to keep standing.
