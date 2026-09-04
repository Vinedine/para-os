#!/usr/bin/env python3
# para-os-integration: outlook 2026.09.01 - see CHANGELOG.md; /para-upgrade reports drift against this line.
"""Read Outlook.com / Hotmail / Microsoft 365 mailboxes via Microsoft Graph, filter for
vault-relevant mail, and drop matches into the vault's triage/ folder.

Microsoft accounts no longer accept Basic Auth or app passwords: the ONLY way in is
OAuth2. This script uses the OAuth2 device-code flow against an Entra app registration
(delegated Graph Mail.Read), with no client secret (public client). Read-only: it never
sends, deletes, or marks mail read (a Graph GET does not change is-read state).

One app cannot serve every mailbox. A personal-accounts app is registered against the
"consumers" authority, which refuses work/school accounts outright, so a Microsoft 365
mailbox needs its own registration in its own tenant. Both the app and the authority
therefore resolve PER ACCOUNT, falling back to the machine-wide pair (see account_app).

Per-vault copy, shared state (the granola pattern): this script is COPIED into each
vault it serves and syncs ONLY the vault it lives in, auto-detected from its own path.
One mailbox can still feed many vaults: each vault's own config lists the accounts
that feed it. All copies share one secret file and one dedup ledger; the ledger tracks
per-vault filing, so the same message can land in several vaults but never twice in
the same one.

Config is split by what it is:

  SECRETS - machine-global, ~/.paraos/secrets/outlook.json (outside the vault on
  purpose: a secret inside it leaks when the vault syncs). Credentials only, nothing vault-specific. Rewritten every run because MSA
  rotates the refresh token on each refresh. "self" lists the owner's other addresses
  (see is_relevant).
    {
      "client_id": "00000000-0000-...",       # default Entra app (client) id
      "authority": "consumers",               # default: "consumers", "common", or a tenant id
      "accounts": {
        "someone@hotmail.com": { "refresh_token": "...", "self": ["someone@icloud.com"] },

        # A work/school mailbox overrides both, pointing at its own tenant's app.
        # Seed them at login:  outlook.py login someone@company.com \
        #                        --client-id <app> --authority <tenant-id>
        "someone@company.com": { "refresh_token": "...",
                                 "client_id": "11111111-1111-...",
                                 "authority": "22222222-2222-..." }
      }
    }

  VAULT CONFIG - this vault's resources/scripts/outlook.config.json, next to this copy,
  version-controlled with the vault. Which mailboxes feed THIS vault plus their filters;
  edit it freely in a vault session, no secret ever lives here. NOT named outlook.json:
  that is the machine-global secret above, and two files sharing one name across opposite
  trust zones is how a credential ends up inside a synced vault.
    { "accounts": ["someone@hotmail.com"], "keywords": ["invoice", "contract"] }

  One list per vault only works while every mailbox feeding it has the same shape. Give
  `accounts` an object instead to filter per mailbox, each key falling back independently
  to the vault-level default (see account_filter):
    {
      "keywords": ["invoice", "contract"],      # vault-level default
      "accounts": {
        # A dedicated mailbox IS the filter - take everything, keywords only subtract.
        "engagement@company.com": { "match_all": true },
        # A shared funnel needs its own tight list; four figures a week otherwise.
        "info@company.com": { "keywords": ["offerte", "bestelling"] }
      }
    }

  Four filter settings, vault-level or per account:
    keywords    - matched case-insensitively (see match_body for where).
    match_all   - take every message. The explicit catch-all, because EMPTYING keywords
                  does the opposite: it leaves the contact allowlist as the only gate,
                  which is stricter, not looser. Default false.
    match_body  - match keywords against bodyPreview as well as the subject. Default
                  TRUE: subject-only matching silently drops any message whose subject is
                  in a language the filter wasn't written in, and a dropped message leaves
                  no trace. Set false for subject-only, accepting that blind spot, for
                  EVERY keyword on that account.
    subject_only_keywords - the same trade, scoped to specific keywords instead of the
                  whole account: a keyword that is also a street name doubling as someone's
                  home/delivery address (a Stationsstraat tenant's parcel, a Kerkstraat
                  resident's takeout order) will keep matching shipping and marketing
                  bodies that happen to print the address, forever, with match_body left on.
                  List such a keyword here and it is checked against the subject only, while
                  every other keyword on the same account keeps matching subject AND body.
                  Case-insensitive, same as keywords; a keyword listed here that isn't also
                  in keywords is inert.

  FILTERING reads bodyPreview, which Graph caps at 255 characters. FILING does not: the
  triage file gets the message's full body, fetched per message by fetch_body. Keep the two
  apart. A record written from the preview stops mid-sentence with no ellipsis and no marker,
  under a header that still reads as complete, so nothing in the file tells its reader it is
  partial. Records written from 2026.09.01 on say so on their own `- **Body:**` line; an
  older one cannot be told from a complete record without opening the mail.

  A drafted filter is a hypothesis until it has run against real traffic. Run `sync`
  without --write against a real window before trusting one, and prefer distinguishing
  words: a company's own name matches almost everything in that company's mailbox, so it
  is noise dressed as precision.

Per vault, the sender allowlist is NOT stored anywhere: it is rebuilt from
<vault>/areas/network/*.md on every run, so adding a contact automatically widens what
gets through.

`sync` is one of five subcommands, and the filter above shapes ONLY what `sync` files
unasked. `search` deliberately ignores it and queries the whole mailbox: the point of a
search is to ask a question the filter would not have surfaced.

Usage (on Windows, `py` works in place of `python3`):
  python3 outlook.py accounts                   # login state + which accounts feed this vault
  python3 outlook.py login someone@outlook.com  # one-time device-code login (machine-global)
  python3 outlook.py sync                       # dry run: what WOULD be filed into THIS vault
  python3 outlook.py sync --write               # actually write matches into this vault's triage/
  python3 outlook.py sync --account someone@hotmail.com --days 14 --write
  python3 outlook.py search "contract renewal"  # search the mailboxes feeding this vault
  python3 outlook.py raw '/me/messages?$top=1'  # any Graph path, prints JSON (debug)
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

try:                                                     # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent            # <vault>/resources/scripts
VAULT_ROOT = SCRIPT_DIR.parents[1]                      # the vault this copy serves (auto-detected)
VAULT = VAULT_ROOT.name

PARAOS_HOME = Path(os.environ.get("PARAOS_HOME") or Path.home() / ".paraos")  # outside the vault on purpose
CONFIG_FILE = PARAOS_HOME / "secrets" / "outlook.json"      # credentials only, machine-global
VAULT_CONFIG = SCRIPT_DIR / "outlook.config.json"           # this vault's accounts + filters
LEGACY_VAULT_CONFIG = SCRIPT_DIR / "outlook_sync.json"      # the superseded name, still read
LEDGER_FILE = PARAOS_HOME / "cache" / "outlook" / "synced.json"

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = "https://graph.microsoft.com/Mail.Read offline_access"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


# --- config + ledger -------------------------------------------------------------------

def _load_json(path):
    """Parse a JSON file, or exit cleanly rather than let a malformed one surface as a raw
    traceback - the same clean-failure bar this file already holds for a missing one."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"{path} is not valid JSON ({e}). Fix it or delete it and re-run.")


