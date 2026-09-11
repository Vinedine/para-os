#!/usr/bin/env python3
# para-os-integration: outlook 2026.09.02 - see CHANGELOG.md; /para-upgrade reports drift against this line.
"""Read Outlook.com / Hotmail / Microsoft 365 mailboxes via Microsoft Graph and hand the
messages to a caller that decides what they mean. Writes nothing, anywhere, ever.

That last part is the design, not a caveat. This script used to have a `sync` subcommand
that decided relevance from a static config - keywords, a catch-all switch, a contact
allowlist - and wrote every match into the vault's triage/ folder. Two things were wrong
with it. The filters were guesses maintained by hand, and being wrong cost a folder full
of files to delete; and on a live personal inbox the honest setting was "take everything",
which meant four figures a week. `fetch` reads the same mailbox and prints the candidates
instead, so a skill can judge them against the vault's own rules and write only what
survives. Removed: nothing here files mail any more.

Microsoft accounts no longer accept Basic Auth or app passwords: the ONLY way in is
OAuth2, against an Entra app registration (delegated Graph Mail.Read) with no client
secret (public client). Read-only in the strict sense: it never sends, deletes, or marks
mail read (a Graph GET does not change is-read state).

`login` signs in through the browser - authorization code + PKCE on a loopback redirect -
because device code flow is being closed off: security defaults block it, and since
1 July 2026 that is the shipped default on every NEW tenant. `login --device-code` still
runs the old flow for an app with no http://localhost redirect URI registered, and on a
tenant predating that change nothing here is affected either way. Which flow minted a
refresh token is not recorded in it and not asked about when it is redeemed, so a mailbox
already logged in keeps working untouched - the flow only decides what `login` does.

One app cannot serve every mailbox. A personal-accounts app is registered against the
"consumers" authority, which refuses work/school accounts outright, so a Microsoft 365
mailbox needs its own registration in its own tenant. Both the app and the authority
therefore resolve PER ACCOUNT, falling back to the machine-wide pair (see account_app).

Per-vault copy, shared secret (the granola pattern): this script is COPIED into each vault
it serves and reads only the mailboxes that vault declares, auto-detected from its own
path. One mailbox can still feed many vaults, each vault's config naming the accounts that
feed it. There is no longer a shared dedup ledger, because nothing is filed to deduplicate:
whatever consumes `fetch` keeps its own record of what it has already dealt with.

Config is split by what it is:

  SECRETS - machine-global, ~/.paraos/secrets/outlook.json (outside the vault on purpose:
  a secret inside it leaks when the vault syncs). Credentials only, nothing vault-specific.
  Rewritten every run because MSA rotates the refresh token on each refresh.
    {
      "client_id": "00000000-0000-...",       # default Entra app (client) id
      "authority": "consumers",               # default: "consumers", "common", or a tenant id
      "accounts": {
        "someone@hotmail.com": { "refresh_token": "..." },

        # A work/school mailbox overrides both, pointing at its own tenant's app.
        # Seed them at login:  outlook.py login someone@company.com \
        #                        --client-id <app> --authority <tenant-id>
        "someone@company.com": { "refresh_token": "...",
                                 "client_id": "11111111-1111-...",
                                 "authority": "22222222-2222-..." },

        # A SHARED mailbox has no sign-in and no password, so it is never a `login`. It is
        # read through a user holding Full Access on it, named by `via`. No token of its
        # own. Needs delegated Mail.Read.Shared on that user's app - which account_scope()
        # asks for on THAT user alone, from this `via` line. Every other account is asked
        # for Mail.Read only, because a scope an account never consented to fails its
        # refresh outright rather than degrading.
        "info@company.com":     { "via": "someone@company.com" },

        # `shared: true` asks for Mail.Read.Shared on an account no `via` line points at
        # yet, so the consent is in place before the shared entry is added. Set by
        # `login --shared`; unnecessary once the `via` line above exists.
        "reader@company.com":   { "refresh_token": "...", "shared": true }
      }
    }

  VAULT CONFIG - this vault's resources/scripts/outlook.config.json, next to this copy,
  version-controlled with the vault. Which mailboxes feed THIS vault, and nothing else now
  that there are no filters to configure. NOT named outlook.json: that is the machine-global
  secret above, and two files sharing one name across opposite trust zones is how a
  credential ends up inside a synced vault.
    { "accounts": ["someone@hotmail.com"] }

  `accounts` may also be an object keyed by address. That shape existed to hang a per-mailbox
  filter off each key and is now equivalent to the list; both are read, so no vault has to be
  edited, and any filter keys left in place are inert.

Bulk mail is dropped before the caller sees it, on the RFC 2369 List-Unsubscribe header and
nothing else (see has_unsubscribe). It is a cost-saver, not a relevance filter: everything
else is judged, and --include-bulk turns it off. There is deliberately no noreply-style
sender-name backstop - that is the exclusion para-shared/connectors.md forbids by default,
because the transactional mail a vault most wants is nearly always sent from one. What
survives is real correspondence mixed with the spam that declines to identify itself, and
telling those apart is judgment rather than a rule.

Usage (on Windows, `py` works in place of `python3`):
  python3 outlook.py accounts                   # login state + which accounts feed this vault
  python3 outlook.py login someone@outlook.com  # one-time browser login (machine-global)
  python3 outlook.py fetch --days 30            # candidates as JSON on stdout, counts on stderr
  python3 outlook.py search "contract renewal"  # search the mailboxes feeding this vault
  python3 outlook.py raw '/me/messages?$top=1'  # any Graph path, prints JSON (debug)
"""
import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

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

