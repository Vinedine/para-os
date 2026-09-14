#!/usr/bin/env python3
"""pocket.py - pull recent Pocket recordings (AI summary + transcript) into a vault's triage/.
para-os-integration: pocket 2026.09.03 - see CHANGELOG.md; /para-upgrade reports drift against this line.

Pocket (heypocket.com) is a wearable recorder; its app transcribes and summarises every
conversation. Drop this file in <vault>/resources/scripts/ and run it there. By default every
recent recording is written to THIS vault's triage/ as a dated Markdown note for /para-triage.
    py pocket.py                # DRY RUN: shows what it would write, touches nothing
    py pocket.py --write        # actually create the notes
    py pocket.py --days 14      # override the 30-day look-back window
    py pocket.py --dump <id>    # print one recording's raw API JSON (see "Response shape")

This file holds nothing vault-specific: the routing table lives in pocket.config.json beside it,
the API key in ~/.paraos/secrets/pocket.json, and the vault is derived from this copy's own path.
So an installed copy re-syncs by straight file copy - never edit this script to configure a vault.

Auth: a Pocket API key (Pocket app -> Settings -> Developer -> API Keys, starts with `pk_`),
stored as {"api_key": "pk_..."} in ~/.paraos/secrets/pocket.json. The script only ever GETs.
See integrations/pocket/README.md for setup and the multi-vault routing config.

Response shape. Pocket's public API documents `transcript` and `summarizations` as untyped. The
shape seen on a live account is read first: `transcript.segments[]` of
{start, end, text}, often with no speaker labels, and per summarization id a
`v2.summary.markdown` plus `v2.actionItems.actions[]`. Other plausible shapes are fallbacks.
A recording is HELD (not written, not ledgered, retried next run) while any status reports
processing, or when a field holds words none of the readers can parse or is blank under a status
not known to be final; the latter prints the `--dump` command that shows why.
Standard library only, Python 3.9+.
"""
import argparse
import email.utils
import http.client
import itertools
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://public.heypocketai.com/api/v1"

# Integration state lives under ~/.paraos (override with PARAOS_HOME); see ~/.paraos/README.md.
PARAOS_HOME = Path(os.environ.get("PARAOS_HOME") or Path.home() / ".paraos")
AUTH = PARAOS_HOME / "secrets" / "pocket.json"
STATE = PARAOS_HOME / "data" / "pocket" / "synced.json"

# This copy lives in <vault>/resources/scripts/, so the vault root is two levels up.
HERE = Path(__file__).resolve().parent
VAULT_ROOT = HERE.parent.parent
CONFIG_PATH = HERE / "pocket.config.json"

# "." in a route means the vault this copy lives in. A vault's folder name is machine-local
# (a synced library is named in the sync client's display language), so the config never
# names its own vault literally. Same rule and reasoning as granola.
SELF = "."


# ─── config ────────────────────────────────────────────────────────────────────────────────
# pocket.config.json beside this script. Never secret. Absent or empty = single-vault mode:
# every recording lands in THIS vault's triage/.
#   { "meetings_subdir": "triage",
#     "route": { "Acme": ".", "Home": "Home" } }
# `route` fans recordings out by TITLE PREFIX, the same rule as granola, so one naming habit
# serves both: a recording titled "Acme - Kickoff" goes to this vault, "Home - Contractor" to
# the sibling vault "Home" (sibling vaults share one parent directory), and the prefix is
# dropped from the filename. Prefixes match case-insensitively. Pocket titles a recording
# itself, so the prefix is added by renaming it in the app; until then it lists as UNROUTED.

def load_config(path):
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        # Never fall through to {}: an unreadable config silently means single-vault mode,
        # which writes every other vault's recordings into this one. Stop instead.
        sys.exit(f"pocket.config.json is present but unreadable: {e}\n  {path}")
    if not isinstance(parsed, dict):
        sys.exit(f"pocket.config.json must be a JSON object (got {type(parsed).__name__}).\n  {path}")
    if not isinstance(parsed.get("route", {}), dict):
        sys.exit(f"pocket.config.json: \"route\" must be an object of title prefix -> vault.\n  {path}")
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