def load_config():
    if not CONFIG_FILE.exists():
        sys.exit(f"No config at {CONFIG_FILE}. Create it with at least: "
                 '{"client_id": "...", "accounts": {}}')
    return _load_json(CONFIG_FILE)


def load_vault_config(required=True):
    """This vault's own accounts + filters, next to this script copy. Never secret.

    Reads the legacy `outlook_sync.json` name when the current one is absent, and says so.
    The script and its config were renamed together, so a copy updated without its config
    would otherwise start up looking correctly configured and quietly file nothing.
    """
    if VAULT_CONFIG.exists():
        return _load_json(VAULT_CONFIG)
    if LEGACY_VAULT_CONFIG.exists():
        print(f"! reading {LEGACY_VAULT_CONFIG.name}, the superseded config name. "
              f"Rename it to {VAULT_CONFIG.name} - the old name will stop being read "
              f"in a future revision.", file=sys.stderr)
        return _load_json(LEGACY_VAULT_CONFIG)
    if not required:
        return {}
    sys.exit(f"No vault config at {VAULT_CONFIG}. Create it with: "
             '{"accounts": ["someone@hotmail.com"], "keywords": []}')


def write_json_atomic(path, data):
    """Write via temp file + replace. These files are shared by every vault's copy of this
    script; a truncating write that dies half way takes every account's token with it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def save_account(cfg, email, **fields):
    """Persist fields on ONE account, re-reading first so a concurrent run's write survives.

    Two vault copies can refresh different accounts at the same moment, and a device-code
    login holds the file open for minutes. Writing our whole in-memory cfg back would undo
    the other's rotation, and the superseded token is dead: that account would need a full
    device-code re-login. So every write to this file goes through here, never wholesale.
    """
    on_disk = _load_json(CONFIG_FILE) if CONFIG_FILE.exists() else cfg
    on_disk.setdefault("accounts", {}).setdefault(email, {}).update(fields)
    write_json_atomic(CONFIG_FILE, on_disk)


def load_ledger():
    if LEDGER_FILE.exists():
        return json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
    return {}


def save_ledger(ledger):
    write_json_atomic(LEDGER_FILE, ledger)


def account_app(cfg, email):
    """The Entra app and authority serving ONE mailbox, as (client_id, authority).

    Both fall back to the machine-wide pair, so every personal-only config keeps working
    untouched. They resolve independently: a work mailbox on a shared multi-tenant app needs
    only the authority switched, and coupling them would quietly send it at the wrong app.

    Resolved before the account exists in the file, because `login` needs it on first run.
    """
    acct = (cfg.get("accounts") or {}).get(email) or {}
    client_id = acct.get("client_id") or cfg.get("client_id")
    authority = acct.get("authority") or cfg.get("authority", "consumers")
    if not client_id:
        sys.exit(f"No client_id for {email}. Set one on the account, or machine-wide "
                 f"at the top of {CONFIG_FILE}.")
    return client_id, authority


def token_url(authority):
    return f"https://login.microsoftonline.com/{authority}/oauth2/v2.0"


# --- OAuth2 device-code flow -----------------------------------------------------------

def device_login(cfg, email):
    """Interactive: user opens a URL, types a code, consents once. Returns a refresh token."""
    client_id, authority = account_app(cfg, email)
    base = token_url(authority)
    r = requests.post(f"{base}/devicecode",
                      data={"client_id": client_id, "scope": SCOPE}, timeout=30)
    r.raise_for_status()
    dc = r.json()
    print(f"\n  To sign in as {email}:")
    print(f"  1. open  {dc['verification_uri']}")
    print(f"  2. enter code  {dc['user_code']}")
    print(f"  3. sign in with {email} and approve.\n  Waiting...", flush=True)

    interval = dc.get("interval", 5)
    deadline = time.monotonic() + dc.get("expires_in", 900)
    while time.monotonic() < deadline:
        time.sleep(interval)
        p = requests.post(f"{base}/token", data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": client_id,
            "device_code": dc["device_code"],
        }, timeout=30)
        body = p.json()
        if p.status_code == 200:
            return body["refresh_token"]
        err = body.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5
            continue
        sys.exit(f"Login failed: {err}: {body.get('error_description', '')[:200]}")
    sys.exit("Login timed out (code expired). Run login again.")


def access_token(cfg, email):
    """Trade the stored refresh token for an access token; persist the rotated refresh token."""
    acct = cfg["accounts"][email]
    if not acct.get("refresh_token"):
        sys.exit(f"{email} has no token yet. Run:  outlook.py login {email}")
    client_id, authority = account_app(cfg, email)
    base = token_url(authority)
    r = requests.post(f"{base}/token", data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": acct["refresh_token"],
        "scope": SCOPE,
    }, timeout=30)
    body = r.json()
    if r.status_code != 200:
        sys.exit(f"Token refresh for {email} failed ({body.get('error')}). "
                 f"Re-run:  outlook.py login {email}")
    if body.get("refresh_token"):           # MSA rotates refresh tokens: write the new one back
        acct["refresh_token"] = body["refresh_token"]
        save_account(cfg, email, refresh_token=body["refresh_token"])
    return body["access_token"]


# --- Graph read ------------------------------------------------------------------------

# One keep-alive connection for the whole run. `requests.get` builds and discards a session
# per call, so every Graph read paid a fresh DNS + TCP + TLS handshake - fine when that was a
# few calls per sync, wasteful now that fetch_body adds one per filed message.
SESSION = requests.Session()


def graph_get(token, path, prefer=None):
    url = path if path.startswith("http") else f"{GRAPH}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    if prefer:
        headers["Prefer"] = prefer
    r = SESSION.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


# The leading `XX:` chain on a subject, however many links and whatever language.
PREFIX_RE = re.compile(r"^\s*((?:[A-Za-z]{1,6}\s*:\s*)+)")
# Forward markers by locale. English, Dutch and French are the ones this has actually been run
# against; the rest are the prefixes those Outlook locales are believed to use, and none of them
# has been checked against a real mailbox. They are here because the errors are asymmetric (see
# is_forward): an extra token that never fires costs nothing, a missing one loses a message. Treat
# the list as a starting guess, not a reference - if a locale matters to you, verify it.
# The reply side is deliberately NOT enumerated: any token that is not a forward is stepped over,
# so "AW:" (de) or "Antw:" (nl) in front of a forward costs nothing and no locale has to be known
# in advance to be handled correctly.
FORWARD_TOKENS = frozenset((
    "fw", "fwd",     # English
    "tr",            # French  (transfert)
    "wg",            # German  (weitergeleitet)
    "doorst",        # Dutch   (doorgestuurd)
    "rv",            # Spanish (reenviar)
    "enc",           # Portuguese (encaminhada)
    "vs",            # Danish / Norwegian (videresendt)
    "vb",            # Swedish (vidarebefordrat)
    "i",             # Italian (inoltro)
))


def is_forward(subject):
    """True if any token in `subject`'s leading `XX:` chain is a forward marker.

    Distinguishing forwards from replies matters because Graph's `uniqueBody` means
    opposite things for each: for a reply it is the new text minus quoted history (exactly
    what a triage file wants); for a forward the entire forwarded message is itself the
    "quoted" part, so uniqueBody for a bare forward is the covering note only - or empty,
    for a forward with no covering note at all - and the content the forward exists to
    deliver never reaches the triage file.

    Reading the whole prefix chain rather than "Re: chain, then Fwd:" is what makes the
    localised cases work: the marker can sit under a reply prefix in any language, in any
    order, and no list of reply words has to be kept.

    The two errors are not equally bad, which is why the marker list leans inclusive. Missing
    a forward loses the forwarded message outright and silently. Mistaking a reply for one
    files `body` instead of `uniqueBody`, so the record carries its quoted thread - verbose,
    visible, and nothing is lost.
    """
    m = PREFIX_RE.match(subject or "")
    if not m:
        return False
    return any(t.strip().lower() in FORWARD_TOKENS for t in m.group(1).split(":"))


def fetch_body(token, msg):
    """(text, source) for ONE message's body, for filing. Falls back to bodyPreview.

    Deliberately a second round trip rather than another $select on the collection, for two
    reasons. `uniqueBody` - the part of the message that is NOT quoted reply history - is not
    returned on a collection query at all, only on a single-message GET; and `body` on a
    collection would drag the entire quoted thread into every page of the sync, for messages
    that mostly will not pass the filter anyway. So the listing stays cheap and this runs
    only for messages actually being written.

    `Prefer: outlook.body-content-type="text"` makes Graph do the HTML-to-text conversion
    server-side, so nothing here has to parse HTML.

    uniqueBody first, because a triage file for the fifth reply in a thread should hold that
    reply, not five copies of the thread. It can come back empty (Graph cannot always work
    out the boundary), so `body` is the fallback and bodyPreview the last resort - a filed
    message with a truncated body is bad, one with no body at all is worse.

    That ordering is backwards for a forward: see `is_forward`. There, `body` (the whole
    message, forwarded content included) goes first and `uniqueBody` (the covering note,
    or nothing) is the fallback instead.

    `source` is "uniqueBody", "body", or "preview". The caller needs the distinction, not just
    the text: "preview" means the message body never arrived and the 255-character preview is
    standing in for it, which write_triage has to say in the file. A record presenting a
    preview as the whole message is the failure this function exists to end, and this fallback
    is the one path where it can still happen.
    """
    try:
        # quote the id: it is base64-derived and can carry "+", "/" and "=", and an unescaped
        # "/" would silently become another path segment. Graph percent-decodes it back.
        m = graph_get(token, f"/me/messages/{quote(msg['id'], safe='')}?$select=body,uniqueBody",
                      prefer='outlook.body-content-type="text"')
    except Exception as e:                       # one unreadable message must not kill a sync
        print(f"    ! body fetch failed ({e}); filing the preview instead", file=sys.stderr)
        return (msg.get("bodyPreview") or "").strip(), "preview"
    keys = ("body", "uniqueBody") if is_forward(msg.get("subject")) else ("uniqueBody", "body")
    for key in keys:
        content = ((m.get(key) or {}).get("content") or "").strip()
        if content:
            return content, key
    return (msg.get("bodyPreview") or "").strip(), "preview"


def fetch_messages(token, days):
    """Recent messages across all folders, newest first, within the day window."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = ("/me/messages?$select=id,receivedDateTime,subject,from,toRecipients,ccRecipients,"
            "bodyPreview,webLink&$orderby=receivedDateTime desc&$top=50"
            f"&$filter=receivedDateTime ge {since}")
    out = []
    while path:
        page = graph_get(token, path)
        out.extend(page.get("value", []))
        path = page.get("@odata.nextLink")
    return out