GRAPH = "https://graph.microsoft.com/v1.0"

# Scope is resolved PER ACCOUNT by account_scope(), never as one constant for every mailbox:
# a refresh may narrow the consented scope but never widen it, so asking every account for
# Mail.Read.Shared fails the refresh (AADSTS65001) on every account that never consented to
# it. The `consumers` endpoint drops the extra silently, so only work tenants show it.
READ_SCOPE = "https://graph.microsoft.com/Mail.Read"
SHARED_SCOPE = "https://graph.microsoft.com/Mail.Read.Shared"
OFFLINE_SCOPE = "offline_access"

# The fields a record is built from. One list, because `fetch` and `search` must emit the
# same record shape - the last field added had to be pasted into both, and a field added to
# only one is a record the caller cannot group.
SELECT_FIELDS = ("id,internetMessageId,conversationId,receivedDateTime,subject,from,"
                 "toRecipients,ccRecipients,bodyPreview,webLink")

# One keep-alive connection for the whole run, token endpoint included. Through a bare
# `requests.post`/`requests.get` every call builds and discards its own session, paying a
# fresh DNS + TCP + TLS handshake - once per mailbox for the tokens, and once per page for
# a fetch that walks a whole window.
SESSION = requests.Session()


# --- config ---------------------------------------------------------------------------

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
             '{"accounts": ["someone@hotmail.com"]}')


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


def account_scope(cfg, email):
    """The delegated scope ONE account is asked for, as a space-separated string.

    Mail.Read for everyone, plus Mail.Read.Shared only for an account that actually reads a
    shared mailbox - a mailbox somewhere in this config names it as its `via`, or a `login
    --shared` set the flag on it ahead of that entry existing.

    Narrow by default because the token endpoint is asymmetric: a refresh may ask for LESS
    than was consented but never more, so a scope the account never consented to does not
    degrade, it fails the refresh outright and takes an already-working mailbox offline. The
    account that needs the wider scope is the exception (one, here), and it is the one that
    gets prompted to consent to it.
    """
    accts = cfg.get("accounts") or {}
    entry = accts.get(email) or {}
    reads_shared = bool(entry.get("shared")) or any(
        (a or {}).get("via") == email for a in accts.values())
    parts = [READ_SCOPE] + ([SHARED_SCOPE] if reads_shared else []) + [OFFLINE_SCOPE]
    return " ".join(parts)


def mailbox_route(cfg, email):
    """Which account's token reads ONE feed address, and where Graph is addressed, as
    (token_account, graph_root).

    A shared mailbox has no sign-in and no password - that is what makes it free and
    unlicensed - so it can never be a `login`. It is read THROUGH a user who holds Full
    Access on it: the account entry carries `via` naming that user, the token comes from
    them, and Graph is addressed at /users/<shared> rather than /me. Needs delegated
    Mail.Read.Shared on the app, which plain Mail.Read does not cover.

    Everything without `via` resolves to itself and /me, so every existing config on every
    machine behaves exactly as it did before this existed.
    """
    acct = (cfg.get("accounts") or {}).get(email) or {}
    via = acct.get("via")
    if not via:
        return email, "/me"
    if via not in (cfg.get("accounts") or {}):
        sys.exit(f"{email} is read via {via}, which has no entry on this machine. "
                 f"Run:  outlook.py login {via}")
    return via, f"/users/{email}"


def token_url(authority):
    return f"https://login.microsoftonline.com/{authority}/oauth2/v2.0"


# --- OAuth2 device-code flow -----------------------------------------------------------

