# Your second vault

One person, two vaults, one mailbox: a private vault beside the one for your own company, say. Without this setup each vault's `/para-triage` reads the whole mailbox, and every mail lands in both.

1. **Register both vaults** in `${PARAOS_HOME:-~/.paraos}/vaults.json`, from [vaults.json.template](vaults.json.template). Each entry's `purpose` line says what belongs in that vault, in the words the mail itself uses ([registry.md](para-ingest/references/registry.md)).
2. **Say in each vault which mail is its own.** The mailbox's row under `## Triage sources` carries a `Relevant when` naming this vault's senders, domains or subjects. A sender one vault's contact cards know routes there on its own.
3. **Install `/para-ingest`** ([Installing](README.md#installing)). It reads the mailbox once and stages each mail in the vault it belongs to; each vault's `/para-triage` then stops reading the mailbox itself.
4. **Run it in preview for a week**, then in write mode, then on a schedule ([the preview week](README.md#the-preview-week)). With unattended triage, the [routine](auto-triage-routine.md) runs after it.

A mail that fits both vaults is staged in both. One that fits neither is staged nowhere and recorded as unrouted in the run log: most of a mailbox is no vault's business, but a rising unrouted count means a `Relevant when` needs widening.