def search_messages(token, query, limit=200):
    """Server-side keyword search across the whole mailbox, at any depth.

    Deliberately a SEPARATE path from fetch_messages: Graph rejects $search combined
    with $filter or $orderby, so there is no date window here and results come back
    ranked by relevance rather than newest-first. That is the point - fetch_messages
    walks a day window (fine for a sync, hopeless across years), while this hits the
    server index and returns in seconds however far back the match is.
    """
    path = ("/me/messages?$select=id,receivedDateTime,subject,from,toRecipients,ccRecipients,"
            f"bodyPreview,webLink&$top=50&$search={quote(chr(34) + query + chr(34))}")
    out = []
    while path and len(out) < limit:
        page = graph_get(token, path)
        out.extend(page.get("value", []))
        path = page.get("@odata.nextLink")
    return out[:limit]


# --- vault-derived relevance filter ----------------------------------------------------

def build_allowlist(vault_root):
    """Every email address mentioned in the vault's contact files (self-maintaining)."""
    network = vault_root / "areas" / "network"
    allow = set()
    if network.is_dir():
        for md in network.glob("*.md"):
            for m in EMAIL_RE.findall(md.read_text(encoding="utf-8", errors="ignore")):
                allow.add(m.lower())
    return allow


def addrs(msg):
    people = [msg.get("from")] + (msg.get("toRecipients") or []) + (msg.get("ccRecipients") or [])
    return {p["emailAddress"]["address"].lower()
            for p in people if p and p.get("emailAddress", {}).get("address")}


