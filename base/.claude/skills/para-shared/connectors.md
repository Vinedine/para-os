# Connector sources

A live mailbox read, read-only. **Never writes to a mailbox** - no send, no reply, no archive, no label.

Most mailboxes are read over MCP. One kind is not: a mailbox with no connector at all, reached by a script that fetches and prints candidates instead. It is the same protocol either way, because the script is doing the reading and nothing else - it does not decide relevance, and it writes no file. A `fetch-script` row is a mailbox, not a sync source, and the difference is what the caller must not get wrong: a sync source writes into `triage/` unjudged, while this one is judged first like any other mail.

This file is the **fetch protocol**, shared by every skill that reads a mailbox declared in a vault's `## Triage sources` block. It ends with a deduped set of candidate threads and stops there. Judging what a thread *means* is the caller's job and differs between callers, so it is deliberately not here.

**Dispatch by the `Type` value:**

| Type in manifest | Search tool | Content tool | Granularity |
|---|---|---|---|
| `connector: claude_ai_Gmail` | `search_threads` | `get_thread` | threads (native) |
| `connector: google-workspace` | `search_gmail_messages` (pass the Endpoint as `user_google_email`) | `get_gmail_messages_content_batch` | messages - **must group by `threadId`** |
| `fetch-script` | the script's `fetch` subcommand, run from the vault root | the `preview` field it already returns | **threads (the script groups)** - one record is one conversation, carrying `message_count`, `messages` and `participants` |

**Match on the tool suffix, not the full name.** The `<server>` half of `mcp__<server>__<tool>` is not stable across clients: the same connector may appear as `mcp__claude_ai_Gmail__*` or under an opaque UUID. If schemas are deferred, search for the suffix to load them. Only when that search comes back empty is the connector genuinely absent: skip the source, note it in the summary ("`<source>` declared but not connected - skipped"), and do not fail the run.

**Per connector source:**

1. **Build the query** from the `Relevant when` text plus a standard frame: `in:inbox -category:promotions -category:social newer_than:30d`. Add the sender/subject operators the filter implies. **Do not exclude machine senders by default.** `-category:updates`, and patterns like `-from:noreply -from:no-reply -from:donotreply -from:notification`, read as free noise reduction and are not: the transactional mail a vault most wants - a domain or DNS action-required notice, a government or tax filing alert, an invoice, a payment receipt, a booking confirmation - is nearly always sent from a `noreply@` address and categorised as an update. Excluding them drops precisely the mail the vault exists to catch, and drops it invisibly: the run reports a clean pass over a window it never really read. Narrow only for a specific mailbox that is measurably mostly bot mail, prefer naming that application's own domain over a blanket `noreply` pattern, and say in the report which exclusion you applied, so the narrowing stays visible to whoever reads the run.
2. **Operators only pre-filter; the judgment is the real gate.** Sender exclusions never catch everything - a variant address (`donotreply@`, `notification@`) or a *human* reply on an automated thread will slip through. Treat the query as a cheap first cut, and let the caller's judgment step drop what survives it wrongly.
3. **Search, then normalize to threads.** Gmail returns threads already, and a `fetch-script` now groups before it prints. Workspace returns individual messages - group results by `threadId` so one conversation is one candidate, not N. Fetch metadata (subject, from, date, and the RFC822 `Message-ID`) for the shortlist.

   When grouping Workspace messages, report how many messages became how many threads. Two numbers that are always equal on a busy mailbox indicate grouping is not running.