def tag_names(rec):
    out = []
    for t in rec.get("tags") or []:
        name = t.get("name") if isinstance(t, dict) else t
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return out


PREFIX = re.compile(r"^\s*([A-Za-z0-9]+)\s*-\s*")  # granola's prefix rule, character for character


def resolve(rec, routes, vault_root, only_vault, subdir):
    """Where a recording goes: {"vault", "dir", "desc"}, {"unrouted": prefix} or {"elsewhere": True}.
    Single-vault mode (no routes) takes everything, under its full title."""
    title = str(rec.get("title") or "")
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


# ─── reading Pocket's payload ─────────────────────────────────────────────────────────────

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?\s*(Z|[+-]\d{2}:?\d{2})?$")


def parse_when(s):
    """ISO timestamp -> aware datetime. No offset means UTC, which is what Pocket's API says it
    speaks. Hand-parsed because Python 3.9's fromisoformat rejects `Z` and 9-digit fractions."""
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


def recorded_at(rec, tz=None):
    """When the conversation happened, in local time (a 00:30 meeting two hours east of UTC is
    22:30 UTC the day before, and the filename's date is the one the operator remembers)."""
    when = parse_when(rec.get("recording_at")) or parse_when(rec.get("created_at"))
    return when.astimezone(tz) if when else None


TEXT_KEYS = ("markdown", "content", "text", "summary", "body", "output", "transcript")
TITLE_KEYS = ("title", "name", "template_name")
SEGMENT_LIST_KEYS = ("segments", "utterances", "items", "results", "entries")
SPEAKER_KEYS = ("speaker_name", "speaker", "speaker_label", "display_name", "speaker_id")


def prose(s):
    """A string found outside a text key counts as text only when it holds more than one word:
    a single token is an id or a status ("tr_123", "pending"), never a transcript or a summary."""
    return s.strip() if isinstance(s, str) and len(s.split()) > 1 else ""


def text_of(v, depth=0):
    """The first non-empty text under the known text keys, depth-limited. Never a JSON dump."""
    if v is None or depth > 4:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        for k in TEXT_KEYS:
            if k in v:
                t = text_of(v[k], depth + 1)
                if t:
                    return t
    return ""


def speaker_of(seg):
    for k in SPEAKER_KEYS:
        v = seg.get(k)
        if isinstance(v, dict):
            v = v.get("name") or v.get("display_name") or v.get("label")
        if isinstance(v, bool) or v is None or v == "":
            continue
        if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
            return f"Speaker {v}"
        if isinstance(v, str):
            return v.strip()
    return None


def stamp(seconds):
    s = int(seconds)
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"[{h}:{m:02d}:{sec:02d}]" if h else f"[{m:02d}:{sec:02d}]"


def transcript_md(t):
    """Transcript in whatever shape it arrives -> Markdown, one paragraph per turn, each opening on
    its timestamp when the segment carries one.

    Consecutive segments of one NAMED speaker merge into a turn. Unlabelled segments never merge:
    Pocket often skips speaker detection (`speakerStageStatus: skipped`), and merging on "no
    speaker" would put a whole meeting on a single line."""
    if not t:
        return ""
    if isinstance(t, str):
        return prose(t)
    if isinstance(t, dict):
        for k in SEGMENT_LIST_KEYS:
            if isinstance(t.get(k), list):
                return transcript_md(t[k])
        return text_of(t)
    if not isinstance(t, list):
        return ""
    turns = []  # [start, speaker, [texts]]
    for seg in t:
        if isinstance(seg, str):
            spk, text, start = None, prose(seg), None
        elif isinstance(seg, dict):
            spk, text, start = speaker_of(seg), text_of(seg), seg.get("start")
            if isinstance(start, bool) or not isinstance(start, (int, float)):
                start = None
        else:
            continue
        if not text:
            continue
        if turns and spk is not None and turns[-1][1] == spk:
            turns[-1][2].append(text)
        else:
            turns.append([start, spk, [text]])
    return "\n\n".join((f"{stamp(st)} " if st is not None else "") + (f"**{spk}:** " if spk else "") + " ".join(txt)
                       for st, spk, txt in turns)