def vault_accounts(vc):
    """The mailboxes feeding this vault, from either config shape: `accounts` is a list of
    addresses when one filter serves them all, or an object keyed by address when they need
    different ones. Iterating a dict yields its keys, so both forms read the same here."""
    return list(vc.get("accounts") or [])


def account_filter(vc, email):
    """The filter serving ONE mailbox, as (keywords, match_all, match_body, subject_only).

    Per account, not per vault, because one vault can be fed by mailboxes of opposite shapes.
    A dedicated engagement mailbox IS the filter: everything in it is in scope, and keywords
    there only subtract, adding silent-drop risk for nothing. A shared info@ funnel is the
    reverse: a week can be four figures of mail, and the filter is the only thing between it
    and a triage/ folder abandoned in its first week. One vault-level list can serve either
    one, never both.

    Each setting falls back independently to the vault-level default, so a per-account block
    that only tightens `keywords` keeps the vault's body-matching choice rather than silently
    reverting it. A setting explicitly written as JSON `null` falls back too - `.get(key, ...)`
    only defaults on a MISSING key, and a null override is indistinguishable from "no opinion",
    not from "the empty/false value".
    """
    accts = vc.get("accounts") or []
    over = (accts.get(email) or {}) if isinstance(accts, dict) else {}

    def setting(key, default):
        value = over.get(key)          # a null (or missing) override defers to the vault level
        if value is None:
            value = vc.get(key)        # a null (or missing) vault default falls to `default`
        return default if value is None else value

    return (
        [k.lower() for k in setting("keywords", [])],
        bool(setting("match_all", False)),
        bool(setting("match_body", True)),
        {k.lower() for k in setting("subject_only_keywords", [])},
    )