def _b64url(raw):
    """base64url, unpadded - what RFC 7636 wants for both PKCE values."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _callback_handler():
    """A one-shot loopback handler, built fresh per login so two logins in one process
    cannot see each other's authorization code."""

    class Handler(BaseHTTPRequestHandler):
        result = None

        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            if "code" not in q and "error" not in q:
                self.send_response(404)       # a browser asking for /favicon.ico is not the
                self.end_headers()            # callback; answer it without consuming the wait
                return
            Handler.result = q
            body = ("<!doctype html><meta charset=utf-8>"
                    "<body style='font-family:system-ui;padding:3rem;max-width:32rem'>"
                    "<h3>Signed in.</h3><p>Close this tab and return to the terminal.</p>"
                    ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass                              # the default logs every hit to stderr

    return Handler


def pkce_login(cfg, email):
    """Interactive: authorization code + PKCE on a loopback redirect. Returns a refresh token.

    The default now that device code flow is being closed off (why: module docstring).
    Untouched by that shift either way.

    Nothing about an existing account changes. Which flow minted a refresh token is not
    recorded in it and not asked about when it is redeemed, so every mailbox already logged
    in keeps working untouched; the flow only decides what happens during `login`.

    Needs `http://localhost` registered as a redirect URI on the app, under the "Mobile and
    desktop applications" platform. Register it without a port: the port is ignored when
    Entra matches a loopback redirect, so one entry covers whatever ephemeral port the OS
    hands us here. An app that has no such entry cannot use this flow at all, which is what
    `login --device-code` is still there for.
    """
    client_id, authority = account_app(cfg, email)
    scope = account_scope(cfg, email)
    base = token_url(authority)

    verifier = _b64url(os.urandom(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    state = secrets.token_urlsafe(16)

    # Port 0 asks the OS for a free one. Bound before the URL is built, because the port is
    # part of the redirect the authorize request has to commit to.
    Handler = _callback_handler()
    try:
        server = HTTPServer(("127.0.0.1", 0), Handler)
    except OSError as e:
        sys.exit(f"Could not open a loopback port for the sign-in redirect ({e}). "
                 f"Use:  outlook.py login {email} --device-code")
    server.timeout = 1
    redirect_uri = f"http://localhost:{server.server_port}"

    url = f"{base}/authorize?" + urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": scope,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "login_hint": email,          # preselects the account; the user can still switch
    })

    print(f"\n  Opening a browser to sign in as {email}.")
    print(f"  If nothing opens, paste this into a browser on THIS machine:\n\n  {url}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass                          # headless is fine: the URL is printed above
    # Printed every time, because the failure it warns about lands in the BROWSER and
    # never reaches this process: an app with no reply address shows AADSTS500113 on
    # Microsoft's own error page, no redirect is ever sent, and all this side sees is
    # silence until the timeout. Naming it up front costs a line and saves five minutes.
    print(f"  App {client_id} must have  http://localhost  registered as a redirect URI")
    print("  (Entra > App registrations > Authentication > Mobile and desktop applications).")
    print("  Waiting for the redirect...", flush=True)

    deadline = time.monotonic() + 300
    while Handler.result is None and time.monotonic() < deadline:
        server.handle_request()
    server.server_close()

    if Handler.result is None:
        # The likely cause is not that the operator was slow. If the browser showed an
        # error instead of redirecting, this process was never told: the authorize step
        # fails at Microsoft, and the commonest reason by far is a missing reply address.
        sys.exit(
            "No redirect arrived within 5 minutes." + chr(10) +
            '  If the browser showed AADSTS500113 ("No reply address is registered for '
            'the application"), that is this, and it is a one-time fix:' + chr(10) +
            "    Entra admin center > App registrations > the app with client id" + chr(10) +
            f"    {client_id} > Authentication > Add a platform >" + chr(10) +
            "    Mobile and desktop applications, then type  http://localhost  into" + chr(10) +
            "    the free-text field (it is NOT one of the tick-boxes) > Configure" + chr(10) +
            "  Register it WITHOUT a port; Entra ignores the port on a loopback redirect."
            + chr(10) +
            f"  Then re-run:  outlook.py login {email}" + chr(10) +
            f"  Or where the tenant still permits it:  outlook.py login {email} --device-code")
    q = Handler.result
    if "error" in q:
        sys.exit(f"Sign-in failed: {q['error'][0]}: "
                 f"{(q.get('error_description') or [''])[0][:300]}")
    # A mismatched state means the code came back from a request that was not the one this
    # process started. Refusing is the whole point of sending it.
    if (q.get("state") or [None])[0] != state:
        sys.exit("Sign-in rejected: the redirect carried the wrong state value.")

    r = SESSION.post(f"{base}/token", data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": q["code"][0],
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
        "scope": scope,
    }, timeout=30)
    body = r.json()
    if r.status_code != 200:
        sys.exit(auth_failure(email, scope, authority, client_id, body, what="Sign-in"))
    return body["refresh_token"]


def device_login(cfg, email):
    """Interactive: user opens a URL, types a code, consents once. Returns a refresh token.

    No longer the default (why: module docstring). Kept because it is the only flow that
    needs nothing registered on the app, so it still logs in a mailbox whose app has no
    loopback redirect URI.
    """
    client_id, authority = account_app(cfg, email)
    scope = account_scope(cfg, email)
    base = token_url(authority)
    r = SESSION.post(f"{base}/devicecode",
                      data={"client_id": client_id, "scope": scope}, timeout=30)
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
        p = SESSION.post(f"{base}/token", data={
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


def auth_failure(email, scope, authority, client_id, body, what="Token refresh"):
    """The message a failed token exchange exits with.

    Microsoft says exactly what is wrong in `error_description`, keyed by an AADSTS code,
    and this used to print neither - just the OAuth error class (`invalid_grant`,
    `invalid_request`, both of which cover a dozen unrelated causes) followed by "re-run
    login". That advice is wrong more often than it is right: a consent gap needs a login
    with a different scope, and a tenant policy block cannot be fixed by logging in at all,
    so the one instruction offered sent you round a loop that could not terminate. The code
    is the diagnosis, so it is quoted, and the remedy follows from it.
    """
    codes = set(body.get("error_codes") or [])
    # `.splitlines()[0]` on a response that carried no description is an IndexError inside
    # the error path - a crash reporting a crash, hiding the failure it was called about.
    desc = next(iter((body.get("error_description") or "").splitlines()), "").strip()
    lines = [f"{what} for {email} failed ({body.get('error')})."]
    if desc:
        lines.append(f"  {desc}")

    if 65001 in codes:                      # consented scope does not cover what was asked
        if SHARED_SCOPE in scope:
            lines.append(f"  This account was asked for Mail.Read.Shared, which its consent "
                         f"does not cover. It is asked because a shared mailbox in "
                         f"{CONFIG_FILE.name} names it as `via`.")
            lines.append(f"  Fix:  outlook.py login {email} --shared   "
                         f"(or have a tenant admin grant Mail.Read.Shared to app {client_id})")
        else:
            lines.append(f"  Consent was never granted, or has been revoked.")
            lines.append(f"  Fix:  outlook.py login {email}")
    elif 530035 in codes:                   # security defaults blocking the sign-in itself
        # Almost always device code flow (why: module docstring). A new tenant enforces
        # security defaults after a 24-hour grace period, so this arrives as "it worked
        # for a day and then stopped".
        lines.append(f"  Tenant {authority} blocks this sign-in by policy, and security "
                     f"defaults are on or off with no per-app exception.")
        lines.append(f"  Most likely fix, and it needs no admin:  outlook.py login {email}")
        lines.append(f"    The default login is a browser sign-in (auth code + PKCE), which "
                     f"security defaults do not block. Device code flow is what they block. "
                     f"Needs http://localhost on app {client_id} as a redirect URI.")
        lines.append(f"  Otherwise a tenant admin either turns security defaults off "
                     f"(losing the MFA baseline unless Entra ID P1 + a Conditional Access "
                     f"policy replaces it), or adds P1 and writes a policy whose "
                     f"'Authentication flows' condition permits this app.")
    elif 53003 in codes:                    # a real Conditional Access policy
        lines.append(f"  A Conditional Access policy in tenant {authority} blocks this "
                     f"sign-in. A re-login cannot get past it; the policy has to change.")
        lines.append(f"  The sign-in log names the policy: Entra ID > Monitoring & health > "
                     f"Sign-in logs, filter on app {client_id}, then the Conditional access "
                     f"tab of the failed record.")
    elif codes & {70008, 700082, 50173}:     # refresh token expired or invalidated
        lines.append(f"  The stored refresh token has expired or was invalidated "
                     f"(a password change and a revoked session both do this).")
        lines.append(f"  Fix:  outlook.py login {email}")
    elif codes & {50076, 50079, 50158}:      # MFA / CA challenge the refresh path cannot answer
        lines.append(f"  The tenant wants an interactive challenge (MFA or a Conditional "
                     f"Access grant) that a refresh cannot answer.")
        lines.append(f"  Fix:  outlook.py login {email}")
    else:
        lines.append(f"  Fix, if the code above does not say otherwise:  "
                     f"outlook.py login {email}")
    return "\n".join(lines)


_TOKENS = {}    # account -> access token, for this run only. Never persisted.


def access_token(cfg, email):
    """Trade the stored refresh token for an access token; persist the rotated refresh token.

    Cached per run, because `mailbox_route` maps every shared mailbox back to the one user
    holding Full Access on it: a vault feeding an owner plus two of their shared mailboxes
    asks for the same account's token three times. Each ask is a network round-trip plus a
    read and an atomic rewrite of the secrets file, and each rotation invalidates the
    refresh token the previous one just stored.
    """
    if email in _TOKENS:
        return _TOKENS[email]
    acct = cfg["accounts"][email]
    if not acct.get("refresh_token"):
        sys.exit(f"{email} has no token yet. Run:  outlook.py login {email}")
    client_id, authority = account_app(cfg, email)
    scope = account_scope(cfg, email)
    base = token_url(authority)
    r = SESSION.post(f"{base}/token", data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": acct["refresh_token"],
        "scope": scope,
    }, timeout=30)
    body = r.json()
    if r.status_code != 200:
        sys.exit(auth_failure(email, scope, authority, client_id, body))
    if body.get("refresh_token"):           # MSA rotates refresh tokens: write the new one back
        acct["refresh_token"] = body["refresh_token"]
        save_account(cfg, email, refresh_token=body["refresh_token"])
    _TOKENS[email] = body["access_token"]
    return _TOKENS[email]


# --- Graph read ------------------------------------------------------------------------

THROTTLE_RETRIES = 3        # a fetch pages hard enough to be throttled; a search does not
THROTTLE_MAX_WAIT = 60      # cap the server's Retry-After: a long one is worse than failing


def graph_get(token, path, prefer=None):
    """One Graph read, retried on a throttle.

    Graph answers a caller that pages hard with 429 and a `Retry-After`, and without this
    that lands as an unhandled HTTPError partway through a run - discarding every message
    already fetched, since nothing is emitted until the end. Retried here rather than at the
    call sites so the search path gets it too, and bounded so a throttled mailbox fails
    loudly rather than hanging.
    """
    url = path if path.startswith("http") else f"{GRAPH}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    if prefer:
        headers["Prefer"] = prefer
    for attempt in range(THROTTLE_RETRIES + 1):
        r = SESSION.get(url, headers=headers, timeout=30)
        if r.status_code not in (429, 503) or attempt == THROTTLE_RETRIES:
            break
        try:
            wait = int(r.headers.get("Retry-After", ""))
        except ValueError:
            wait = 5 * (attempt + 1)
        wait = min(max(wait, 1), THROTTLE_MAX_WAIT)
        print(f"! throttled by Graph, waiting {wait}s "
              f"({attempt + 1}/{THROTTLE_RETRIES})", file=sys.stderr)
        time.sleep(wait)
    r.raise_for_status()
    return r.json()


# Folders a fetch reads, as Graph well-known names rather than display names, which are
# localized ("Junk Email" is "Ongewenste e-mail" on a Dutch mailbox) and so cannot be
# matched on. An allowlist, because the folders worth reading are few and the ones worth
# skipping are not: Junk and Deleted Items are disposals the operator or the spam filter
# has already made, and re-surfacing them undoes that decision.
FETCH_FOLDERS = ("inbox", "archive")

# A ceiling on one mailbox's fetch. `search` has always had `--limit`; this is the same bound
# for the path that pages a whole window, because a busy inbox over 30 days is thousands of
# messages, each carrying its full header block, and a run that dies of its own size has
# fetched everything and emitted nothing. Truncation is reported, never silent.
FETCH_MAX_MESSAGES = 1000

# Messages per request. The payload is dominated by the header block either way, so a
# bigger page buys fewer sequential round-trips for the same bytes - and a full window is
# all latency, not bandwidth.
PAGE_SIZE = 100


def fetch_messages(token, days, root="/me", limit=FETCH_MAX_MESSAGES):
    """Recent messages from the inbox and the archive, newest first, within the day window.

    Pulls internetMessageHeaders along with the rest, which is how the caller sees
    List-Unsubscribe and therefore knows bulk mail for what it is. The header block is
    large and never leaves this script, so it costs time rather than tokens.

    Scoped to FETCH_FOLDERS rather than /me/messages, which is the whole mailbox. That
    earlier scope read Junk Email, Deleted Items and Sent Items too, so a run re-surfaced
    mail the spam filter had caught and mail the operator had thrown away, and offered it
    back as a candidate (README.md has the measurements). The archive stays in scope
    because a fast archiver can file a real message between two runs, and it is cheap.

    Stops at `limit` messages across all folders and says so on stderr, so a mailbox too big
    for one window truncates visibly instead of running until something breaks.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out, seen = [], set()
    for folder in FETCH_FOLDERS:
        if len(out) >= limit:
            break
        path = (f"{root}/mailFolders/{folder}/messages"
                f"?$select={SELECT_FIELDS},internetMessageHeaders"
                f"&$orderby=receivedDateTime desc&$top={PAGE_SIZE}"
                f"&$filter=receivedDateTime ge {since}")
        while path:
            try:
                page = graph_get(token, path)
            except requests.HTTPError as e:
                # A mailbox without this folder must not cost the run the folders it does
                # have; anything else is still fatal.
                if e.response is not None and e.response.status_code == 404:
                    break
                raise
            for m in page.get("value", []):
                if m["id"] not in seen:
                    seen.add(m["id"])
                    out.append(m)
            path = page.get("@odata.nextLink")
            if len(out) >= limit:
                if path:
                    print(f"! {root} {folder}: stopped at {limit} messages, window not fully "
                          f"covered. Narrow --days, or raise FETCH_MAX_MESSAGES.", file=sys.stderr)
                break
    out.sort(key=lambda m: m.get("receivedDateTime") or "", reverse=True)
    return out


def search_messages(token, query, limit=200, root="/me"):
    """Server-side keyword search across the whole mailbox, at any depth.

    Deliberately a SEPARATE path from fetch_messages: Graph rejects $search combined
    with $filter or $orderby, so there is no date window here and results come back
    ranked by relevance rather than newest-first. That is the point - fetch_messages
    walks a day window (fine for a fetch, hopeless across years), while this hits the
    server index and returns in seconds however far back the match is.
    """
    path = (f"{root}/messages?$select={SELECT_FIELDS}"
            f"&$top={PAGE_SIZE}&$search={quote(chr(34) + query + chr(34))}")
    out = []
    while path and len(out) < limit:
        page = graph_get(token, path)
        out.extend(page.get("value", []))
        path = page.get("@odata.nextLink")
    return out[:limit]


# --- vault config -----------------------------------------------------------------------

def vault_accounts(vc):
    """The mailboxes feeding this vault, from either config shape: `accounts` is a list of
    addresses when one filter serves them all, or an object keyed by address when they need
    different ones. Iterating a dict yields its keys, so both forms read the same here."""
    return list(vc.get("accounts") or [])


# --- vault guard ------------------------------------------------------------------------

def require_vault():
    """Refuse to run outside a vault. This copy resolves the vault from its own path, so run
    in place from the integrations folder that guess lands on the para-os repo, and the script
    would read a mailbox on behalf of a 'vault' that is really a source tree."""
    claude_md = VAULT_ROOT / "CLAUDE.md"
    marked = claude_md.exists() and "para-os-template:" in claude_md.read_text(
        encoding="utf-8", errors="ignore")
    if not marked and not (VAULT_ROOT / "triage").is_dir():
        sys.exit(f"{VAULT_ROOT} does not look like a vault (its CLAUDE.md carries no "
                 f"para-os-template marker and there is no triage/). Copy this script to "
                 f"<vault>/resources/scripts/ and run it from there.")


# --- commands --------------------------------------------------------------------------

def cmd_accounts(cfg, _args):
    accts = cfg.get("accounts", {})
    if not accts:
        print("No accounts configured yet.")
        return
    feeds = vault_accounts(load_vault_config(required=False))
    for email, a in accts.items():
        # A shared mailbox has no sign-in of its own, so "NOT logged in" would read as a
        # setup step that will never be done. Say what it actually is instead.
        if a.get("via"):
            state = f"shared, read via {a['via']}"
        else:
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
        # The one account carrying the wider consent is worth seeing here. It is the only
        # one that can fail on a scope the others never ask for, and a listing that hides
        # which account that is makes AADSTS65001 look like it came from nowhere.
        if SHARED_SCOPE in account_scope(cfg, email):
            own += "  +Mail.Read.Shared"
        print(f" {mark} {email:40s} [{state}]{own}")
    print(f"\n(* = feeds this vault: {VAULT}, per {VAULT_CONFIG.name})")


def cmd_login(cfg, args):
    entry = cfg.setdefault("accounts", {}).setdefault(args.email, {})
    # Seed the app pointers BEFORE the flow runs: device_login resolves them per account,
    # and `shared` is one of them - account_scope reads it off this entry to decide what
    # consent to ask for, so setting it afterwards would consent to the narrow scope and
    # then request the wide one on every refresh after that.
    seeded = {k: v for k, v in (("client_id", args.client_id),
                                ("authority", args.authority),
                                ("shared", args.shared or None)) if v}
    entry.update(seeded)
    # The device-code wait can run for minutes, and another vault's run can rotate a token
    # meanwhile. Merge this one account rather than writing the cfg we read before the wait.
    flow = device_login if getattr(args, "device_code", False) else pkce_login
    entry["refresh_token"] = flow(cfg, args.email)
    save_account(cfg, args.email, refresh_token=entry["refresh_token"], **seeded)
    print(f"Logged in (machine-global). Token stored in {CONFIG_FILE}.\n"
          f"A vault pulls this mailbox when its own {VAULT_CONFIG.name} lists it under \"accounts\".")


def resolve_feeds(cfg, account_arg):
    """The accounts this copy may read: its vault's declared feeds, minus what this machine
    is not logged in to."""
    require_vault()
    feeds = vault_accounts(load_vault_config())
    if not feeds:
        sys.exit(f"{VAULT_CONFIG} lists no accounts - add the mailbox(es) that feed '{VAULT}'.")
    known = cfg.get("accounts", {})   # logged in on THIS machine
    if account_arg:
        if account_arg not in feeds:
            sys.exit(f"{account_arg} does not feed vault '{VAULT}' "
                     f"(its accounts per {VAULT_CONFIG.name}: {', '.join(feeds)}).")
        # A named account is a specific ask: if THIS one is not logged in, that is the
        # whole answer, not something to skip past silently.
        if account_arg not in known:
            sys.exit(f"Not logged in on this machine: {account_arg}. "
                     f"Run:  outlook.py login {account_arg}")
        return [account_arg], []
    # Default "everyone this vault is configured for" must not let one teammate's account -
    # logged in only on THEIR machine, per account_app's own design - block every other
    # account on this one. Run what this machine actually can, and say what it skipped,
    # rather than exiting before touching a single mailbox.
    missing = [e for e in feeds if e not in known]
    if missing:
        print(f"! not logged in on this machine, skipping: {', '.join(missing)} "
              f"(run:  outlook.py login <email>  on the machine that owns it)",
              file=sys.stderr)
    if len(missing) == len(feeds):
        sys.exit(f"None of this vault's accounts ({', '.join(feeds)}) are logged in on "
                 f"this machine. Run:  outlook.py login <email>")
    return [e for e in feeds if e in known], missing


def cmd_raw(cfg, args):
    email = args.account or next(iter(cfg.get("accounts", {})), None)
    if not email:
        sys.exit("No account. Pass --account or configure one.")
    token = access_token(cfg, email)
    print(json.dumps(graph_get(token, args.path), indent=2, ensure_ascii=False))


def has_unsubscribe(msg):
    """The one bulk signal this script cuts on: RFC 2369 List-Unsubscribe, which every
    legitimate marketing sender sets and ordinary correspondence does not.

    It does nearly all of the bulk cut on its own (README.md has the measurement). It is a
    cost-saver rather than a relevance filter - anything it misses is judged, and
    `--include-bulk` turns it off.

    **There is deliberately no sender-name backstop.** Matching `noreply`, `notification`
    and the like on the local part is the exact exclusion `para-shared/connectors.md`
    forbids by default for every mailbox source, this one included: the transactional mail
    a vault most wants - a domain or DNS action-required notice, a tax filing alert, an
    invoice, a payment receipt, a booking confirmation - is nearly always sent from a
    `noreply@` address, so the pattern drops precisely what the vault exists to catch, and
    drops it invisibly, while earning little, because the shops write from `hello@` and
    `news@`. A mailbox that is
    measurably mostly bot mail is narrowed by naming that application's own domain in the
    vault's own rules, where the narrowing stays visible, never by a blanket rule here.
    """
    for h in msg.get("internetMessageHeaders") or []:
        if (h.get("name") or "").lower() in ("list-unsubscribe", "list-unsubscribe-post"):
            return True
    return False


def cmd_fetch(cfg, args):
    """Emit candidates as JSON on stdout and write NOTHING.

    The point of the whole script, and since the removal of `sync` the only way mail leaves
    it. The candidates go to a skill, which judges them against the vault's own `Relevant
    when` rules exactly as it judges mail from a Gmail connector, and writes only what
    survives. The reading happens here; the decision happens where the context is.

    stdout is pure JSON so a caller can parse it; every human-readable line goes to stderr.
    """
    feeds, missing = resolve_feeds(cfg, args.account)

    records, scanned_total, bulk_total, msg_total = [], 0, 0, 0
    failed = []
    for email in feeds:
        try:
            # The owner's own addresses, so a caller can tell a counterparty from the person
            # whose mailbox this is. Every message here is to or from them, so a rule that
            # matches on contact identity matches ALL of it unless it knows to skip them.
            acct = cfg["accounts"][email]
            owner = {email.lower()} | {a.lower() for a in acct.get("self", [])}
            token_account, root = mailbox_route(cfg, email)
            token = access_token(cfg, token_account)
            msgs = fetch_messages(token, args.days, root)
        except (Exception, SystemExit) as e:
            # One unusable mailbox must not cost the run the ones already read. Nothing is
            # emitted until the end, so an exit here discarded every earlier mailbox and
            # printed no JSON at all - the failure resolve_feeds is written against, one
            # level down. mailbox_route and access_token both exit, so SystemExit is in
            # scope, exactly as in cmd_search.
            failed.append(email)
            print(f"{email}  FETCH FAILED: {e}", file=sys.stderr)
            continue
        scanned_total += len(msgs)
        bulk = 0
        # Grouped by conversation, insertion-ordered, so the records come back in the order
        # the mailbox handed them over rather than in whatever order a dict happens to hold.
        threads = {}
        for m in msgs:
            # The flag first: with --include-bulk the header scan is work whose result is
            # thrown away, and the sender fields below are built for messages about to be
            # skipped - which, per the measurement above, is most of them.
            if not args.include_bulk and has_unsubscribe(m):
                bulk += 1
                continue
            frm = (m.get("from") or {}).get("emailAddress") or {}
            address = (frm.get("address") or "").lower()
            # Fall back to the message id when Graph omits conversationId, which it does
            # often enough to matter. Keyed on the missing value instead, every such message
            # lands in one bucket and N unrelated ones collapse into a single candidate:
            # the same bug as ungrouped mail, inverted, and losing items rather than
            # multiplying them.
            key = m.get("conversationId") or m.get("id")
            threads.setdefault(key, []).append({
                "id": m.get("id"),
                "message_id": m.get("internetMessageId"),
                "received": m.get("receivedDateTime"),
                "from_name": frm.get("name") or "",
                "from": address,
                "from_owner": address in owner,
                "to": [p["emailAddress"]["address"] for p in (m.get("toRecipients") or [])
                       if p.get("emailAddress", {}).get("address")],
                "cc": [p["emailAddress"]["address"] for p in (m.get("ccRecipients") or [])
                       if p.get("emailAddress", {}).get("address")],
                "subject": m.get("subject") or "(no subject)",
                "preview": " ".join((m.get("bodyPreview") or "").split()),
                "link": m.get("webLink"),
            })
        kept = len(msgs) - bulk      # every non-bulk message lands in exactly one thread
        msg_total += kept
        for key, group in threads.items():
            # Newest first, and by date rather than by arrival: Graph orders newest-first
            # today, but a grouping that depends on that silently inverts the day a page
            # boundary or a re-sort hands them over in another order.
            group.sort(key=lambda x: x["received"] or "", reverse=True)
            newest = group[0]
            records.append({
                "account": email,
                **newest,
                "thread_id": key,
                "message_count": len(group),
                # Everyone who WROTE on the thread, minus the mailbox owner. The caller's
                # contact rule matches a counterparty, and reading only the newest message
                # hides that counterparty the moment the owner replies last - the most
                # ordinary thing a live thread does. Senders only, never recipients: routing
                # on who received a message says nothing about whose business it is.
                "participants": sorted({x["from"] for x in group
                                        if x["from"] and not x["from_owner"]}),
                "messages": group,
            })
        bulk_total += bulk
        print(f"{email}  last {args.days}d: scanned {len(msgs)}, "
              f"{bulk} bulk skipped, {kept} candidates"
              f" in {len(threads)} thread{'' if len(threads) == 1 else 's'}", file=sys.stderr)

    if missing:
        print(f"! {len(missing)} mailbox(es) skipped (not logged in here): "
              f"{', '.join(missing)}", file=sys.stderr)
    if failed:
        print(f"! {len(failed)} mailbox(es) failed and were skipped: "
              f"{', '.join(failed)}", file=sys.stderr)
    print(f"total: {scanned_total} scanned, {bulk_total} bulk skipped, "
          f"{msg_total} messages in {len(records)} candidate threads. "
          f"Read-only: nothing was written.", file=sys.stderr)

    json.dump(records, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def cmd_search(cfg, args):
    """Ad-hoc lookup. Read-only by construction: prints, never writes.

    Distinct from `fetch` in what it is for rather than in what it writes, since neither
    writes anything. `fetch` walks a recent window so a skill can triage it; this asks one
    question of the whole mailbox, at any depth, and answers it on screen. It does not
    ignore the vault's account list: it reads only the mailboxes that feed this vault, so a
    work-vault session never prints personal mail. `--all-mailboxes` widens it.
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
            token_account, root = mailbox_route(cfg, email)
            hits = search_messages(access_token(cfg, token_account), args.query,
                                   limit=args.limit, root=root)
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
    p = argparse.ArgumentParser(description="Read Outlook/Hotmail mail for a vault. Never writes.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("accounts")

    lg = sub.add_parser("login")
    lg.add_argument("email")
    lg.add_argument("--client-id", help="Entra app for THIS mailbox (default: the machine-wide one). "
                                        "A work/school mailbox needs its own tenant's app")
    lg.add_argument("--device-code", action="store_true",
                    help="sign in with the device-code flow instead of a browser. Needed "
                         "where the app has no http://localhost redirect URI; refused by "
                         "security defaults on newer tenants")
    lg.add_argument("--shared", action="store_true",
                    help="also consent to Mail.Read.Shared, so this account can read shared "
                         "mailboxes that name it as their `via`. Only needed when the shared "
                         "entry does not exist yet; once it does, the scope is derived")
    lg.add_argument("--authority", help="tenant id for THIS mailbox, or 'common' / 'consumers' "
                                        "(default: the machine-wide setting)")

    fe = sub.add_parser("fetch", help="emit candidate messages as JSON for a skill to judge (read-only)")
    fe.add_argument("--account", help="only this account (default: this vault's accounts)")
    fe.add_argument("--days", type=int, default=7, help="lookback window (default 7)")
    fe.add_argument("--include-bulk", action="store_true",
                    help="keep messages carrying a List-Unsubscribe header instead of skipping them")

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

    # No default subcommand. There used to be one, so the /para-triage sync-script convention
    # (`<script> --write`) reached `sync`; this script is a fetch source now and that
    # convention no longer points at it. An explicit verb beats a bare call that silently
    # picks a behaviour, especially for a script that reads mailboxes.
    args = p.parse_args()
    cfg = load_config()
    {"accounts": cmd_accounts, "login": cmd_login, "fetch": cmd_fetch,
     "search": cmd_search, "raw": cmd_raw}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
