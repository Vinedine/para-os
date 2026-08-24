#!/usr/bin/env python3
# para-os-integration: outlook 2026.08.02 - see CHANGELOG.md; /para-upgrade reports drift against this line.
"""Read personal Outlook.com / Hotmail mailboxes via Microsoft Graph, filter for
vault-relevant mail, and drop matches into the vault's triage/ folder.

Personal Microsoft accounts (outlook.com, hotmail.com, live.com) no longer accept
Basic Auth or app passwords: the ONLY way in is OAuth2. This script uses the OAuth2
device-code flow against one Entra app registration (delegated Graph Mail.Read), which
serves any number of personal accounts. No client secret (public client). Read-only:
it never sends, deletes, or marks mail read (a Graph GET does not change is-read state).

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
      "client_id": "00000000-0000-...",       # Entra app (client) id
      "authority": "consumers",               # "consumers" (personal-only app) or "common"
      "accounts": {
        "someone@hotmail.com": { "refresh_token": "...", "self": ["someone@icloud.com"] }
      }
    }

  VAULT CONFIG - this vault's resources/scripts/outlook_sync.json, next to this copy,
  version-controlled with the vault. Which mailboxes feed THIS vault plus its
  subject-keyword filter; edit it freely in a vault session, no secret ever lives here.
    { "accounts": ["someone@hotmail.com"], "keywords": ["invoice", "contract"] }

Per vault, the sender allowlist is NOT stored anywhere: it is rebuilt from
<vault>/areas/network/*.md on every run, so adding a contact automatically widens what
gets through.

Usage (on Windows, `py` works in place of `python3`):
  python3 outlook_sync.py accounts                   # login state + which accounts feed this vault
  python3 outlook_sync.py login someone@outlook.com  # one-time device-code login (machine-global)
  python3 outlook_sync.py sync                       # dry run: what WOULD be filed into THIS vault
  python3 outlook_sync.py sync --write               # actually write matches into this vault's triage/
  python3 outlook_sync.py sync --account someone@hotmail.com --days 14 --write
  python3 outlook_sync.py search "contract renewal"  # search the mailboxes feeding this vault
  python3 outlook_sync.py raw '/me/messages?$top=1'  # any Graph path, prints JSON (debug)
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
VAULT_CONFIG = SCRIPT_DIR / "outlook_sync.json"             # this vault's accounts + keywords
LEDGER_FILE = PARAOS_HOME / "cache" / "outlook" / "synced.json"

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = "https://graph.microsoft.com/Mail.Read offline_access"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


# --- config + ledger -------------------------------------------------------------------

def load_config():
    if not CONFIG_FILE.exists():
        sys.exit(f"No config at {CONFIG_FILE}. Create it with at least: "
                 '{"client_id": "...", "accounts": {}}')
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def load_vault_config(required=True):
    """This vault's own accounts + keywords, next to this script copy. Never secret."""
    if not VAULT_CONFIG.exists():
        if not required:
            return {}
        sys.exit(f"No vault config at {VAULT_CONFIG}. Create it with: "
                 '{"accounts": ["someone@hotmail.com"], "keywords": []}')
    return json.loads(VAULT_CONFIG.read_text(encoding="utf-8"))


