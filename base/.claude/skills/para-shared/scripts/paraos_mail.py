#!/usr/bin/env python3
"""Reading mail threads, the triage notes they become, and the ledgers that track them.

Imported by `/para-triage` and `/para-daily-brief`, and run from the command line by any skill
that reads mail. Nothing here reads a vault's own files; that is `paraos_vault.py`, beside this
file, which holds the date arithmetic this builds on.

    py -3 paraos_mail.py key <messages.json>
    py -3 paraos_mail.py eml <message.eml> [--extract <dir>]

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "para-shared" / "scripts"))
    from paraos_mail import watermark, unanswered, note_name_parts

What lives here is what `/para-triage`'s per-vault seen-ledger and `/para-ingest`'s central one
both need: the dedup key both are keyed on, reading the run logs (older ones a model wrote,
naming their fields inconsistently between runs), recomputing a staged note's name from the
thread id that produced it, deciding whether a ledger entry still covers a thread's newest
message, and how many working days a sent message has waited. A vault without `/para-ingest`
reads empty logs and an absent ledger here, which is the truth about it. It also reads a
message saved as an `.eml`, for a mailbox that reaches a vault only that way.
"""

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

from paraos_vault import is_under, iso, paraos_home_dir, parse_date, same_place, working_days

UNANSWERED_WORKING_DAYS = 5 # a sent message unanswered this many working days is a wait

def _parse_instant(text):
    """An ISO-8601 string, offset or trailing `Z`, as an aware datetime. None where it does
    not parse, and None (not a naive datetime) where it parses but carries no offset at all
    - comparing a naive instant against an aware one raises, and an instant with no stated
    offset is exactly the input connectors.md says never to accept as one."""
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


INGEST_STAMP_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$")


def _filename_instant(stem):
    """The `YYYYMMDD-HHMMSS` a run log's own filename carries, read as local time and given
    this machine's UTC offset for that date (so a log from before or after a DST change
    still gets the offset that actually applied) - the only instant left once neither JSON
    field parses."""
    m = INGEST_STAMP_RE.match(stem)
    if not m:
        return None
    y, mo, d, h, mi, s = (int(g) for g in m.groups())
    try:
        naive = datetime(y, mo, d, h, mi, s)
    except ValueError:
        return None
    return naive.astimezone()


def _ingest_started(data, stem):
    """(ISO string, which field it came from) for one run log: `started_at`, else
    `started`, else the filename stamp - the drift 50 real logs on this machine show
    between what a model happened to write each run."""
    for key in ("started_at", "started"):
        instant = _parse_instant(data.get(key))
        if instant:
            return instant.isoformat(), key
    instant = _filename_instant(stem)
    return (instant.isoformat() if instant else None), "filename"


def ingest_logs(paraos_home=None):
    """Every `/para-ingest` run log under `<paraos_home>/cache/ingest/runs/`, newest first.
    `paraos_home` defaults the way `registry()` does: `$PARAOS_HOME`, else `~/.paraos`.

    `stage.py` writes them; one a model wrote by hand names its fields as that run chose,
    so this reads every spelling seen on this machine rather than one. A file that
    fails to parse still comes back as a record with `load_error` set, its `started_at`
    read from the filename: dropping it would report an ingest run that never happened
    rather than one this reader could not read. A missing directory is `[]`.
    """
    home = paraos_home_dir(paraos_home)
    base = home / "cache" / "ingest" / "runs"
    if not base.is_dir():
        return []
    records = []
    for path in sorted(base.glob("*.json")):
        stem = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not a JSON object")
        except (OSError, ValueError) as err:
            started_at, started_from = _ingest_started({}, stem)
            records.append({
                "file": path.name, "mode": None, "started_at": started_at,
                "started_from": started_from, "files_written": None, "per_vault": None,
                "declaring_vaults": None, "sync_runs": None, "errors": [],
                "load_error": str(err),
            })
            continue
        started_at, started_from = _ingest_started(data, stem)
        counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
        source_plan = data.get("source_plan") if isinstance(data.get("source_plan"), dict) else {}
        per_vault = counts.get("per_vault")
        if not isinstance(per_vault, dict):
            staged = data.get("staged_per_vault")
            per_vault = staged if isinstance(staged, dict) else None
        declaring = source_plan.get("declaring_vaults")
        errors = data.get("errors")
        records.append({
            "file": path.name,
            "mode": data.get("mode"),
            "started_at": started_at,
            "started_from": started_from,
            "files_written": data.get("files_written") if isinstance(data.get("files_written"), list) else None,
            "per_vault": per_vault,
            "declaring_vaults": declaring if isinstance(declaring, dict) else None,
            "sync_runs": data.get("sync_runs") if isinstance(data.get("sync_runs"), list) else None,
            "errors": errors if isinstance(errors, list) else [],
            "load_error": None,
        })

    def sort_key(record):
        instant = _parse_instant(record["started_at"])
        return (instant is not None, instant, record["file"])

    records.sort(key=sort_key, reverse=True)
    return records