4. **Page until the window is exhausted, and say so if you stop early.** A search returns one page, and a busy mailbox has several. Taking page one for the whole window is a **silent truncation**: it looks exactly like a quiet month, and the messages it drops are the oldest in the window, which are the ones most likely to have gone unanswered. Follow the next-page token until there is none. If you stop at a page cap instead, that cap is a finding to report in as many words (`<mailbox>: stopped at N pages, window not fully covered`), never a footnote and never omitted.
5. **Dedup against the caller's ledger, on a watermark rather than on the thread.** Drop a thread the caller has already dispositioned **through its newest message**, not one it has dispositioned at all. Which ledger that is, and what a disposition means in it, belongs to the caller: `/para-triage` uses the per-vault seen-ledger in [../para-triage/references/sources.md](../para-triage/references/sources.md), `/para-ingest` uses its own central one. What every one of them must carry is the same pair: **`seen_through`**, the dedup key (step 6) of the newest message at the moment of disposition, and **`seen_date`**, that message's received timestamp. **Both, every time.** An entry carrying `routed`, `reason` and a date but no pair looks like a working ledger and behaves like a thread-keyed one, which is precisely the failure this step exists to prevent.

   **A mail thread is not a fixed object: keying a ledger on thread ID alone turns one disposition into a permanent dismissal.** When later replies arrive on an already-handled thread, a thread-keyed ledger drops them before the caller ever evaluates them.

   **The cut here is cheap and approximate, and step 6 settles it.** A search returns a date reliably and the newest message's `Message-ID` only sometimes, so drop a ledgered thread at this step only when the newest date the search gave is no later than `seen_date`, and carry everything else forward. Same shape as the query frame in steps 1 and 2: a first cut, with the exact check downstream. Erring toward carrying a thread forward costs one comparison in step 6; erring the other way drops new replies.

   **`seen_date` is an instant, so write it and read it as one.** A full ISO-8601 timestamp carrying its UTC offset (`2026-09-10T01:39:13+02:00`), parsed to an instant on both sides before comparing. Never compare watermarks as strings, and never fall back to comparing whole days.

   **Entries lacking `seen_through`, or carrying a day-granularity `seen_date`:** read the watermark as the *start* of that day and let anything later resurface. An entry written this way is a legacy entry, not a valid one: the caller rewrites it with a real pair the next time it dispositions that thread.

   **Read the ledger as UTF-8, whichever one it is.** Every ledger in this protocol stores subjects, so a Dutch or French one, or an emoji, is normal rather than exceptional, and they are written with `ensure_ascii=False`. Python on Windows defaults to cp1252 and raises `UnicodeDecodeError` on exactly those entries, so pass `encoding="utf-8"` on every read. A ledger that fails to load and is caught rather than raised dedups against nothing: every thread in it resurfaces as new, and the run reports that as a busy mailbox.
6. **Get the true message list before judging.** For every `claude_ai_Gmail` thread that survives dedup, call `get_thread` with `messageFormat: METADATA_ONLY` (cheap - IDs, senders, dates, labels, no bodies). Search results may be truncated, so a thread that looks short may not be. Workspace threads need no such call.

   **Then settle the watermark against that list.** For a thread carrying a ledger entry, compare its newest message's dedup key against `seen_through`. Equal means step 5's date cut was a false positive, and the thread is dropped here instead. Different means the thread grew after it was dispositioned, and it goes to the caller as a **resurfaced** thread, carrying its earlier disposition and reason plus the messages that arrived after the watermark.

   **The dedup key, in this order and never in another.** An unstated fallback drifts into several derivations at once, which is how an identifier stops identifying anything:

   1. The RFC822 `Message-ID` header, verbatim including its angle brackets.
   2. Failing that, a **content key**: `content:` plus the first 16 characters of `sha1("<normalised subject>|<sender address, lowercased>|<received time truncated to the minute, in UTC>")`, normalising the subject by stripping any leading run of `Re:`, `Fwd:`, `RE:`, `FW:` and collapsing whitespace.
   3. Failing even that, `provider:<mailbox>:<provider message id>`.

   **Rung 2 exists because rung 3 is per-mailbox and rung 1 is not always offered.** Say in the report whenever rung 3 was used, because that is the rung where cross-mailbox dedup is off.

**Where this ends.** Step 6 hands back a deduped candidate set with a true message list, each thread flagged new or resurfaced. Neither the query frame nor the dedup decides whether a thread matters - that is the caller's, and the two callers ask different questions of the same set: `/para-triage` asks what to *do* about a thread, `/para-ingest` asks only which vault it belongs to. A caller that finds itself needing to change something in this file for its own question is almost certainly writing a rule that belongs in its own reference instead.