def summary_items(s):
    """The summaries in `summarizations`: a string, one summary object, a list of them, or an
    object keyed by summarization id. Only objects are taken from a list or an id-keyed object."""
    if isinstance(s, str):
        return [s] if prose(s) else []
    if isinstance(s, dict):
        if any(k in s for k in TEXT_KEYS + ("v2",)):
            return [s]
        return [v for v in s.values() if isinstance(v, dict)]
    return [v for v in s if isinstance(v, dict)] if isinstance(s, list) else []


def summary_body(it):
    """Pocket's shape, seen on a live account: {"v2": {"summary": {"markdown": ...}}}, one such
    object per summarization id. Anything else falls back to the generic text keys."""
    if isinstance(it, dict) and isinstance(it.get("v2"), dict):
        body = text_of(it["v2"].get("summary"))
        if body:
            return body
    return text_of(it)


def summaries_md(s):
    """Summarizations -> [(title or None, markdown)], empties dropped.
    Accepts a string, one summary object, a list, or an object keyed by summarization id."""
    out = []
    for it in summary_items(s) if s else []:
        body = summary_body(it)
        if not body:
            continue
        title = None
        if isinstance(it, dict):
            for k in TITLE_KEYS:
                if isinstance(it.get(k), str) and it[k].strip():
                    title = it[k].strip()
                    break
            tpl = it.get("template")
            if not title and isinstance(tpl, dict) and isinstance(tpl.get("name"), str):
                title = tpl["name"].strip()
        # Pocket's own exports bullet with "•"; Markdown wants "-".
        body = re.sub(r"^(\s*)[•·]\s+", r"\1- ", body, flags=re.M)
        out.append((title, pocket_blocks(body)))
    return out


POCKET_BLOCK = re.compile(r"<pocket:([\w-]+)([^>]*)>(.*?)</pocket:\1>", re.S)


def pocket_blocks(md):
    """Pocket embeds custom blocks in its summary Markdown, seen live as
    `<pocket:timeline title="...">` holding one `when | what | detail` row per line. A tag like
    that is dropped or hidden by most Markdown renderers, a PDF pipeline included, so each block
    becomes a bold title over plain bullets."""
    def plain(m):
        title = re.search(r'title="([^"]*)"', m.group(2))
        items = []
        for row in (r.strip() for r in m.group(3).strip().splitlines()):
            if row:
                cells = [c.strip() for c in row.split("|")]
                items.append("- " + (f"**{cells[0]}**: " + " · ".join(cells[1:]) if len(cells) > 1 else cells[0]))
        return (f"**{title.group(1)}**\n\n" if title else "") + "\n".join(items)
    return POCKET_BLOCK.sub(plain, md)


def action_items_md(s):
    """Pocket's generated action items (v2.actionItems.actions) as plain bullets. Deliberately
    not checkboxes: the note lands in triage/, and a checkbox is a commitment only an
    actions.md may hold. /para-triage decides which of these become one."""
    lines = []
    for it in summary_items(s) if s else []:
        v2 = it.get("v2") if isinstance(it, dict) else None
        acts = (v2.get("actionItems") or {}).get("actions") if isinstance(v2, dict) else None
        for a in acts if isinstance(acts, list) else []:
            if not isinstance(a, dict):
                continue
            label, context = str(a.get("label") or "").strip(), str(a.get("context") or "").strip()
            if not (label or context):
                continue
            extra = [x for x in (
                f"for {a['assignee']}" if a.get("assignee") not in (None, "", "me") else None,
                f"due {str(a['dueDate'])[:10]}" if a.get("dueDate") else None,
                "done in Pocket" if a.get("isCompleted") or a.get("is_completed") else None) if x]
            line = "- " + ": ".join(x for x in (f"**{label}**" if label else "", context) if x)
            lines.append(line + (f" ({', '.join(extra)})" if extra else ""))
    return "\n".join(lines)


def demote(md, base=3):
    """Renumber heading levels to consecutive, starting at `base`, so they nest under ## Summary."""
    levels = sorted({len(h) for h in re.findall(r"^(#{1,6}) ", md, flags=re.M)})
    if not levels:
        return md
    remap = {lvl: min(6, base + i) for i, lvl in enumerate(levels)}
    return re.sub(r"^(#{1,6}) ", lambda m: "#" * remap[len(m.group(1))] + " ", md, flags=re.M)