def ingest_ledger(paraos_home=None):
    """`/para-ingest`'s own central ledger, `<paraos_home>/cache/ingest/ledger.json`
    (`multi-vault/para-ingest/references/staging.md`, "The ledger"): `{"mailboxes":
    {<mailbox>: {<threadId>: {"routed": [...], "reason", "date", "subject", "seen_through",
    "seen_date"}}}, "by_message_id": {...}}`.

    This is the system of record for which vaults a thread was actually routed to - a note's
    own `Routed` line is prose a model wrote about that decision, not the decision itself, and
    a negated mention ("Not <Vault>: ...") reads as a routing hit to anything that greps the
    line for a vault's name. Two consumers read it this way: `/para-triage`'s `routed_vaults` (which
    vaults a staged note's thread actually went to, for its cross-vault duplicate check) and
    `/para-ingest`'s own reconciles (settling an `undelivered` candidate).

    Read with `encoding="utf-8"`, per the connectors protocol every ledger in it follows. A
    missing file is `exists: False` with empty maps, never an exception: a ledger read is
    background context, not something a caller needs to fail on. A file that fails to parse
    is reported in `load_error` with empty maps too - a ledger a caller cannot read must never
    look like a ledger that says nothing routed anywhere.
    """
    home = paraos_home_dir(paraos_home)
    path = home / "cache" / "ingest" / "ledger.json"
    if not path.is_file():
        return {"exists": False, "mailboxes": {}, "by_message_id": {}, "load_error": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
    except (OSError, ValueError) as err:
        return {"exists": True, "mailboxes": {}, "by_message_id": {}, "load_error": str(err)}
    mailboxes = data.get("mailboxes")
    by_message_id = data.get("by_message_id")
    return {
        "exists": True,
        "mailboxes": mailboxes if isinstance(mailboxes, dict) else {},
        "by_message_id": by_message_id if isinstance(by_message_id, dict) else {},
        "load_error": None,
    }


def log_instant(record):
    """The aware `datetime` an `ingest_logs()` record's `started_at` names, for a caller
    comparing it against its own `now` rather than against a string."""
    return _parse_instant(record.get("started_at"))


def written_under(entry, folder):
    """Whether one `files_written` string names a file inside `folder`.

    A real entry may carry a trailing ` (...)` annotation after the path (never part of a
    staged note's own name, which always ends in its hash and extension, never in a bare
    `)`), a leading `~` for the ingest cache's own home, and either slash depending on which
    machine wrote it. Mojibake inside the filename itself is real and is compared as
    written, since it never changes what folder the file sits in. Both sides are compared
    as `same_place`: the log spells the vault the way the registry does, and a caller has
    usually resolved its own root, so a symlinked or short-named path must still match.
    """
    text = re.sub(r"\s+\([^)]*\)\s*$", "", str(entry).strip()).replace("\\", "/")
    if text.startswith("~"):
        text = os.path.expanduser(text)
    return is_under(Path(same_place(text)), Path(same_place(folder)))


REPLY_PREFIX_RE = re.compile(r"^(?:(?:re|fwd?)\s*:\s*)+", re.IGNORECASE)


def received_instant(text):
    """A message's received time, an ISO-8601 instant or an RFC 2822 date (a `Date:`
    header), as an aware datetime. None where it reads as neither, or has no offset."""
    instant = _parse_instant(text)
    if instant is not None or not text:
        return instant
    try:
        instant = parsedate_to_datetime(str(text))
    except (TypeError, ValueError, IndexError):
        return None
    return instant if instant.tzinfo is not None else None


def dedup_key(message):
    """The key connectors.md step 6 dedupes one message on, from a mapping with any of
    `message_id`, `subject`, `from`, `received`, `mailbox` and `provider_id`.

    In this order: the RFC822 Message-ID in angle brackets; else `content:` plus the first 16
    hex of `sha1("<subject>|<sender>|<received>")`, the subject stripped of every leading
    Re/Fwd/FW with whitespace collapsed, the sender's bare address lowercased, and the received
    time cut to the minute in UTC as `YYYY-MM-DDTHH:MM`, with no `Z`, as most keys already in
    a ledger have it; else `provider:<mailbox>:<provider_id>`. A received time that is no
    instant raises ValueError rather than falling through to another form, as does a message
    none fits.
    """
    message_id = str(message.get("message_id") or "").strip().strip("<>")
    if message_id:
        return f"<{message_id}>"
    sender = parseaddr(str(message.get("from") or ""))[1].lower()
    received = message.get("received")
    if sender and received:
        instant = received_instant(received)
        if instant is None:
            raise ValueError(f"received {received!r} is not an instant with its offset")
        minute = instant.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        subject = REPLY_PREFIX_RE.sub("", " ".join(str(message.get("subject") or "").split()))
        digest = hashlib.sha1(f"{subject}|{sender}|{minute}".encode("utf-8")).hexdigest()
        return f"content:{digest[:16]}"
    mailbox, provider_id = message.get("mailbox"), message.get("provider_id")
    if mailbox and provider_id:
        return f"provider:{mailbox}:{provider_id}"
    raise ValueError("no message_id, no from and received, and no mailbox and provider_id")


def thread_hash(thread_id):
    """The first six hex characters of `sha1(thread_id)` - the derivation `/para-ingest`
    names every staged note with, so a later run can recompute a note's filename from the
    thread id that produced it rather than trusting a stored mapping."""
    return hashlib.sha1(str(thread_id).encode("utf-8")).hexdigest()[:6]


NOTE_DATE_RE = re.compile(r"^\d{8}$")
NOTE_HEX_RE = re.compile(r"^[0-9a-f]{6}$")
NOTE_COPY_RE = re.compile(r"^\d{1,3}$")  # a sync client's " 2" copy, never a 6-digit hash


def note_name_parts(filename):
    """A staged triage note's `YYYYMMDD <subject> <6 hex>[ <copy>].md` name in its parts, or
    None where the name is not that shape.

    The hash is always the trailing token that fits the shape, so a subject that itself ends
    in a six-letter hex-looking word never shadows the real hash that follows it - only the
    last such token is ever read as one.
    """
    name = Path(filename).name
    if not name.lower().endswith(".md"):
        return None
    tokens = name[:-len(".md")].split(" ")
    if len(tokens) < 2 or not NOTE_DATE_RE.match(tokens[0]):
        return None
    date_part, rest = tokens[0], tokens[1:]
    if len(rest) >= 2 and NOTE_COPY_RE.match(rest[-1]) and NOTE_HEX_RE.match(rest[-2]):
        copy, subject_tokens, hash_ = int(rest[-1]), rest[:-2], rest[-2]
    elif NOTE_HEX_RE.match(rest[-1]):
        copy, subject_tokens, hash_ = None, rest[:-1], rest[-1]
    else:
        return None
    if not subject_tokens:
        return None
    return {"date": date_part, "subject": " ".join(subject_tokens), "hash": hash_,
            "copy": copy}


BARE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_bare_date(text):
    return bool(text) and bool(BARE_DATE_RE.match(str(text)))


def _watermark_instant(entry, legacy):
    """The instant a ledger entry's watermark names: `seen_date` parsed as an instant for a
    full entry, or the UTC start of the relevant day for a legacy one - `seen_date`'s own
    day where it has one, else the entry's plain `date`."""
    if not legacy:
        return _parse_instant(entry.get("seen_date"))
    raw = entry.get("seen_date") or entry.get("date")
    day = parse_date(str(raw)[:10]) if raw else None
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) if day else None


