#!/usr/bin/env python3
"""plaud.py - pull recent Plaud recordings (AI summary + transcript) into a vault's triage/.
para-os-integration: plaud 2026.10.01 - see CHANGELOG.md; /para-upgrade reports drift against this line.

Plaud (plaud.ai) is a wearable recorder (NotePin, Note); its app transcribes and summarises every
recording. Drop this file in <vault>/resources/scripts/ and run it there. By default every
recent recording is written to THIS vault's triage/ as a dated Markdown note for /para-triage.
    py plaud.py login           # one-time browser sign-in; tokens saved under ~/.paraos
    py plaud.py                 # DRY RUN: shows what it would write, touches nothing in the vault
    py plaud.py --write         # actually create the notes
    py plaud.py --days 14       # override the 30-day look-back window
    py plaud.py --dump <id>     # print one recording's raw API JSON (see "Response shape")

This file holds nothing vault-specific: the routing table lives in plaud.config.json beside it,
the tokens in ~/.paraos/secrets/plaud.json, and the vault is derived from this copy's own path.
So an installed copy re-syncs by straight file copy - never edit this script to configure a vault.

Auth: OAuth 2 with PKCE against the public client of Plaud's own CLI (`@plaud-ai/cli`, no client
secret), on a loopback redirect at http://localhost:8199/auth/callback. The access token refreshes
on its own; a refused refresh means `login` again. The script only ever GETs the API.
See integrations/plaud/README.md for setup and the multi-vault routing config.

Response shape, as `@plaud-ai/cli` 0.3.14 reads it: GET /open/third-party/files/?page=&page_size=
gives {data: [{id, name, created_at, duration (ms)}]}, newest first. GET .../files/<id> adds
`start_at`, `source_list[]` (blocks by `data_type`: `transaction` is the transcript,
`transaction_polish` a cleaned copy) and `note_list[]` (`auto_sum_note` is the AI summary, titled
by `data_title`). A block's text is inline in `data_content` or behind a pre-signed `data_link`. A
transcript is a JSON list of {start_time (ms), end_time, speaker, content}.
A recording missing its transcript or its summary is HELD (not written, not ledgered, retried next
run) until HOLD_HOURS after Plaud received it, then written with whatever exists, so an
untranscribed recording cannot hold forever. A transcript in a shape the reader cannot parse holds
until it is fixed, with the `--dump` command that shows it.
Standard library only, Python 3.9+.
"""
import argparse
import base64
import email.utils
import hashlib
import http.client
import http.server
import itertools
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = os.environ.get("PLAUD_API_BASE") or "https://platform.plaud.ai/developer/api"
AUTH_URL = "https://web.plaud.ai/platform/oauth"
TOKEN_URL = API + "/oauth/third-party/access-token"
REFRESH_URL = API + "/oauth/third-party/access-token/refresh"
# The public client id of Plaud's own CLI: an identifier, not a secret.
CLIENT_ID = os.environ.get("PLAUD_CLIENT_ID") or "client_f9e0b214-c11f-434b-8b95-c4497d1feb81"
REDIRECT_PORT = 8199
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/auth/callback"
LOGIN_TIMEOUT = 300  # seconds the sign-in waits for the browser to come back

# Integration state lives under ~/.paraos (override with PARAOS_HOME); see ~/.paraos/README.md.
PARAOS_HOME = Path(os.environ.get("PARAOS_HOME") or Path.home() / ".paraos")
AUTH = PARAOS_HOME / "secrets" / "plaud.json"
STATE = PARAOS_HOME / "data" / "plaud" / "synced.json"

# This copy lives in <vault>/resources/scripts/, so the vault root is two levels up.
HERE = Path(__file__).resolve().parent
VAULT_ROOT = HERE.parent.parent
CONFIG_PATH = HERE / "plaud.config.json"

# "." in a route means the vault this copy lives in. A vault's folder name is machine-local
# (a synced library is named in the sync client's display language), so the config never
# names its own vault literally. Same rule and reasoning as granola and pocket.
SELF = "."