def is_relevant(msg, allow, keywords, self_addrs=frozenset(), match_all=False, match_body=True,
                subject_only=frozenset()):
    # Match a COUNTERPARTY who is a known contact, not the mailbox owner. The owner's own
    # addresses are in the vault's contacts and every message in their box is to/from them,
    # so leaving them in would match everything (incl. the owner's other addresses, e.g.
    # hotmail <-> icloud self-mail). self_addrs lists every address that IS the owner.
    others = addrs(msg) - self_addrs
    if others & allow:
        return "contact"
    # match_all is the explicit catch-all. It exists because emptying `keywords` - the obvious
    # guess for "file everything" - does the opposite: it leaves the contact allowlist as the
    # only gate, which is STRICTER, not looser.
    if match_all:
        return "all"
    subject = (msg.get("subject") or "").lower()
    for kw in keywords:
        if kw in subject:
            return f"keyword:{kw}"
    # Subject-only matching is a systematic blind spot, not an occasional miss: it drops any
    # message whose subject is in a language the filter wasn't written in, and a dropped
    # message leaves no trace. bodyPreview is already fetched, so this costs nothing.
    if match_body:
        body = (msg.get("bodyPreview") or "").lower()
        for kw in keywords:
            if kw in subject_only:     # this keyword's body side is opted out - see docstring
                continue
            if kw in body:
                return f"body:{kw}"
    return None


# --- triage output ---------------------------------------------------------------------