def watermark(entry, newest_date=None, newest_key=None):
    """Where one ledger entry stands against a thread's current state, per connectors.md
    steps 5 and 6: `/para-triage`'s per-vault seen-ledger and `/para-ingest`'s central one
    both make this comparison, and both must drop a thread only when it is dispositioned
    *through its newest message*, never compared as strings.

    Returns `{"verdict": "new" | "seen" | "grown" | "carry", "legacy": bool,
    "watermark": <ISO string or None>}`. `newest_key`, when the entry carries `seen_through`,
    settles it outright - the key wins over dates either way. Otherwise the cut is by date:
    an entry with no `seen_through`, a bare `YYYY-MM-DD` `seen_date`, or no `seen_date` at
    all is legacy, its watermark the start of that day in UTC, and growing past it reads as
    `grown` rather than `carry` (connectors.md: let anything later resurface). A watermark or
    a `newest_date` that fails to parse never reads as `seen` - it carries forward instead,
    since failing toward dropping a thread is the false quiet this protocol exists to
    prevent.
    """
    if entry is None:
        return {"verdict": "new", "legacy": False, "watermark": None}

    seen_through = entry.get("seen_through")
    legacy = not seen_through or _is_bare_date(entry.get("seen_date")) or not entry.get("seen_date")
    watermark_instant = _watermark_instant(entry, legacy)
    watermark_iso = watermark_instant.isoformat() if watermark_instant else None

    if newest_key is not None and seen_through:
        return {"verdict": "seen" if newest_key == seen_through else "grown",
                "legacy": legacy, "watermark": watermark_iso}

    if watermark_instant is None:
        return {"verdict": "carry", "legacy": legacy, "watermark": watermark_iso}
    newest_instant = _parse_instant(newest_date) if newest_date is not None else None
    if newest_instant is None:
        return {"verdict": "carry", "legacy": legacy, "watermark": watermark_iso}
    if newest_instant <= watermark_instant:
        return {"verdict": "seen", "legacy": legacy, "watermark": watermark_iso}
    return {"verdict": "grown" if legacy else "carry", "legacy": legacy,
            "watermark": watermark_iso}