HOLD_HOURS = 24
# Plaud sits behind Cloudflare, which refuses Python's default `Python-urllib` agent (error 1010).
UA = "para-os-plaud/1.0"


# ─── config ────────────────────────────────────────────────────────────────────────────────
# plaud.config.json beside this script. Never secret. Absent or empty = single-vault mode:
# every recording lands in THIS vault's triage/, so a vault that is the only destination needs
# no file and no title prefixes.
#   { "meetings_subdir": "triage",
#     "route": { "Acme": ".", "Home": "Home" } }
# `route` fans recordings out by TITLE PREFIX, the same rule as granola and pocket, so one naming
# habit serves all three: "Acme - Kickoff" goes to this vault, "Home - Contractor" to the sibling
# vault "Home", and the prefix is dropped from the filename. Prefixes match case-insensitively.

def load_config(path):
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        # Never fall through to {}: an unreadable config silently means single-vault mode,
        # which writes every other vault's recordings into this one. Stop instead.
        sys.exit(f"plaud.config.json is present but unreadable: {e}\n  {path}")
    if not isinstance(parsed, dict):
        sys.exit(f"plaud.config.json must be a JSON object (got {type(parsed).__name__}).\n  {path}")
    if not isinstance(parsed.get("route", {}), dict):
        sys.exit(f"plaud.config.json: \"route\" must be an object of title prefix -> vault.\n  {path}")
    return parsed


def build_routes(route, vault_name, parent):
    """Lowercased prefix -> vault name, plus one warning per target that resolves nowhere."""
    routes, warnings = {}, []
    for prefix, target in route.items():
        vault = vault_name if target == SELF else target
        routes[prefix.lower()] = vault
        if vault != vault_name and not (parent / vault).is_dir():
            warnings.append(f"! route \"{prefix}\" -> \"{target}\": no vault of that name beside this one, "
                            f"and it is not this vault (\"{vault_name}\"). Recordings with that prefix will "
                            f"count as other vaults' and be skipped. Use \".\" to mean this vault.")
    return routes, warnings


PREFIX = re.compile(r"^\s*([A-Za-z0-9]+)\s*-\s*")  # granola's prefix rule, character for character


def resolve(title, routes, vault_root, only_vault, subdir):
    """Where a recording goes: {"vault", "dir", "desc"}, {"unrouted": prefix} or {"elsewhere": True}.
    Single-vault mode (no routes) takes everything, under its full title."""
    if not routes:
        return {"vault": vault_root.name, "dir": vault_root / subdir, "desc": title}
    m = PREFIX.match(title)
    vault = routes.get(m.group(1).lower()) if m else None
    if not vault:
        return {"unrouted": m.group(1) if m else "none"}
    if only_vault and vault != only_vault:
        return {"elsewhere": True}
    # PARENT/VAULT_NAME is VAULT_ROOT, so one join serves this vault and every sibling.
    return {"vault": vault, "dir": vault_root.parent / vault / subdir, "desc": title[m.end():] or title}


# ─── reading Plaud's payload ──────────────────────────────────────────────────────────────

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?\s*(Z|[+-]\d{2}:?\d{2})?$")


def parse_when(s):
    """ISO timestamp -> aware datetime. No offset means UTC, the CLI's own rule. Hand-parsed
    because Python 3.9's fromisoformat rejects `Z` and 9-digit fractions."""
    m = _ISO.match(str(s or "").strip())
    if not m:
        return None
    y, mo, d, h, mi, sec, frac, tz = m.groups()
    micro = int((frac or "0")[:6].ljust(6, "0"))
    if not tz or tz == "Z":
        off = timezone.utc
    else:
        sign = 1 if tz[0] == "+" else -1
        hh, mm = int(tz[1:3]), int(tz[-2:])
        off = timezone(sign * timedelta(hours=hh, minutes=mm))
    return datetime(int(y), int(mo), int(d), int(h), int(mi), int(sec or 0), micro, off)


def stamp(ms):
    s = int(ms) // 1000
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"[{h}:{m:02d}:{sec:02d}]" if h else f"[{m:02d}:{sec:02d}]"