# Pocket's API reference gives `state` no enum. "completed" is the value seen live; the rest are
# the obvious spellings. A status in neither set cannot tell a blank field from a changed payload,
# so it holds as unreadable rather than as processing.
PENDING = {"pending", "queued", "uploading", "uploaded", "processing", "transcribing", "summarizing",
           "in_progress", "running", "started", "recording", "new", "created", "waiting", "diarizing",
           "analyzing", "generating"}
DONE = {"completed", "complete", "done", "finished", "failed", "error", "skipped", "cancelled", "canceled"}
# Key words whose strings are never transcript or summary text.
NOT_TEXT = {"title", "name", "template", "error", "errors", "message", "metadata", "speaker", "status", "state"}


def norm(v):
    return v.strip().lower() if isinstance(v, str) else ""


def tokens(key):
    """A key's words, lowercased: "v2SummaryStatus" -> v, 2, summary, status; "body_md" -> body, md."""
    return [t.lower() for t in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", str(key))]


def status_fields(obj):
    """Every status an object reports under a key ending in "status" or "state", including the
    `status` of an object held there (`v2SummaryStatus: {status: ...}`)."""
    out = []
    for k, v in obj.items() if isinstance(obj, dict) else ():
        if tokens(k)[-1:] in (["status"], ["state"]):
            out.append(v.get("status") if isinstance(v, dict) else v)
    return out


def statuses(rec):
    """The recording's state, every status its summaries report and the transcript's own status
    fields, normalised, blanks dropped."""
    s = rec.get("summarizations")
    found = [rec.get("state")] + status_fields(rec.get("transcript"))
    for it in ([s] if isinstance(s, dict) else []) + [i for i in summary_items(s) if isinstance(i, dict)]:
        found += status_fields(it)
    return [norm(v) for v in found if norm(v)]


def has_words(v, depth=0, where="bare"):
    """Whether a field holds text the readers may have missed. Only strings where text is expected
    count: a non-empty string under a text key ("originalText", "body_md", judged by the key's last
    word, so "transcript_id" is not one), or a string of more than one word that is the field itself,
    an item of a list, or inside a segment list (a single token is an id or a status). Keys naming a
    label, an error, a speaker, metadata or a status are skipped, as is anything that parses as a
    timestamp."""
    if depth > 8:
        return False
    if isinstance(v, str):
        if parse_when(v):
            return False
        return bool(v.strip()) if where == "text" else where in ("bare", "segments") and bool(prose(v))
    if isinstance(v, list):
        return any(has_words(x, depth + 1, "other" if where == "other" else "segments") for x in v)
    if not isinstance(v, dict):
        return False
    for k, x in v.items():
        words = tokens(k)
        if set(words) & NOT_TEXT:
            continue
        if words[-1:] and words[-1] in TEXT_KEYS + ("md",):
            inner = "text"
        elif where == "segments" or (isinstance(x, list) and set(words) & set(SEGMENT_LIST_KEYS)):
            inner = "segments"
        else:
            inner = "other"
        if has_words(x, depth + 1, inner):
            return True
    return False


def readiness(rec, transcript, summaries):
    """None when the recording can be written, else (kind, why) for a HELD one, retried next run
    and never ledgered. "processing": any status Pocket reports is in progress. "unreadable": a
    field holds words the readers cannot parse, or a field is blank while the recording's state or
    any other status is not one known to be final. A blank field is written as empty only when
    every status is final, or when Pocket reported an error for it."""
    found = statuses(rec)
    busy = sorted({s for s in found if s in PENDING})
    if busy:
        return "processing", ", ".join(busy)
    gaps = [(name, field) for name, text, err, field in (
        ("transcript", transcript, rec.get("transcript_error"), rec.get("transcript")),
        ("summary", summaries, rec.get("summarizations_errors"), rec.get("summarizations")))
        if not text and not err]
    unread = [name for name, field in gaps if has_words(field)]
    if unread:
        return "unreadable", " and ".join(unread) + " present but unreadable"
    unsure = sorted({s for s in found if s not in DONE})
    if norm(rec.get("state")) not in DONE and not unsure:
        unsure = [json.dumps(rec.get("state"))]
    if gaps and unsure:
        return "unreadable", (f"no {' or '.join(n for n, _ in gaps)}, and status "
                              f"{', '.join(unsure)} is not one known to be final")
    return None


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


def read_ledger(path):
    if not path.exists():
        return {}
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        ledger = e
    if not isinstance(ledger, dict):
        sys.exit(f"The dedup ledger is unreadable ({ledger}):\n  {path}\nRepair or restore it: deleting it "
                 "re-imports every recording in the look-back window whose note has left its folder.")
    return ledger


def load_ledger():
    """The ledger at STATE, over the one an older copy kept under cache/. That legacy file is
    read, never written or deleted."""
    legacy = STATE.parents[2] / "cache" / STATE.parent.name / STATE.name
    return {**read_ledger(legacy), **read_ledger(STATE)}


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
                if line.startswith("pocket_id:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def pick_path(folder, when, title, rid):
    """(path, already_written). Recordings sharing a date and title get an id suffix, the first
    six characters, then the whole id, then a counter, each taken only when the file there is
    absent or carries this recording's id, so no recording is dropped as another's duplicate."""
    base = f"{when:%Y%m%d} {sanitize(title) or 'untitled'}"
    full = sanitize(rid)
    for i in itertools.count():
        suffix = ("", f" ({rid[:6]})", f" ({full})")[i] if i < 3 else f" ({full} {i - 1})"
        p = folder / f"{base}{suffix}.md"
        if not p.exists():
            return p, False
        if note_id(p) == rid:
            return p, True


def render_note(rec, when, transcript, summaries, actions=""):
    title = rec.get("title") or "(untitled)"
    by = (rec.get("recorded_by") or {}).get("display_name")
    tags = tag_names(rec)
    dur = rec.get("duration")  # seconds: matches transcript.metadata.duration on a live recording
    minutes = round(dur / 60) if isinstance(dur, (int, float)) and not isinstance(dur, bool) and dur > 0 else None
    # No `language`: Pocket's field is the transcriber's guess, not the language spoken.
    front = ["---",
             f"title: {json.dumps(title, ensure_ascii=False)}",  # quoted: a colon in a title breaks YAML
             f"date: {when:%Y-%m-%d}",
             f"pocket_id: {rec.get('id')}",
             "source: pocket",
             f"recorded_by: {json.dumps(by, ensure_ascii=False)}" if by else None,
             f"duration_min: {minutes}" if minutes else None,
             f"tags: {json.dumps(tags, ensure_ascii=False)}" if tags else None,
             "---"]
    if summaries:
        parts = []
        for t, body in summaries:
            if len(summaries) == 1:
                parts.append(demote(body, 3))
            else:
                parts.append(f"### {t or 'Summary'}\n\n{demote(body, 4)}")
        summary = "\n\n".join(parts)
    else:
        errs = "; ".join(str(e) for e in rec.get("summarizations_errors") or [])
        summary = f"_(no summary: Pocket reported {errs})_" if errs else "_(no summary available)_"
    if not transcript:
        err = rec.get("transcript_error")
        transcript = f"_(no transcript: Pocket reported {err})_" if err else "_(no transcript available)_"
    body = [f"# {title}", f"_{when:%Y-%m-%d %H:%M}" + (f" · {minutes} min_" if minutes else "_"), "",
            "## Summary", "", summary, ""]
    if actions:
        body += ["## Action items", "", "_Generated by Pocket, unconfirmed._", "", actions, ""]
    body += ["## Transcript", "", transcript, ""]
    return "\n".join([x for x in front if x is not None] + [""] + body)


# ─── Pocket API (GET only) ────────────────────────────────────────────────────────────────

def load_key(path=None):
    path = path or AUTH
    if not path.exists():
        sys.exit(f"No Pocket API key at {path}\n"
                 "Create one in the Pocket app (Settings -> Developer -> API Keys) and save it as\n"
                 '  {"api_key": "pk_..."}\n'
                 "in that file. It is a secret: it lives under ~/.paraos, never in the vault.")
    try:
        key = str(json.loads(path.read_text(encoding="utf-8")).get("api_key") or "").strip()
    except (OSError, ValueError, AttributeError) as e:
        sys.exit(f"{path} is unreadable: {e}")
    if not key.startswith("pk_"):
        sys.exit(f"{path}: \"api_key\" is missing or does not start with pk_.")
    return key


class PocketError(RuntimeError):
    """A request that still failed after retries, or a response that is not Pocket's JSON."""


RETRIES = 3
PAGE_SIZE = 100
MAX_PAGES = 50  # 5000 recordings in one window is a runaway loop, not a backlog


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


def api_get(key, path, params=None):
    """GET one API path -> parsed JSON. A rate limit, a server error or a network failure is
    retried, then raised as PocketError, as is a response that is not JSON. A refused key stops."""
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(RETRIES + 1):
        wait = 2 ** (attempt + 1) if attempt < RETRIES else None
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + key, "Accept": "application/json", "User-Agent": "para-os-pocket"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit(f"Pocket refused the API key (HTTP {e.code}). Create a new one and update {AUTH}.")
            if wait and (e.code == 429 or e.code >= 500):
                time.sleep(retry_after((e.headers or {}).get("Retry-After"), wait))
                continue
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except (OSError, AttributeError, ValueError):
                detail = ""
            raise PocketError(f"GET {path} -> HTTP {e.code}" + (f": {detail}" if detail else ""))
        except (OSError, http.client.HTTPException) as e:
            if wait:
                time.sleep(wait)
                continue
            raise PocketError(f"GET {path}: {getattr(e, 'reason', None) or str(e) or type(e).__name__}")
        try:
            body = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise PocketError(f"GET {path}: response is not JSON")
        if isinstance(body, dict) and body.get("success") is False:
            raise PocketError(f"GET {path}: {body.get('error')}")
        return body


def list_recordings(key, since):
    out = []
    for page in range(1, MAX_PAGES + 1):
        body = api_get(key, "/public/recordings", {"start_date": f"{since:%Y-%m-%d}", "page": page,
                                                   "limit": PAGE_SIZE})
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(body, dict) or not isinstance(data, (list, type(None))):
            raise PocketError("GET /public/recordings: response has no list of recordings")
        out.extend(r for r in data or [] if isinstance(r, dict))
        paging = body.get("pagination") if isinstance(body.get("pagination"), dict) else {}
        if not paging.get("has_more"):
            if "has_more" not in paging and len(data or []) >= PAGE_SIZE:
                print(f"! page {page} of the listing came back full with no has_more flag: the listing may be "
                      f"truncated after {len(out)} recordings. Narrow --days.", file=sys.stderr)
            return out
    print(f"! stopped after {MAX_PAGES} pages ({len(out)} recordings): the rest of the window was not "
          f"read. Narrow --days.", file=sys.stderr)
    return out


def get_recording(key, rid):
    path = f"/public/recordings/{urllib.parse.quote(rid)}"
    body = api_get(key, path, {"include_transcript": "true", "include_summarizations": "true"})
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise PocketError(f"GET {path}: response has no recording object")
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pull recent Pocket recordings into triage/ (dry run by default).")
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
            print(f"! --vault \"{args.vault}\" ignored: pocket.config.json has no \"route\", so every "
                  f"recording goes to this vault (\"{vault_name}\").", file=sys.stderr)
        elif target not in set(routes.values()):
            sys.exit(f"! --vault \"{args.vault}\": nothing routes there. This config routes to: "
                     f"{', '.join(sorted(set(routes.values())))}.")

    key = load_key()
    if args.dump:
        try:
            body = api_get(key, f"/public/recordings/{urllib.parse.quote(args.dump)}",
                           {"include_transcript": "true", "include_summarizations": "true"})
        except PocketError as e:
            sys.exit(f"! {e}")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return

    state = load_ledger()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    try:
        listed = [(recorded_at(r), r) for r in list_recordings(key, cutoff.date())]
    except PocketError as e:
        sys.exit(f"! Could not list Pocket recordings, nothing written: {e}")
    undated = [r for w, r in listed if not w]
    recent = sorted([(w, r) for w, r in listed if w and w >= cutoff], key=lambda x: x[0], reverse=True)
    mode = "WRITE" if args.write else "DRY RUN"
    scope = f" · routing {'-> ' + only if only else 'all vaults'}" if routes else ""
    print(f"{mode} · last {args.days} days · {len(recent) + len(undated)} recordings{scope}\n")

    n = dict.fromkeys(("written", "recorded", "skipped", "processing", "unreadable", "failed", "undated",
                       "unrouted", "elsewhere"), 0)
    for when, rec in [(None, r) for r in undated] + recent:
        rid = str(rec.get("id"))
        label = f"{f'{when:%Y-%m-%d}' if when else '(no date)':<10}  {str(rec.get('title') or '(untitled)')[:34]:<35}"
        r = resolve(rec, routes, VAULT_ROOT, only, subdir)
        # Another vault's recording: silent per recording, but counted, so the closing line adds
        # up to the header's count and a misrouted config cannot pass for a quiet week.
        if r.get("elsewhere"):
            n["elsewhere"] += 1
            continue
        if not when:
            print(f"  !!  {label}UNDATED (no recording_at or created_at it can parse); "
                  f"inspect: py pocket.py --dump {rid}")
            n["undated"] += 1
            continue
        if "unrouted" in r:
            print(f"  ??  {label}-> UNROUTED (prefix: {r['unrouted']})")
            n["unrouted"] += 1
            continue

        vault = r["vault"]
        dest, exists = pick_path(r["dir"], when, r["desc"], rid)
        if state.get(f"{rid}@{vault}"):
            print(f"  ==  {label}-> {vault}/{subdir} (exists, skip)")
            n["skipped"] += 1
            continue
        if exists:
            # This recording's note, written by a run that stopped before ledgering it: ledger it
            # now, or it is imported again once /para-triage files the note out of this folder.
            print(f"  ==  {label}-> {vault}/{subdir}/{dest.name} (exists, {'recorded' if args.write else 'would record'})")
            if args.write:
                record(f"{rid}@{vault}", str(dest))
            n["recorded"] += 1
            continue

        try:
            rec = {**rec, **get_recording(key, rid)}
        except PocketError as e:
            print(f"  xx  {label}FAILED ({e}) - retried next run")
            n["failed"] += 1
            continue
        transcript = transcript_md(rec.get("transcript"))
        summaries = summaries_md(rec.get("summarizations"))
        hold = readiness(rec, transcript, summaries)
        if hold and hold[0] == "processing":
            print(f"  ..  {label}HELD, still processing ({hold[1]}) - retried next run")
            n["processing"] += 1
            continue
        if hold:
            print(f"  !!  {label}HELD, unreadable ({hold[1]}) - retried next run; inspect: py pocket.py --dump {rid}")
            n["unreadable"] += 1
            continue

        actions = action_items_md(rec.get("summarizations"))
        print(f"  {'->' if args.write else '+ '}  {label}-> {vault}/{subdir}/{dest.name}  "
              f"[sum {sum(len(b) for _, b in summaries)}c · actions {actions.count(chr(10) + '- ') + bool(actions)} · tr {len(transcript)}c]")
        if args.write:
            write_atomic(dest, render_note(rec, when, transcript, summaries, actions))
            record(f"{rid}@{vault}", str(dest))
        n["written"] += 1

    tail = f" · unrouted: {n['unrouted']} · other vaults: {n['elsewhere']}" if routes else ""
    recorded = f" · {'recorded' if args.write else 'would record'}: {n['recorded']}" if n["recorded"] else ""
    print(f"\n{'wrote' if args.write else 'would write'}: {n['written']}{recorded} · skipped(exists): {n['skipped']} · "
          f"held(processing): {n['processing']} · held(unreadable): {n['unreadable']} · failed: {n['failed']} · "
          f"undated: {n['undated']}{tail}")
    if not args.write:
        print("Re-run with --write to create the files.")


if __name__ == "__main__":
    main()