def unanswered(sent, now):
    """How long a message the operator sent, newest in its thread, has gone without a reply:
    `{"since", "working_days", "waiting"}`, `since` the day it went out in `now`'s timezone
    and `waiting` true from UNANSWERED_WORKING_DAYS on (connectors.md's sent pass). `sent`
    is an ISO-8601 instant, or a bare `YYYY-MM-DD` read as that day. One that reads as
    neither leaves all three None, never a count of zero."""
    instant = _parse_instant(sent)
    if instant is not None:
        since = instant.astimezone(now.tzinfo).date()
    else:
        since = parse_date(sent) if _is_bare_date(sent) else None
    if since is None:
        return {"since": None, "working_days": None, "waiting": None}
    count = working_days(since, now.date())
    return {"since": iso(since), "working_days": count,
            "waiting": count >= UNANSWERED_WORKING_DAYS}


EML_HEADERS = ("From", "To", "Cc", "Date", "Subject", "Message-ID")
BLOCK_TAGS = {"p", "div", "br", "li", "tr", "table", "ul", "ol", "blockquote", "hr",
              "h1", "h2", "h3", "h4", "h5", "h6"}


class _HtmlText(HTMLParser):
    """An HTML part's words: script and style dropped, a line break at each block."""

    def __init__(self):
        super().__init__()
        self.chunks, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        elif tag in BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif tag in BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.chunks.append(data)