def transcript_md(raw):
    """Plaud's segment list -> Markdown, one paragraph per speaker turn, each opening on its
    timestamp. Plain text passes through. None when the text is JSON of a shape this does not
    read, so the recording holds rather than being written as if it had no transcript."""
    if not raw or not raw.strip():
        return ""
    try:
        segs = json.loads(raw)
    except ValueError:
        return raw.strip()
    if not isinstance(segs, list):
        return None
    turns = []  # [start, speaker, [texts]]
    for seg in segs:
        if not isinstance(seg, dict):
            continue
        text = str(seg.get("content") or "").strip()
        if not text:
            continue
        spk = str(seg.get("speaker") or "").strip() or None
        start = seg.get("start_time")
        if isinstance(start, bool) or not isinstance(start, (int, float)):
            start = None
        if turns and spk and turns[-1][1] == spk:
            turns[-1][2].append(text)
        else:
            turns.append([start, spk, [text]])
    return "\n\n".join((f"{stamp(st)} " if st is not None else "") + (f"**{spk}:** " if spk else "") + " ".join(txt)
                       for st, spk, txt in turns)


def summaries(detail):
    """The AI summaries in `note_list` -> [(title or None, markdown)], empties dropped."""
    out = []
    for note in detail.get("note_list") or []:
        if isinstance(note, dict) and note.get("data_type") == "auto_sum_note":
            body = block_text(note).strip()
            if body:
                out.append((str(note.get("data_title") or "").strip() or None, body))
    return out


def demote(md, base=3):
    """Renumber heading levels to consecutive, starting at `base`, so they nest under ## Summary."""
    levels = sorted({len(h) for h in re.findall(r"^(#{1,6}) ", md, flags=re.M)})
    if not levels:
        return md
    remap = {lvl: min(6, base + i) for i, lvl in enumerate(levels)}
    return re.sub(r"^(#{1,6}) ", lambda m: "#" * remap[len(m.group(1))] + " ", md, flags=re.M)


# ─── writing ──────────────────────────────────────────────────────────────────────────────

# Illegal characters become a space rather than nothing, so "Q3/Q4 plan" stays two words.
# Leading/trailing spaces and dots go: Windows strips both. Matches granola's sanitize.
_EDGES = re.compile(r"^[ .]+|[ .]+$")


def sanitize(s):
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", str(s or ""))
    s = _EDGES.sub("", re.sub(r"\s+", " ", s))
    return _EDGES.sub("", s[:80])