def write_json_atomic(path, data):
    """Write via temp file + replace. These files are shared by every vault's copy of this
    script; a truncating write that dies half way takes every account's token with it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def save_config(cfg):
    write_json_atomic(CONFIG_FILE, cfg)


def save_token(cfg, email, refresh_token):
    """Persist ONE account's rotated token, re-reading first so a concurrent run's write survives.

    Two vault copies can refresh different accounts at the same moment. Writing our whole
    in-memory cfg back would undo the other's rotation, and the superseded token is dead:
    that account would need a full device-code re-login.
    """
    on_disk = json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else cfg
    on_disk.setdefault("accounts", {}).setdefault(email, {})["refresh_token"] = refresh_token
    write_json_atomic(CONFIG_FILE, on_disk)


def load_ledger():
    if LEDGER_FILE.exists():
        return json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
    return {}


def save_ledger(ledger):
    write_json_atomic(LEDGER_FILE, ledger)


def token_url(cfg):
    authority = cfg.get("authority", "consumers")  # personal-only app -> "consumers"
    return f"https://login.microsoftonline.com/{authority}/oauth2/v2.0"


# --- OAuth2 device-code flow -----------------------------------------------------------

def device_login(cfg, email):
    """Interactive: user opens a URL, types a code, consents once. Returns a refresh token."""
    base = token_url(cfg)
    r = requests.post(f"{base}/devicecode",
                      data={"client_id": cfg["client_id"], "scope": SCOPE}, timeout=30)
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
            "client_id": cfg["client_id"],
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
        sys.exit(f"{email} has no token yet. Run:  outlook_sync.py login {email}")
    base = token_url(cfg)
    r = requests.post(f"{base}/token", data={
        "grant_type": "refresh_token",
        "client_id": cfg["client_id"],
        "refresh_token": acct["refresh_token"],
        "scope": SCOPE,
    }, timeout=30)
    body = r.json()
    if r.status_code != 200:
        sys.exit(f"Token refresh for {email} failed ({body.get('error')}). "
                 f"Re-run:  outlook_sync.py login {email}")
    if body.get("refresh_token"):           # MSA rotates refresh tokens: write the new one back
        acct["refresh_token"] = body["refresh_token"]
        save_token(cfg, email, body["refresh_token"])
    return body["access_token"]


# --- Graph read ------------------------------------------------------------------------

def graph_get(token, path):
    url = path if path.startswith("http") else f"{GRAPH}{path}"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return r.json()


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
    from urllib.parse import quote
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


def is_relevant(msg, allow, keywords, self_addrs=frozenset()):
    # Match a COUNTERPARTY who is a known contact, not the mailbox owner. The owner's own
    # addresses are in the vault's contacts and every message in their box is to/from them,
    # so leaving them in would match everything (incl. the owner's other addresses, e.g.
    # hotmail <-> icloud self-mail). self_addrs lists every address that IS the owner.
    others = addrs(msg) - self_addrs
    if others & allow:
        return "contact"
    subject = (msg.get("subject") or "").lower()
    for kw in keywords:
        if kw in subject:
            return f"keyword:{kw}"
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


def write_triage(vault_root, account, msg, reason):
    received = (msg.get("receivedDateTime") or "")[:10].replace("-", "")
    frm = (msg.get("from") or {}).get("emailAddress") or {}
    subject = msg.get("subject") or "(no subject)"
    mid = hashlib.sha1(msg["id"].encode("utf-8")).hexdigest()[:6]  # unique per message: thread replies share date+subject
    # Join non-empty parts: a message with no receivedDateTime must not yield " Title.md".
    fname = " ".join(p for p in (received, safe_title(subject), mid) if p) + ".md"
    dest = vault_root / "triage" / fname
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        f"# {subject}\n\n"
        f"- **Source:** Outlook ({account})\n"
        f"- **From:** {frm.get('name', '')} <{frm.get('address', '')}>\n"
        f"- **Received:** {msg.get('receivedDateTime') or ''}\n"
        f"- **Matched:** {reason}\n"
        f"- **Link:** {msg.get('webLink') or ''}\n\n"
        f"{(msg.get('bodyPreview') or '').strip()}\n",
        encoding="utf-8")
    return dest


# --- commands --------------------------------------------------------------------------

def cmd_accounts(cfg, _args):
    accts = cfg.get("accounts", {})
    if not accts:
        print("No accounts configured yet.")
        return
    feeds = load_vault_config(required=False).get("accounts", [])
    for email, a in accts.items():
        state = "logged in" if a.get("refresh_token") else "NOT logged in (run login)"
        mark = "*" if email in feeds else " "
        print(f" {mark} {email:40s} [{state}]")
    print(f"\n(* = feeds this vault: {VAULT}, per {VAULT_CONFIG.name})")


def cmd_login(cfg, args):
    accts = cfg.setdefault("accounts", {})
    entry = accts.setdefault(args.email, {})
    entry["refresh_token"] = device_login(cfg, args.email)
    save_config(cfg)
    print(f"Logged in (machine-global). Token stored in {CONFIG_FILE}.\n"
          f"A vault pulls this mailbox when its own {VAULT_CONFIG.name} lists it under \"accounts\".")


def cmd_sync(cfg, args):
    # This copy syncs ONLY its own vault: the accounts its vault config declares.
    require_vault()
    vc = load_vault_config()
    feeds = vc.get("accounts") or []
    if not feeds:
        sys.exit(f"{VAULT_CONFIG} lists no accounts - add the mailbox(es) that feed '{VAULT}'.")
    if args.account:
        if args.account not in feeds:
            sys.exit(f"{args.account} does not feed vault '{VAULT}' "
                     f"(its accounts per {VAULT_CONFIG.name}: {', '.join(feeds)}).")
        feeds = [args.account]
    # Narrow first: an account this run will not touch must not block it.
    missing = [e for e in feeds if e not in cfg.get("accounts", {})]
    if missing:
        sys.exit(f"Not logged in on this machine: {', '.join(missing)}. "
                 f"Run:  outlook_sync.py login <email>")

    ledger = load_ledger()
    allow = build_allowlist(VAULT_ROOT)
    keywords = [k.lower() for k in vc.get("keywords", [])]
    if not allow and not keywords:
        print(f"! vault '{VAULT}' has no contact emails and no keywords - nothing can match yet.")

    total_new = 0
    for email in feeds:
        acct = cfg["accounts"][email]
        self_addrs = {email.lower()} | {a.lower() for a in acct.get("self", [])}
        token = access_token(cfg, email)
        msgs = fetch_messages(token, args.days)
        print(f"\n{email}  scanned {len(msgs)} msgs -> {VAULT}  "
              f"({len(allow)} allowlisted senders, {len(keywords)} keywords)")

        for msg in msgs:
            if VAULT in ledger.get(msg["id"], {}).get("filed", []):   # already filed here
                continue
            reason = is_relevant(msg, allow, keywords, self_addrs)
            if not reason:
                continue
            total_new += 1
            subject = msg.get("subject") or "(no subject)"
            frm = ((msg.get("from") or {}).get("emailAddress") or {}).get("address", "")
            tag = "WRITE" if args.write else "dry "
            print(f"  [{tag}] {(msg.get('receivedDateTime') or '')[:10]}  {reason:16s}  "
                  f"{frm:30s}  {subject[:50]}")
            if args.write:
                write_triage(VAULT_ROOT, email, msg, reason)
                entry = ledger.setdefault(msg["id"], {"date": msg.get("receivedDateTime") or "",
                                                      "subject": subject, "account": email,
                                                      "filed": []})
                entry["filed"].append(VAULT)
                # Save per write, not at the end: a crash between the file and the ledger
                # resurrects mail the user has already triaged and moved out of triage/.
                save_ledger(ledger)
    print(f"\n{'Wrote' if args.write else 'Would file'} {total_new} new item(s) into {VAULT}/triage."
          + ("" if args.write else "  Re-run with --write to create the triage files."))


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
        accounts = load_vault_config(required=False).get("accounts") or []
        if not accounts:
            sys.exit(f"{VAULT_CONFIG.name} lists no accounts for vault '{VAULT}'. Pass "
                     f"--account <email>, or --all-mailboxes for every mailbox on this machine.")
    if not accounts:
        sys.exit("No accounts configured. Run: outlook_sync.py login <email>")
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

    # `sync` is the default command: bare `outlook_sync.py` or `... --write` runs a sync, so the
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