def require_vault():
    """Refuse to write outside a vault. Run in place from the integrations folder, the
    two-levels-up guess resolves to the para-os repo and files real mail into it."""
    claude_md = VAULT_ROOT / "CLAUDE.md"
    marked = claude_md.exists() and "para-os-template:" in claude_md.read_text(
        encoding="utf-8", errors="ignore")
    if not marked and not (VAULT_ROOT / "triage").is_dir():
        sys.exit(f"{VAULT_ROOT} does not look like a vault (its CLAUDE.md carries no "
                 f"para-os-template marker and there is no triage/). Copy this script to "
                 f"<vault>/resources/scripts/ and run it from there.")


def safe_title(text):
    """Keep the vault's `YYYYMMDD Description.ext` shape: real words and spaces, minus
    the characters a filesystem rejects. Illegal characters become a space rather than
    nothing, so `Q3/Q4 plan` stays two words instead of welding into `Q3Q4`."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text or "")
    return re.sub(r"\s+", " ", text).strip(" .")[:60].strip(" .") or "no subject"


def write_triage(vault_root, account, msg, reason, body, source):
    received = (msg.get("receivedDateTime") or "")[:10].replace("-", "")
    frm = (msg.get("from") or {}).get("emailAddress") or {}
    subject = msg.get("subject") or "(no subject)"
    mid = hashlib.sha1(msg["id"].encode("utf-8")).hexdigest()[:6]  # unique per message: thread replies share date+subject
    # Join non-empty parts: a message with no receivedDateTime must not yield " Title.md".
    fname = " ".join(p for p in (received, safe_title(subject), mid) if p) + ".md"
    dest = vault_root / "triage" / fname
    dest.parent.mkdir(parents=True, exist_ok=True)
    # A preview standing in for the message is qualified in the file itself. The ledger entry
    # written straight after this one means no later run revisits the record, so its reader is
    # the only one left who can act on it, and an unmarked preview reads as the whole message.
    # Above the Link line on purpose: everything after Link is the message body verbatim, so a
    # header note placed below it would read as part of the message to anything measuring it.
    note = ("- **Body:** preview only - Graph's 255-character bodyPreview, not the full "
            "message. Open the link below to read it.\n") if source == "preview" else ""
    dest.write_text(
        f"# {subject}\n\n"
        f"- **Source:** Outlook ({account})\n"
        f"- **From:** {frm.get('name', '')} <{frm.get('address', '')}>\n"
        f"- **Received:** {msg.get('receivedDateTime') or ''}\n"
        f"- **Matched:** {reason}\n"
        f"{note}"
        f"- **Link:** {msg.get('webLink') or ''}\n\n"
        f"{body}\n",
        encoding="utf-8")
    return dest


# --- commands --------------------------------------------------------------------------

def cmd_accounts(cfg, _args):
    accts = cfg.get("accounts", {})
    if not accts:
        print("No accounts configured yet.")
        return
    feeds = vault_accounts(load_vault_config(required=False))
    for email, a in accts.items():
        state = "logged in" if a.get("refresh_token") else "NOT logged in (run login)"
        mark = "*" if email in feeds else " "
        # Show the authority when it is not the machine-wide one: a work mailbox silently
        # falling back to the personal app is otherwise invisible until the token fails.
        # account_app() exits on an unresolvable client_id; one such account must not blank
        # out the listing for every account after it.
        try:
            _, authority = account_app(cfg, email)
            own = f"  via {authority}" if authority != cfg.get("authority", "consumers") else ""
        except SystemExit:
            own = "  [no client_id configured]"
        print(f" {mark} {email:40s} [{state}]{own}")
    print(f"\n(* = feeds this vault: {VAULT}, per {VAULT_CONFIG.name})")


def cmd_login(cfg, args):
    entry = cfg.setdefault("accounts", {}).setdefault(args.email, {})
    # Seed the app pointers BEFORE the flow runs: device_login resolves them per account.
    seeded = {k: v for k, v in (("client_id", args.client_id),
                                ("authority", args.authority)) if v}
    entry.update(seeded)
    # The device-code wait can run for minutes, and another vault's sync can rotate a token
    # meanwhile. Merge this one account rather than writing the cfg we read before the wait.
    entry["refresh_token"] = device_login(cfg, args.email)
    save_account(cfg, args.email, refresh_token=entry["refresh_token"], **seeded)
    print(f"Logged in (machine-global). Token stored in {CONFIG_FILE}.\n"
          f"A vault pulls this mailbox when its own {VAULT_CONFIG.name} lists it under \"accounts\".")


def cmd_sync(cfg, args):
    # This copy syncs ONLY its own vault: the accounts its vault config declares.
    require_vault()
    vc = load_vault_config()
    feeds = vault_accounts(vc)
    if not feeds:
        sys.exit(f"{VAULT_CONFIG} lists no accounts - add the mailbox(es) that feed '{VAULT}'.")
    known = cfg.get("accounts", {})   # logged in on THIS machine
    missing = []                      # mailboxes it cannot read; named in the summary
    if args.account:
        if args.account not in feeds:
            sys.exit(f"{args.account} does not feed vault '{VAULT}' "
                     f"(its accounts per {VAULT_CONFIG.name}: {', '.join(feeds)}).")
        # A named account is a specific ask: if THIS one is not logged in, that is the
        # whole answer, not something to skip past silently.
        if args.account not in known:
            sys.exit(f"Not logged in on this machine: {args.account}. "
                     f"Run:  outlook.py login {args.account}")
        feeds = [args.account]
    else:
        # Default "sync everyone this vault is configured for" must not let one teammate's
        # account - logged in only on THEIR machine, per account_app's own design - block
        # every other account on this one. Run what this machine actually can, and say what
        # it skipped, rather than exiting before touching a single mailbox.
        missing = [e for e in feeds if e not in known]
        if missing:
            print(f"! not logged in on this machine, skipping: {', '.join(missing)} "
                  f"(run:  outlook.py login <email>  on the machine that owns it)",
                  file=sys.stderr)
        if len(missing) == len(feeds):
            sys.exit(f"None of this vault's accounts ({', '.join(feeds)}) are logged in on "
                     f"this machine. Run:  outlook.py login <email>")
        feeds = [e for e in feeds if e in known]

    ledger = load_ledger()
    allow = build_allowlist(VAULT_ROOT)

    total_new = 0
    degraded = 0                  # filed from the preview because the body fetch failed
    for email in feeds:
        keywords, match_all, match_body, subject_only = account_filter(vc, email)
        if not allow and not keywords and not match_all:
            print(f"! {email} -> '{VAULT}': no contact emails, no keywords, and match_all is "
                  f"off, so nothing can match. Add keywords, or set \"match_all\": true on "
                  f"this account in {VAULT_CONFIG.name} to file everything it receives.")
        acct = cfg["accounts"][email]
        self_addrs = {email.lower()} | {a.lower() for a in acct.get("self", [])}
        token = access_token(cfg, email)
        msgs = fetch_messages(token, args.days)
        # Name the filter actually in force per account: with per-account overrides, "which
        # filter ran against this mailbox" is no longer answerable from the config at a glance.
        # Only when match_body is on: with it off the body loop never runs, so a subject-only
        # opt-out is inert and naming a count for it reports a filter that is not in force.
        subj_only_note = (f", {len(subject_only)} subject-only"
                          if match_body and subject_only else "")
        scope = "match_all" if match_all else \
            f"{len(keywords)} keywords ({'subject+body' if match_body else 'subject only'}"\
            f"{subj_only_note})"
        print(f"\n{email}  scanned {len(msgs)} msgs -> {VAULT}  "
              f"({len(allow)} allowlisted senders, {scope})")

        for msg in msgs:
            if VAULT in ledger.get(msg["id"], {}).get("filed", []):   # already filed here
                continue
            reason = is_relevant(msg, allow, keywords, self_addrs, match_all, match_body,
                                 subject_only)
            if not reason:
                continue
            total_new += 1
            subject = msg.get("subject") or "(no subject)"
            frm = ((msg.get("from") or {}).get("emailAddress") or {}).get("address", "")
            tag = "WRITE" if args.write else "dry "
            print(f"  [{tag}] {(msg.get('receivedDateTime') or '')[:10]}  {reason:16s}  "
                  f"{frm:30s}  {subject[:50]}")
            if args.write:
                body, source = fetch_body(token, msg)
                if source == "preview":
                    degraded += 1
                write_triage(VAULT_ROOT, email, msg, reason, body, source)
                entry = ledger.setdefault(msg["id"], {"date": msg.get("receivedDateTime") or "",
                                                      "subject": subject, "account": email,
                                                      "filed": []})
                entry["filed"].append(VAULT)
                # Save per write, not at the end: a crash between the file and the ledger
                # resurrects mail the user has already triaged and moved out of triage/.
                save_ledger(ledger)
    # Both caveats belong on the closing line, not only in a warning that scrolled off the top
    # under one line per matched message: a run that never opened half the vault's mail, or
    # that filed records the body never reached, must not read like a clean one.
    caveats = ""
    if missing:
        caveats += f"  {len(missing)} mailbox(es) skipped (not logged in here): {', '.join(missing)}."
    if degraded:
        caveats += (f"  {degraded} record(s) filed from the preview because the body fetch "
                    f"failed; each says so on its own Body line.")
    print(f"\n{'Wrote' if args.write else 'Would file'} {total_new} new item(s) into {VAULT}/triage."
          + ("" if args.write else "  Re-run with --write to create the triage files.")
          + caveats)


def cmd_raw(cfg, args):
    email = args.account or next(iter(cfg.get("accounts", {})), None)
    if not email:
        sys.exit("No account. Pass --account or configure one.")
    token = access_token(cfg, email)
    print(json.dumps(graph_get(token, args.path), indent=2, ensure_ascii=False))


def cmd_search(cfg, args):
    """Ad-hoc lookup. Read-only by construction: prints, never writes.

    Unlike `sync` this ignores the vault's keyword filter and contact allowlist - the whole
    point is to ask a question the filter would not have surfaced. It does NOT ignore the
    vault's account list: like `sync`, it reads only the mailboxes that feed this vault,
    so a work-vault session never prints personal mail. `--all-mailboxes` widens it.
    """
    if args.account:
        accounts = [args.account]
    elif args.all_mailboxes:
        accounts = list(cfg.get("accounts", {}))
    else:
        accounts = vault_accounts(load_vault_config(required=False))
        if not accounts:
            sys.exit(f"{VAULT_CONFIG.name} lists no accounts for vault '{VAULT}'. Pass "
                     f"--account <email>, or --all-mailboxes for every mailbox on this machine.")
    if not accounts:
        sys.exit("No accounts configured. Run: outlook.py login <email>")
    total = 0
    for email in accounts:
        try:
            hits = search_messages(access_token(cfg, email), args.query, limit=args.limit)
        except (Exception, SystemExit) as e:        # one bad mailbox must not kill the rest;
            print(f"{email}  SEARCH FAILED: {e}", file=sys.stderr)   # access_token exits, so
            continue                                                 # SystemExit is in scope
        print(f"\n{email}  {len(hits)} hit(s) for {args.query!r}")
        for m in hits:
            when = (m.get("receivedDateTime") or "")[:10]
            frm = (m.get("from") or {}).get("emailAddress", {}).get("address", "?")
            subj = " ".join((m.get("subject") or "(no subject)").split())
            print(f"  {when}  {frm:34.34}  {subj[:72]}")
            if args.body:
                prev = " ".join((m.get("bodyPreview") or "").split())
                if prev:
                    print(f"{'':14}{prev[:200]}")
        total += len(hits)
    print(f"\n{total} hit(s) total. Read-only: nothing was written.")


def main():
    p = argparse.ArgumentParser(description="Sync personal Outlook/Hotmail mail into a vault's triage.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("accounts")

    lg = sub.add_parser("login")
    lg.add_argument("email")
    lg.add_argument("--client-id", help="Entra app for THIS mailbox (default: the machine-wide one). "
                                        "A work/school mailbox needs its own tenant's app")
    lg.add_argument("--authority", help="tenant id for THIS mailbox, or 'common' / 'consumers' "
                                        "(default: the machine-wide setting)")

    sy = sub.add_parser("sync")
    sy.add_argument("--account", help="only this account (default: all)")
    sy.add_argument("--days", type=int, default=7, help="lookback window (default 7)")
    sy.add_argument("--write", action="store_true", help="create triage files (default: dry run)")

    se = sub.add_parser("search", help="ad-hoc keyword search across the whole mailbox (read-only)")
    se.add_argument("query", help="words to look for; quote a phrase")
    se.add_argument("--account", help="only this account (default: this vault's accounts)")
    se.add_argument("--limit", type=int, default=50, help="max hits per account (default 50)")
    se.add_argument("--body", action="store_true", help="also print a body preview per hit")
    se.add_argument("--all-mailboxes", action="store_true",
                    help="search every mailbox on this machine, not just this vault's")

    rw = sub.add_parser("raw")
    rw.add_argument("path")
    rw.add_argument("--account")

    # `sync` is the default command: bare `outlook.py` or `... --write` runs a sync, so the
    # /para-triage sync-script convention (`<script> --write`, dry in preview) works unchanged.
    # Anything that is a real subcommand, or asks for the top-level help, is left alone.
    argv = sys.argv[1:]
    if not (argv and (argv[0] in sub.choices or argv[0] in {"-h", "--help"})):
        argv = ["sync"] + argv

    args = p.parse_args(argv)
    cfg = load_config()
    {"accounts": cmd_accounts, "login": cmd_login, "sync": cmd_sync,
     "search": cmd_search, "raw": cmd_raw}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