def write_atomic(path, text):
    """Temp file beside the target, then replace: a run that dies mid-write leaves the old file or
    none, never a partial one that the next run takes as already written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def load_ledger():
    if not STATE.exists():
        return {}
    try:
        ledger = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        ledger = e
    if not isinstance(ledger, dict):
        sys.exit(f"The dedup ledger is unreadable ({ledger}):\n  {STATE}\nRepair or restore it: deleting it "
                 "re-imports every recording in the look-back window whose note has left its folder.")
    return ledger


def record(key, value):
    """Add one ledger entry. Every vault's copy shares the file, so re-read and merge rather than
    write back what this run loaded."""
    ledger = load_ledger()
    ledger[key] = value
    write_atomic(STATE, json.dumps(ledger, indent=2, ensure_ascii=False))


def note_id(path):
    try:
        with path.open(encoding="utf-8") as f:
            for _, line in zip(range(15), f):
                if line.startswith("plaud_id:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def pick_path(folder, when, title, fid):
    """(path, already_written). Recordings sharing a date and title get an id suffix, the first
    six characters, then the whole id, then a counter, each taken only when the file there is
    absent or carries this recording's id, so no recording is dropped as another's duplicate."""
    base = f"{when:%Y%m%d} {sanitize(title) or 'untitled'}"
    full = sanitize(fid)
    for i in itertools.count():
        suffix = ("", f" ({fid[:6]})", f" ({full})")[i] if i < 3 else f" ({full} {i - 1})"
        p = folder / f"{base}{suffix}.md"
        if not p.exists():
            return p, False
        if note_id(p) == fid:
            return p, True


def render_note(title, when, fid, minutes, summ, transcript):
    front = ["---",
             f"title: {json.dumps(title, ensure_ascii=False)}",  # quoted: a colon in a title breaks YAML
             f"date: {when:%Y-%m-%d}",
             f"plaud_id: {fid}",
             "source: plaud",
             f"duration_min: {minutes}" if minutes else None,
             "---"]
    if summ:
        summary = demote(summ[0][1], 3) if len(summ) == 1 else "\n\n".join(
            f"### {t or 'Summary'}\n\n{demote(b, 4)}" for t, b in summ)
    else:
        summary = "_(no summary available)_"
    body = [f"# {title}", f"_{when:%Y-%m-%d %H:%M}" + (f" · {minutes} min_" if minutes else "_"), "",
            "## Summary", "", summary, "",
            "## Transcript", "", transcript or "_(no transcript available)_", ""]
    return "\n".join([x for x in front if x is not None] + [""] + body)


# ─── sign-in and tokens ───────────────────────────────────────────────────────────────────

def pkce_pair(verifier=None):
    """(code_verifier, S256 code_challenge), RFC 7636."""
    verifier = verifier or secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorize_url(challenge, state):
    return AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, "response_type": "code",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state})


def post_form(url, fields, basic=False):
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json", "User-Agent": UA}
    if basic:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{CLIENT_ID}:".encode()).decode()
    req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def save_tokens(data):
    """Keep the access and refresh tokens, the expiry as an absolute time. Owner-only on disk."""
    if not isinstance(data, dict) or not isinstance(data.get("access_token"), str) or not data["access_token"]:
        sys.exit("Plaud's token response carried no access_token. Run `py plaud.py login` again.")
    try:
        expires_at = time.time() + float(data["expires_in"]) if data.get("expires_in") else None
    except (TypeError, ValueError):
        expires_at = None
    tok = {"access_token": data["access_token"], "refresh_token": data.get("refresh_token"),
           "expires_at": expires_at}
    AUTH.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(AUTH.parent, 0o700)
    write_atomic(AUTH, json.dumps(tok, indent=2))
    os.chmod(AUTH, 0o600)
    return tok


def callback_handler(state, got):
    """The loopback redirect's handler: the callback's query lands in `got`. Any other path (a
    favicon, a prefetch) gets a 404 and the wait goes on."""
    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parts = urllib.parse.urlsplit(self.path)
            if parts.path != "/auth/callback":
                self.send_error(404)
                return
            got.update((k, v[0]) for k, v in urllib.parse.parse_qs(parts.query).items())
            ok = got.get("code") and got.get("state") == state
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(("<p>Sign-in received. You can close this window and return to the terminal.</p>" if ok else
                              "<p>Sign-in failed. Run the login again.</p>").encode("utf-8"))

        def log_message(self, *a):
            pass
    return Callback


def login(port=REDIRECT_PORT, open_browser=webbrowser.open, timeout=LOGIN_TIMEOUT):
    """One-time browser sign-in: authorization code with PKCE on a loopback redirect."""
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    url = authorize_url(challenge, state)
    got = {}
    try:
        srv = http.server.HTTPServer(("127.0.0.1", port), callback_handler(state, got))
    except OSError as e:
        sys.exit(f"Cannot listen on localhost:{port} for Plaud's sign-in redirect ({e}). "
                 "Close whatever holds that port and run the login again.")
    with srv:
        srv.timeout = 1  # handle_request() returns each second, so the deadline is checked
        print(f"Opening Plaud sign-in in your browser. If nothing opens, visit:\n  {url}\n", flush=True)
        open_browser(url)
        deadline = time.monotonic() + timeout
        while not got and time.monotonic() < deadline:
            srv.handle_request()
    if not got:
        sys.exit(f"Sign-in timed out after {timeout} seconds with no answer from the browser.")
    if got.get("error") or not got.get("code"):
        sys.exit(f"Sign-in failed: {got.get('error_description') or got.get('error') or 'no code returned'}")
    if got.get("state") != state:
        sys.exit("Sign-in failed: the redirect does not belong to this sign-in (state mismatch).")
    try:
        data = post_form(TOKEN_URL, {"code": got["code"], "redirect_uri": REDIRECT_URI,
                                     "code_verifier": verifier, "state": state}, basic=True)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except (OSError, AttributeError, ValueError):
            detail = ""
        sys.exit(f"Token exchange failed: HTTP {e.code} {detail}".rstrip())
    except (OSError, ValueError, http.client.HTTPException) as e:
        sys.exit(f"Token exchange failed: {e}")
    save_tokens(data)
    print(f"Signed in. Tokens saved to {AUTH}")


def access_token():
    """The saved access token, refreshed first when it expires within a minute."""
    if not AUTH.exists():
        sys.exit(f"Not signed in to Plaud. Run once:  py {Path(__file__).name} login")
    try:
        tok = json.loads(AUTH.read_text(encoding="utf-8"))
        if not isinstance(tok, dict) or not tok.get("access_token"):
            raise ValueError("no access_token")
    except (OSError, ValueError) as e:
        sys.exit(f"{AUTH} is unreadable: {e}. Run `py plaud.py login` again.")
    expires_at = tok.get("expires_at")
    if isinstance(expires_at, (int, float)) and time.time() > expires_at - 60:
        if not tok.get("refresh_token"):
            sys.exit("The Plaud sign-in has expired and holds no refresh token. Run `py plaud.py login` again.")
        try:
            data = post_form(REFRESH_URL, {"refresh_token": tok["refresh_token"]})
        except urllib.error.HTTPError as e:
            sys.exit(f"Plaud refused the token refresh (HTTP {e.code}). Run `py plaud.py login` again.")
        except (OSError, ValueError, http.client.HTTPException) as e:
            sys.exit(f"Could not refresh the Plaud token, nothing written: {e}")
        if isinstance(data, dict):
            data.setdefault("refresh_token", tok["refresh_token"])
        tok = save_tokens(data)
    return tok["access_token"]


# ─── Plaud API (GET only) ─────────────────────────────────────────────────────────────────

class PlaudError(RuntimeError):
    """A request that still failed after retries, or a response that is not Plaud's JSON."""