def _html_text(html):
    parser = _HtmlText()
    parser.feed(html)
    parser.close()
    lines = [" ".join(line.split()) for line in "".join(parser.chunks).split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _part_text(part):
    """A text part decoded by its declared charset; one Python does not know, or that its
    bytes break, is read as UTF-8, else cp1252, never refused."""
    try:
        text = part.get_content()
    except (LookupError, UnicodeError):
        data = part.get_payload(decode=True) or b""
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")
    return text.replace("\r\n", "\n").strip()


def _leaves(part):
    if part.get_content_maintype() == "multipart":
        for sub in part.iter_parts():
            yield from _leaves(sub)
    else:
        yield part


def _is_body(part):
    return (part.get_content_type() in ("text/plain", "text/html")
            and part.get_content_disposition() != "attachment" and not part.get_filename())


def _attachment_bytes(part):
    if part.get_content_maintype() == "message":
        inner = part.get_payload()
        inner = inner[0] if isinstance(inner, list) and inner else inner
        return inner.as_bytes() if hasattr(inner, "as_bytes") else b""
    return part.get_payload(decode=True) or b""


def _save(folder, name, data):
    """`data` as `name` inside `folder`, never outside it or over another file: a path in
    the name keeps only its last part, and a taken name gets ` (2)`, ` (3)`."""
    folder.mkdir(parents=True, exist_ok=True)
    base = PurePosixPath(name.replace("\\", "/")).name
    base = " ".join(re.sub(r'[<>:"|?*\x00-\x1f]', " ", base).split()).strip(" .") or "attachment"
    target, n = folder / base, 2
    while target.exists():
        target = folder / f"{PurePosixPath(base).stem} ({n}){PurePosixPath(base).suffix}"
        n += 1
    target.write_bytes(data)
    return target


def eml(path, extract=None):
    """What a saved message holds: `headers` (From, To, Cc, Date, Subject and Message-ID,
    decoded, None where absent), `text` with `text_from` (`plain`, the plain parts; else
    `html`, the HTML parts reduced to text; else None), and `attachments`, each part that is
    no body as `{"name", "type", "size"}` in bytes, a forwarded message among them. With
    `extract`, each is written into that folder and carries `saved_to`."""
    with open(path, "rb") as f:
        message = BytesParser(policy=policy.default).parse(f)
    headers = {name: (None if message.get(name) is None else str(message.get(name)))
               for name in EML_HEADERS}
    leaves = list(_leaves(message))
    bodies = [p for p in leaves if _is_body(p)]
    plain = [_part_text(p) for p in bodies if p.get_content_type() == "text/plain"]
    html = [_html_text(_part_text(p)) for p in bodies if p.get_content_type() == "text/html"]
    text_from = "plain" if plain else ("html" if html else None)
    attachments = []
    for n, part in enumerate((p for p in leaves if not _is_body(p)), 1):
        data = _attachment_bytes(part)
        kind = part.get_content_type()
        name = part.get_filename() or f"part-{n}{mimetypes.guess_extension(kind) or ''}"
        attachment = {"name": name, "type": kind, "size": len(data)}
        if extract is not None:
            attachment["saved_to"] = _save(Path(extract), name, data).as_posix()
        attachments.append(attachment)
    return {"file": Path(path).as_posix(), "headers": headers,
            "text": "\n\n".join(t for t in (plain or html) if t), "text_from": text_from,
            "attachments": attachments}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Answer one question about mail, as JSON.")
    sub = ap.add_subparsers(dest="command", required=True)
    key = sub.add_parser("key", help="the dedup key of each message, in order")
    key.add_argument("file", help="a JSON message or list of them, each with any of "
                                  "message_id, subject, from, received (ISO-8601 or RFC 2822, "
                                  "with its offset), mailbox and provider_id")
    saved = sub.add_parser("eml", help="a saved message's headers, text and attachments")
    saved.add_argument("file", help="the .eml file")
    saved.add_argument("--extract", metavar="DIR", help="also write the attachments into DIR")
    args = ap.parse_args(argv)

    # A Windows console defaults to a codepage that cannot encode a subject.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if args.command == "eml":
        if not Path(args.file).is_file():
            ap.error(f"no such file: {args.file}")
        json.dump(eml(args.file, args.extract), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    try:
        messages = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        ap.error(f"cannot read {args.file}: {err}")
    if isinstance(messages, dict):
        messages = [messages]
    keys = []
    for n, message in enumerate(messages, 1):
        try:
            keys.append(dedup_key(message if isinstance(message, dict) else {}))
        except ValueError as err:
            ap.error(f"message {n}: {err}")
    json.dump({"keys": keys}, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