RETRIES = 3
PAGE_SIZE = 50
MAX_PAGES = 40  # 2000 recordings in one window is a runaway loop, not a backlog


def retry_after(value, default):
    """Seconds to wait, capped at 60, from a Retry-After header: either seconds or an HTTP date."""
    try:
        return max(0, min(int(str(value).strip()), 60))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(str(value))
        return max(0, min(int((when - datetime.now(timezone.utc)).total_seconds()), 60))
    except (TypeError, ValueError, IndexError, OverflowError):
        return default


def api_get(token, path, params=None):
    """GET one API path -> parsed JSON. A rate limit, a server error or a network failure is
    retried, then raised as PlaudError, as is a response that is not JSON. A refused token stops."""
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(RETRIES + 1):
        wait = 2 ** (attempt + 1) if attempt < RETRIES else None
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + token, "Accept": "application/json", "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit(f"Plaud refused the sign-in (HTTP {e.code}). Run `py plaud.py login` again.")
            if wait and (e.code == 429 or e.code >= 500):
                time.sleep(retry_after((e.headers or {}).get("Retry-After"), wait))
                continue
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except (OSError, AttributeError, ValueError):
                detail = ""
            raise PlaudError(f"GET {path} -> HTTP {e.code}" + (f": {detail}" if detail else ""))
        except (OSError, http.client.HTTPException) as e:
            if wait:
                time.sleep(wait)
                continue
            raise PlaudError(f"GET {path}: {getattr(e, 'reason', None) or str(e) or type(e).__name__}")
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            raise PlaudError(f"GET {path}: response is not JSON")


def fetch_text(url):
    """A block's `data_link`: a pre-signed https URL, fetched without the bearer token."""
    host = urllib.parse.urlsplit(url).netloc
    if not url.lower().startswith("https://"):
        raise PlaudError(f"data_link is not an https URL ({url.split(':', 1)[0]}:)")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
            return r.read(20_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise PlaudError(f"GET data_link at {host} -> HTTP {e.code}")
    except (OSError, http.client.HTTPException) as e:
        raise PlaudError(f"GET data_link at {host}: {getattr(e, 'reason', None) or str(e) or type(e).__name__}")


def block_text(block):
    """A block's text, inline or behind its link; empty when it has neither."""
    if not isinstance(block, dict):
        return ""
    content, link = block.get("data_content"), block.get("data_link")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(link, str) and link:
        return fetch_text(link)
    return ""


def list_files(token, cutoff):
    """Every recording Plaud lists back to `cutoff`. The listing is newest first, so a page that
    reaches past the cutoff, or comes back short, is the last one read."""
    out = []
    for page in range(1, MAX_PAGES + 1):
        body = api_get(token, "/open/third-party/files/", {"page": page, "page_size": PAGE_SIZE})
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list):
            raise PlaudError("GET /open/third-party/files/: response has no list of recordings")
        items = [f for f in data if isinstance(f, dict)]
        out.extend(items)
        if len(data) < PAGE_SIZE or any((parse_when(f.get("created_at")) or cutoff) < cutoff for f in items):
            return out
    print(f"! stopped after {MAX_PAGES} pages ({len(out)} recordings): the rest of the window was not "
          f"read. Narrow --days.", file=sys.stderr)
    return out


def get_file(token, fid):
    path = f"/open/third-party/files/{urllib.parse.quote(fid)}"
    body = api_get(token, path)
    data = body.get("data", body) if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise PlaudError(f"GET {path}: response has no recording object")
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pull recent Plaud recordings into triage/ (dry run by default).")
    ap.add_argument("command", nargs="?", choices=["login"], help="login: one-time browser sign-in")
    ap.add_argument("--write", action="store_true", help="actually create the notes")
    ap.add_argument("--days", type=int, default=30, help="look-back window (default 30)")
    ap.add_argument("--vault", help="multi-vault: write this routed vault instead of this one")
    ap.add_argument("--all", action="store_true", help="multi-vault: write every routed vault")
    ap.add_argument("--dump", metavar="ID", help="print one recording's raw JSON and exit")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    if args.command == "login":
        return login()

    cfg = load_config(CONFIG_PATH)
    subdir = cfg.get("meetings_subdir") or "triage"
    vault_name = VAULT_ROOT.name
    routes, warnings = build_routes(cfg.get("route") or {}, vault_name, VAULT_ROOT.parent)
    for w in warnings:
        print(w, file=sys.stderr)
    target = vault_name if args.vault == SELF else args.vault
    only = target or (None if args.all else vault_name)
    if args.vault:
        # A named target is an explicit ask: nothing routing there must fail loudly, not
        # skip every recording and report success having written nothing.
        if not routes:
            print(f"! --vault \"{args.vault}\" ignored: plaud.config.json has no \"route\", so every "
                  f"recording goes to this vault (\"{vault_name}\").", file=sys.stderr)
        elif target not in set(routes.values()):
            sys.exit(f"! --vault \"{args.vault}\": nothing routes there. This config routes to: "
                     f"{', '.join(sorted(set(routes.values())))}.")

    token = access_token()
    if args.dump:
        try:
            body = api_get(token, f"/open/third-party/files/{urllib.parse.quote(args.dump)}")
        except PlaudError as e:
            sys.exit(f"! {e}")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return

    state = load_ledger()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=args.days)
    try:
        listed = [(parse_when(f.get("created_at")), f) for f in list_files(token, cutoff)]
    except PlaudError as e:
        sys.exit(f"! Could not list Plaud recordings, nothing written: {e}")
    undated = [f for c, f in listed if not c]
    recent = sorted([(c, f) for c, f in listed if c and c >= cutoff], key=lambda x: x[0], reverse=True)
    mode = "WRITE" if args.write else "DRY RUN"
    scope = f" · routing {'-> ' + only if only else 'all vaults'}" if routes else ""
    print(f"{mode} · last {args.days} days · {len(recent) + len(undated)} recordings{scope}\n")

    n = dict.fromkeys(("written", "recorded", "skipped", "pending", "unreadable", "failed", "undated",
                       "unrouted", "elsewhere"), 0)
    for created, f in [(None, f) for f in undated] + recent:
        fid, title = str(f.get("id")), str(f.get("name") or "")
        label = f"{f'{created.astimezone():%Y-%m-%d}' if created else '(no date)':<10}  {(title or '(untitled)')[:34]:<35}"
        r = resolve(title, routes, VAULT_ROOT, only, subdir)
        # Another vault's recording: silent per recording, but counted, so the closing line adds
        # up to the header's count and a misrouted config cannot pass for a quiet week.
        if r.get("elsewhere"):
            n["elsewhere"] += 1
            continue
        if not created:
            print(f"  !!  {label}UNDATED (no created_at it can parse); inspect: py plaud.py --dump {fid}")
            n["undated"] += 1
            continue
        if "unrouted" in r:
            print(f"  ??  {label}-> UNROUTED (prefix: {r['unrouted']})")
            n["unrouted"] += 1
            continue

        vault = r["vault"]
        if state.get(f"{fid}@{vault}"):
            print(f"  ==  {label}-> {vault}/{subdir} (exists, skip)")
            n["skipped"] += 1
            continue
        try:
            detail = get_file(token, fid)
            blocks = {b.get("data_type"): b for b in detail.get("source_list") or [] if isinstance(b, dict)}
            raw = block_text(blocks.get("transaction")) or block_text(blocks.get("transaction_polish"))
            summ = summaries(detail)
        except PlaudError as e:
            print(f"  xx  {label}FAILED ({e}) - retried next run")
            n["failed"] += 1
            continue
        when = (parse_when(detail.get("start_at")) or created).astimezone()
        dest, exists = pick_path(r["dir"], when, r["desc"], fid)
        if exists:
            # This recording's note, written by a run that stopped before ledgering it: ledger it
            # now, or it is imported again once /para-triage files the note out of this folder.
            print(f"  ==  {label}-> {vault}/{subdir}/{dest.name} (exists, {'recorded' if args.write else 'would record'})")
            if args.write:
                record(f"{fid}@{vault}", str(dest))
            n["recorded"] += 1
            continue

        transcript = transcript_md(raw)
        if transcript is None:
            print(f"  !!  {label}HELD, unreadable (transcript in a shape the reader cannot parse) - retried "
                  f"next run; inspect: py plaud.py --dump {fid}")
            n["unreadable"] += 1
            continue
        missing = [name for name, have in (("transcript", transcript), ("summary", summ)) if not have]
        if missing and now - created < timedelta(hours=HOLD_HOURS):
            print(f"  ..  {label}HELD, no {' or '.join(missing)} yet - retried next run, "
                  f"written as it stands once {HOLD_HOURS}h old")
            n["pending"] += 1
            continue

        dur = f.get("duration") or detail.get("duration")  # milliseconds
        minutes = round(dur / 60000) if isinstance(dur, (int, float)) and not isinstance(dur, bool) and dur > 0 else None
        print(f"  {'->' if args.write else '+ '}  {label}-> {vault}/{subdir}/{dest.name}  "
              f"[sum {sum(len(b) for _, b in summ)}c · tr {len(transcript)}c]")
        if args.write:
            write_atomic(dest, render_note(title or "(untitled)", when, fid, minutes, summ, transcript))
            record(f"{fid}@{vault}", str(dest))
        n["written"] += 1

    tail = f" · unrouted: {n['unrouted']} · other vaults: {n['elsewhere']}" if routes else ""
    recorded = f" · {'recorded' if args.write else 'would record'}: {n['recorded']}" if n["recorded"] else ""
    print(f"\n{'wrote' if args.write else 'would write'}: {n['written']}{recorded} · skipped(exists): {n['skipped']} · "
          f"held(pending): {n['pending']} · held(unreadable): {n['unreadable']} · failed: {n['failed']} · "
          f"undated: {n['undated']}{tail}")
    if not args.write:
        print("Re-run with --write to create the files.")


if __name__ == "__main__":
    main()
