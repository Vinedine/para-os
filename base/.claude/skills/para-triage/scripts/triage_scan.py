#!/usr/bin/env python3
"""The mechanical half of /para-triage's Step 2 and Step 3 checks, as a script instead of
instructions.

    py -3 triage_scan.py --vault <path> [--now <ISO-8601>] [--paraos-home <dir>]
                          [--threads <file.json>] [--indent N]

Read-only, one JSON document on stdout. It never writes to the vault, never asks, never
decides a disposition - every judgment (what a file becomes, what a thread means, every
write) stays with the skill, per references/filing.md and references/approval.md.

It answers: whether the current folder is a triage-capable vault root; which of the vault's
declared Triage sources /para-ingest already covered and which still need a local pull, from
the run logs under `<paraos_home>/cache/ingest/runs/`; every loose file in `triage/` with its
kind, its ingest-staged-note fields where it is one, its in-vault and cross-vault duplicates,
and every inbound reference to it; the vault's subdirectories; which staged notes share a
thread; the seen-ledger's shape; and, given `--threads`, whether a freshly fetched thread is
already staged as a note and where its seen-ledger watermark stands.

Reading the vault's primitives - the registry, run logs, staged-note names, thread hashes,
watermarks, content hashes, tasks, links, snapshots - is not this script's own work:
para-shared/scripts/paraos_vault.py holds it. What lives here is what this skill alone
decides: how a triage source row's `plan` is computed from the vault's ingest coverage, how a
staged note's two header shapes are parsed, when its Content line calls itself incomplete,
which registered vaults its Routed line names, and how a fetched thread folds against an
already-staged note.

What it deliberately does NOT do, so the skill keeps owning it: run a sync script, fetch a
mailbox, convert a Google-native file, write a ledger, or decide what happens to any item.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        MIN_HASH_BYTES, WIP_THRESHOLD, abspath, action_files, hashes,
        ingest_ledger, ingest_logs, inbound_references, live_lines, log_instant, norm,
        note_name_parts, open_tasks, read_lines, registered_vault,
        registry, rel_posix, same_place, snapshot, thread_hash, triage_items, triage_sources,
        vault_root, watermark, written_under,
    )
except ImportError as missing:  # the skill falls back to scanning by hand
    print(f"triage_scan: {missing}. The shared vault library belongs at "
          f"{SHARED_DIR}/paraos_vault.py: install para-shared beside this skill, or scan "
          f"by hand with the skill's own reference procedure", file=sys.stderr)
    sys.exit(2)


# ------------------------------------------------------------------------------ the vault

def _entry_by_path(entries, vault):
    target = same_place(vault)
    for entry in entries:
        path = entry.get("path")
        if path and same_place(path) == target:
            return entry
    return None


def _entry_by_name(entries, name):
    key = norm(name)
    for entry in entries:
        if norm(entry.get("name") or "") == key:
            return entry
    return None


def vault_block(vault, entries):
    """The library's root rule plus a `triage/` folder present. `hint`, where this is not a
    root, is the registry entry holding the path (`registered_vault`), else an entry whose
    name folds to the checked folder's own name, as when a vault has moved and the session
    started at its old location. `name` is the registry name of the entry whose
    path is exactly this root, else the folder name; it keys the seen-ledger file."""
    info = vault_root(vault)
    missing = list(info["missing"])
    has_triage = (vault / "triage").is_dir()
    if not has_triage:
        missing.append("triage/")
    root = info["root"] and has_triage

    hint = None
    if not root:
        entry = registered_vault(entries, vault)
        if entry is None:
            entry = _entry_by_name(entries, vault.name)
        if entry:
            hint = {"name": entry.get("name"), "path": entry.get("path")}

    exact = _entry_by_path(entries, vault)
    name = exact.get("name") if exact else vault.name
    return {
        "path": str(vault), "root": root, "missing": missing, "hint": hint,
        "name": name, "registered": exact is not None,
        "active": bool(exact.get("active")) if exact else False,
    }


# ---------------------------------------------------------------------------- ingest & plan

def _log_summary(record, now):
    if record is None:
        return None
    instant = log_instant(record)
    age = (now - instant).total_seconds() / 3600 if instant else None
    return {"file": record["file"], "started_at": record.get("started_at"), "age_hours": age}


def ingest_block(vault, entries, vault_name, paraos_home, now):
    """Whether /para-ingest already covered this vault's mailboxes and sync scripts, per the
    three bullets of references/sources.md: registered and active, a write log within 48
    hours, and that log actually reaching this root (a `files_written` entry under this
    vault's `triage/`, or an explicit `0` in `counts.per_vault` for this vault's name). A
    positive count with nothing written under this root is the opposite of coverage - the
    vault moved and the registry lagged - and is named, not silently trusted.
    """
    records = ingest_logs(paraos_home)
    newest_write = next((r for r in records if r.get("mode") == "write"), None)
    newest_any = records[0] if records else None

    exact = _entry_by_path(entries, vault)
    registered = exact is not None
    active = bool(exact.get("active")) if exact else False

    triage_dir = vault / "triage"
    staged_here = 0
    if newest_write and newest_write.get("files_written"):
        staged_here = sum(1 for f in newest_write["files_written"]
                          if written_under(f, triage_dir))
    count_for_vault = None
    if newest_write and isinstance(newest_write.get("per_vault"), dict):
        count_for_vault = newest_write["per_vault"].get(vault_name)

    # references/sources.md names exactly four phrasings: "pulled as normal" for a vault the
    # registry does not cover at all (unregistered or inactive - nothing to report on either),
    # "pulled locally" for a registered, active vault ingest still did not cover, in the two
    # shapes its own bullets name (a stale/missing/preview-only log, or a positive count staged
    # somewhere else). Covered keeps its own phrasing, unchanged.
    staged_date = newest_write.get("started_at") if newest_write else None
    within_window = False
    if newest_write is not None:
        instant = log_instant(newest_write)
        age_hours = (now - instant).total_seconds() / 3600 if instant else None
        within_window = age_hours is not None and age_hours <= 48

    covered, reason = False, None
    if not registered:
        reason = "vault not registered - pulled as normal"
    elif not active:
        reason = "registry lists this vault inactive - pulled as normal"
    elif within_window and (staged_here > 0 or count_for_vault == 0):
        covered = True
        reason = f"ingest last staged {staged_date}"
    elif within_window and count_for_vault:
        reason = (f"ingest staged {count_for_vault} for {vault_name} outside this root - "
                  f"pulled locally")
    else:
        reason = (f"registry lists this vault, but ingest last staged {staged_date or 'never'} "
                  f"- pulled locally")

    block = {
        "registered": registered, "active": active,
        "newest_write": _log_summary(newest_write, now),
        "newest_any": _log_summary(newest_any, now),
        "covered": covered, "reason": reason,
        "staged_here": staged_here, "count_for_vault": count_for_vault,
        "log_errors": [{"file": r["file"], "error": r["load_error"]}
                       for r in records if r.get("load_error")],
    }
    return block, newest_write


def _norm_script(path):
    return str(path).replace("\\", "/").lower() if path else None


def row_plan(row, covered, vault_name, declaring_vaults, errors_list, sync_runs, vault_reason):
    """`pull` / `run` / `skip` / `lookup` / `unknown` for one Triage sources row, per exactly
    the conditions references/sources.md states. A drive row is never ingest's and always
    `lookup`; an unrecognised row is `unknown`; everything else follows the vault's coverage
    verdict, refined per row for a mailbox `declaring_vaults` does not list, a mailbox an
    ingest error names, or a sync script `sync_runs` does not record without an error.
    """
    kind = row.get("kind")
    mailbox = row.get("mailbox")
    path = row.get("path")

    if kind == "drive":
        return "lookup", "a drive row is never ingest's and always stays"
    if kind not in ("connector", "fetch-script", "sync-script"):
        return "unknown", f"unrecognised source type: {row.get('type') or 'none'}"

    if not covered:
        # vault_reason (ingest["reason"]) already carries "- pulled locally" / "- pulled as
        # normal" - it is the row's reason verbatim, not a fragment to suffix again.
        return ("run" if kind == "sync-script" else "pull"), vault_reason

    if kind in ("connector", "fetch-script"):
        if declaring_vaults is not None:
            names = declaring_vaults.get(mailbox) if mailbox else None
            if not names or vault_name not in names:
                return "pull", f"declaring_vaults does not list {vault_name} for {mailbox}"
        if mailbox and any(mailbox in str(e) for e in errors_list):
            return "pull", f"an ingest error names {mailbox}"
        return "skip", "ingest covered this mailbox"

    # sync-script
    if sync_runs is not None:
        for record in sync_runs:
            if not isinstance(record, dict):
                continue
            if (record.get("vault") == vault_name
                    and _norm_script(record.get("script")) == _norm_script(path)
                    and not record.get("error")):
                return "skip", f"ingest ran {path} for {vault_name} with no error"
        return "run", "log records no matching sync run for this script"
    return "run", "log records no per-vault sync runs"


def sources_block(vault, entries, vault_name, ingest, newest_write):
    src = triage_sources(vault)
    declaring_vaults = newest_write.get("declaring_vaults") if newest_write else None
    errors_list = (newest_write.get("errors") if newest_write else None) or []
    sync_runs = newest_write.get("sync_runs") if newest_write else None

    rows = []
    for row in src["rows"]:
        plan, reason = row_plan(row, ingest["covered"], vault_name, declaring_vaults,
                                errors_list, sync_runs, ingest["reason"])
        rows.append(dict(row, plan=plan, reason=reason))
    return {"declared": src["declared"], "rows": rows}


# ------------------------------------------------------------------------------- items: kind

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif")
GOOGLE_NATIVE_SUFFIXES = (".gdoc", ".gsheet", ".gslides", ".gform", ".gdraw")
ARCHIVE_SUFFIXES = (".zip", ".7z", ".rar", ".tar", ".gz", ".tgz")


def kind_of(path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix == ".md":
        return "markdown"
    if suffix in GOOGLE_NATIVE_SUFFIXES:
        return "google-native"
    if suffix in ARCHIVE_SUFFIXES:
        return "archive"
    if suffix == ".txt":
        return "text"
    return "other"


# -------------------------------------------------------------------------- items: the note

BULLET_FIELD_RE = re.compile(r"^- \*\*([^*]+?)\s*:?\s*\*\*\s*:?\s*(.*)$")
FRONTMATTER_FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")
LINK_THREAD_RE = re.compile(r"#[^/]+/([0-9a-fA-F]{16})")
# claude.ai Gmail's link form carries the same thread id in decimal: `#all/thread-f:<decimal>`.
LINK_THREAD_F_RE = re.compile(r"#[^/]+/thread-f:(\d+)")

# "incomplete" is here, and checked first, because the held phrase "complete" is inside it.
INCOMPLETE_PHRASES = ("snippet", "preview", "opening lines", "no readable body", "cut mid",
                      "truncat", "excerpt", "trimmed", "not read", "not fetched", "incomplete")
COMPLETE_PHRASES = ("full body", "full text", "plain-text body", "complete")
# A Content line's clauses: split at `;`, `,`, `:` and a sentence end, never inside `invite.ics`.
CLAUSE_SPLIT_RE = re.compile(r"[;,:]|\.(?:\s|$)")
BESIDE_BODY_RE = re.compile(r"attach|linked (?:document|file)|enclos")


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_ingest_shape(lines):
    """The bullet header lines after the H1 (`- **Field:** value`), stopping at the first
    blank line once at least one field has been read - the snippet or body that follows the
    header block is never mistaken for more fields. None where the file carries no H1 at all,
    so the caller can fall through to the frontmatter shape."""
    fields = {}
    titled = False
    for text in lines:
        stripped = text.strip()
        if not titled:
            if not stripped:
                continue
            if not stripped.startswith("#"):
                return None
            titled = True
            continue
        if not stripped:
            if fields:
                break
            continue
        match = BULLET_FIELD_RE.match(stripped)
        if not match:
            break
        fields[match.group(1).strip()] = match.group(2).strip()
    return fields if fields else None


def _parse_frontmatter(lines):
    """A leading `---` block of `key: value` lines. None where the first line is not `---`,
    or the block never closes."""
    if not lines or lines[0].strip() != "---":
        return None
    fields = {}
    for text in lines[1:]:
        if text.strip() == "---":
            return fields
        match = FRONTMATTER_FIELD_RE.match(text.strip())
        if match:
            fields[match.group(1).strip()] = _unquote(match.group(2))
    return None


def _extract_mailbox(source_value):
    if not source_value:
        return None
    match = re.search(r"\(([^)]+)\)", source_value)
    return match.group(1).strip() if match else None


def _content_incomplete(text):
    """`(True/False/None, matched phrase)` from a note's `Content` line. The vocabulary is
    this script's own - stated in references/scan.md's by-hand section, not in
    references/filing.md or references/approval.md, which only name the field. An incomplete
    signal wins even where a "held" phrase is also present, since "false" means the body is
    held *with none* of the incomplete signals. Only the clauses describing the body are
    read: a clause naming an attachment or linked document ("26 image attachments not read")
    names something *beside* the body, so it settles nothing either way."""
    if not text:
        return None, None
    clauses = [c for c in CLAUSE_SPLIT_RE.split(text.lower()) if not BESIDE_BODY_RE.search(c)]
    for phrases, verdict in ((INCOMPLETE_PHRASES, True), (COMPLETE_PHRASES, False)):
        for phrase in phrases:
            if any(phrase in clause for clause in clauses):
                return verdict, phrase
    return None, None


def _mentioned_vaults(routed_text, entries, this_vault_name):
    """Registry names other than this vault's, appearing in the `Routed` line as whole words:
    case-insensitive for a name of four or more characters, case-sensitive for a shorter one
    (a short name such as `IT` or `OR` is also an ordinary word). **No negation parsing** - a
    "Not Beta: ..." line still names Beta here, because this is documented as a mention the
    line makes, never a routing decision; `routed_vaults` (from the ingest ledger, below) is
    the routing decision."""
    if not routed_text:
        return []
    hits = []
    for entry in entries:
        name = entry.get("name")
        if not name or name == this_vault_name:
            continue
        flags = re.IGNORECASE if len(name) >= 4 else 0
        if re.search(r"\b" + re.escape(name) + r"\b", routed_text, flags):
            hits.append(name)
    return sorted(set(hits))


def _ledger_entry(ledger_mailboxes, mailbox, filename_hash):
    """`(thread_id, record)` of the entry in `/para-ingest`'s central ledger, in this note's
    own mailbox, whose thread hashes to this note's filename hash; `(None, None)` where the
    mailbox is unknown to the ledger or no entry's thread matches. The hash is searched only
    within the note's own mailbox, never across every mailbox in the ledger, since a six-hex
    hash can collide between two unrelated mailboxes."""
    if not mailbox or not filename_hash:
        return None, None
    mailbox_entries = ledger_mailboxes.get(mailbox)
    if not isinstance(mailbox_entries, dict):
        return None, None
    for thread_id, record in mailbox_entries.items():
        if isinstance(record, dict) and thread_hash(thread_id) == filename_hash:
            return thread_id, record
    return None, None


def _routed_from_ledger(ledger_mailboxes, mailbox, filename_hash, vault_name):
    """`(routed_vaults, routed_from)`: the ledger entry's `routed` list minus this vault,
    and `"ledger"`; `(None, None)` with no entry."""
    _, record = _ledger_entry(ledger_mailboxes, mailbox, filename_hash)
    if record is None:
        return None, None
    routed = record.get("routed")
    routed = routed if isinstance(routed, list) else []
    return sorted({v for v in routed if v and v != vault_name}), "ledger"


def _ingest_seen(ledger_mailboxes, mailbox, filename_hash):
    """The ledger entry's thread id and watermark, which a re-read at source is compared
    against (references/execute.md); None with no entry."""
    thread_id, record = _ledger_entry(ledger_mailboxes, mailbox, filename_hash)
    if record is None:
        return None
    return {"thread_id": thread_id, "seen_through": record.get("seen_through"),
            "seen_date": record.get("seen_date")}


def _extract_thread_id(link_value, filename_hash):
    if not link_value or not filename_hash:
        return None
    match = LINK_THREAD_RE.search(link_value)
    if match:
        candidate = match.group(1)
    else:
        match = LINK_THREAD_F_RE.search(link_value)
        if not match:
            return None
        candidate = format(int(match.group(1)), "x")
    return candidate if thread_hash(candidate) == filename_hash else None


def note_block(path, entries, vault_name, ledger_mailboxes):
    """`shape`, `fields`, `mail_note` and everything a staged note's header settles, per the
    two shapes staging.md and execute.md's Note-to-triage write: the ingest bullet header, or
    a leading frontmatter block. Neither shape found: every field comes back empty/None.

    Two different answers about which other vaults this thread concerns: `mentioned_vaults`
    is text the `Routed` line happens to name (a mention, negation included); `routed_vaults`
    is what the ingest ledger's own record says the thread was actually routed to (the system
    of record). `cross_vault`, below, checks the union of both.
    """
    name_parts = note_name_parts(path.name)
    filename_hash = name_parts["hash"] if name_parts else None
    lines = [text for _, text in live_lines(read_lines(path))]

    shape, fields = None, {}
    ingest_fields = _parse_ingest_shape(lines)
    if ingest_fields is not None:
        shape, fields = "ingest", ingest_fields
    else:
        frontmatter_fields = _parse_frontmatter(lines)
        if frontmatter_fields is not None:
            shape, fields = "frontmatter", frontmatter_fields

    if shape == "ingest":
        source_value = fields.get("Source")
        mail_note = bool(fields.get("Source")) and bool(fields.get("Link"))
        mailbox = _extract_mailbox(source_value)
        mentioned_vaults = _mentioned_vaults(fields.get("Routed"), entries, vault_name)
        incomplete, evidence = _content_incomplete(fields.get("Content"))
        link_value = fields.get("Link")
    elif shape == "frontmatter":
        source_value = fields.get("source")
        mail_note = bool(fields.get("thread_id"))
        mailbox = _extract_mailbox(source_value)
        mentioned_vaults = []
        incomplete, evidence = None, None
        link_value = fields.get("link")
    else:
        mail_note, mailbox, mentioned_vaults = False, None, []
        incomplete, evidence, link_value = None, None, None

    routed_vaults, routed_from = _routed_from_ledger(ledger_mailboxes, mailbox, filename_hash,
                                                      vault_name)

    return {
        "shape": shape, "fields": fields, "mail_note": mail_note, "mailbox": mailbox,
        "mentioned_vaults": mentioned_vaults, "routed_vaults": routed_vaults,
        "routed_from": routed_from, "content_incomplete": incomplete,
        "content_evidence": evidence, "thread_hash": filename_hash,
        "thread_id": _extract_thread_id(link_value, filename_hash),
        "message_id": fields.get("Message id") if shape == "ingest" else None,
        "conversation_id": fields.get("Conversation id") if shape == "ingest" else None,
        "ingest_seen": _ingest_seen(ledger_mailboxes, mailbox, filename_hash),
    }


# -------------------------------------------------------------------- items: duplicates etc

def _fill_duplicates(vault, items):
    """`duplicates` per item, one batched `hashes()` call across every item's size rather
    than one call per item - size first is the point, on a streaming cloud mount reading a
    file's bytes downloads it. `skip=()`: a triage photo duplicating one under
    `sources/photos/` is a real duplicate here."""
    sizes = {item["size"] for item in items if item["size"] >= MIN_HASH_BYTES}
    digests = hashes(vault, skip=(), sizes=sizes)["files"] if sizes else {}
    for item in items:
        rel = f"triage/{item['name']}"
        if item["size"] < MIN_HASH_BYTES:
            item["hash_skipped"] = f"below MIN_HASH_BYTES ({MIN_HASH_BYTES})"
            item["duplicates"] = None
            continue
        item["hash_skipped"] = None
        digest = digests.get(rel)
        item["duplicates"] = (sorted(p for p, d in digests.items() if d == digest and p != rel)
                              if digest else [])


def _file_digest(path):
    try:
        return hashlib.md5(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _cross_vault(entries, note_path, size, routed_vaults):
    """Byte-identical files in each routed vault's `sources/` folders, `{"vault", "path"}`
    per hit; an unreadable or missing vault root is `{"vault", "unreadable": true}`, never
    dropped - a scan that passed over a vault in silence reports one it never read as clean.
    """
    digest = _file_digest(note_path)
    out = []
    for name in routed_vaults:
        entry = next((e for e in entries if e.get("name") == name), None)
        other_path = entry.get("path") if entry else None
        other_root = Path(other_path) if other_path else None
        if other_root is None or not other_root.is_dir():
            out.append({"vault": name, "unreadable": True})
            continue
        try:
            other_digests = hashes(other_root, skip=(), sizes={size}, within=("sources",))["files"]
        except OSError:
            out.append({"vault": name, "unreadable": True})
            continue
        if digest is None:
            continue
        for path, other_digest in other_digests.items():
            if other_digest == digest:
                out.append({"vault": name, "path": path})
    return out


def _inbound_for_item(vault, name):
    triage_rel = f"triage/{name}"
    out = []
    for hit in inbound_references(vault, name, parent="triage"):
        if hit["file"] == triage_rel:
            continue
        out.append({"file": hit["file"], "line": hit["line"], "shape": hit["shape"]})
    return out


# ------------------------------------------------------------------------------ items: loose

def _mailbox_readers(entries):
    """`{mailbox, lowercased: [vault names]}` for every active registered vault whose
    `## Triage sources` declares that mailbox: the vaults that receive its mail on their own,
    so Dismiss (other vault) leaves the item somewhere (references/approval.md)."""
    readers = {}
    for entry in entries:
        path, name = entry.get("path"), entry.get("name")
        if not entry.get("active") or not name or not path or not Path(path).is_dir():
            continue
        for row in triage_sources(Path(path))["rows"]:
            if row.get("mailbox") and row.get("kind") in ("connector", "fetch-script"):
                names = readers.setdefault(row["mailbox"].lower(), [])
                if name not in names:
                    names.append(name)
    return {mailbox: sorted(names) for mailbox, names in readers.items()}


def build_loose(vault, entries, vault_name, ledger_mailboxes):
    triage_dir = vault / "triage"
    file_map = {}
    if triage_dir.is_dir():
        file_map = {p.name: p for p in triage_dir.iterdir()
                    if p.is_file() and p.name != ".gitkeep"}

    items = []
    for name in triage_items(vault):
        path = file_map.get(name)
        if path is None:
            continue
        entry = {
            "name": name, "size": path.stat().st_size, "kind": kind_of(path),
            "readme": name.lower() == "readme.md", "twin": None, "note": None,
            "duplicates": None, "hash_skipped": None, "cross_vault": [], "inbound": [],
        }
        if path.suffix.lower() == ".pdf":
            twin_name = f"{path.stem}.md"
            if twin_name in file_map:
                entry["twin"] = twin_name
        if path.suffix.lower() == ".md":
            entry["note"] = note_block(path, entries, vault_name, ledger_mailboxes)
        items.append(entry)

    _fill_duplicates(vault, items)
    readers = None
    for entry in items:
        note = entry["note"]
        if note:
            note["mailbox_readers"] = None
        if note and note["mail_note"]:
            if readers is None:
                readers = _mailbox_readers(entries)
            note["mailbox_readers"] = readers.get((note["mailbox"] or "").lower(), [])
            # cross_vault checks the union: mentioned_vaults costs one extra size-filtered
            # sources/ walk per name when it turns out wrong, routed_vaults missing one is
            # the silent duplicate real --test runs have hit.
            union_vaults = sorted(set(note.get("mentioned_vaults") or ()) |
                                  set(note.get("routed_vaults") or ()))
            if union_vaults:
                entry["cross_vault"] = _cross_vault(
                    entries, triage_dir / entry["name"], entry["size"], union_vaults)
        entry["inbound"] = _inbound_for_item(vault, entry["name"])
    return items


# --------------------------------------------------------------------- items: subdirectories

def subdirectories_block(vault):
    triage_dir = vault / "triage"
    out = []
    if triage_dir.is_dir():
        for entry in sorted(triage_dir.iterdir()):
            if entry.is_dir():
                count = sum(1 for p in entry.rglob("*") if p.is_file())
                out.append({"name": entry.name, "files": count,
                            "handoff": entry.name.startswith("_")})
    return out


def subdirectories_line(subdirectories):
    """The manifest's line for the subdirectories, as approval.md writes it, or None when
    there are none. Printed as it stands, so a run never words it its own way."""
    if not subdirectories:
        return None
    listed = ", ".join(f"triage/{s['name']}/ ({s['files']} file{'' if s['files'] == 1 else 's'})"
                       for s in subdirectories)
    return f"Subdirectories, not asked: {listed}"


def same_thread_block(items):
    """Staged notes of one thread: joined by the filename hash, or by a shared `Conversation
    id`, which pairs one conversation staged from two mailboxes. A group a conversation id
    joins is keyed by it, any other by its hash."""
    parent, first, keys = {}, {}, {}

    def root(name):
        while parent[name] != name:
            name = parent[name]
        return name

    for item in items:
        parts = note_name_parts(item["name"]) if item["kind"] == "markdown" else None
        if not parts:
            continue
        name = item["name"]
        parent[name] = name
        conversation = (item.get("note") or {}).get("conversation_id")
        keys[name] = (conversation, parts["hash"])
        for key in (parts["hash"], ("conversation", conversation)):
            if key == ("conversation", None):
                continue
            if key in first:
                parent[root(name)] = root(first[key])
            else:
                first[key] = name

    groups = {}
    for name in parent:
        groups.setdefault(root(name), []).append(name)
    out = {}
    for names in groups.values():
        if len(names) < 2:
            continue
        conversations = sorted(keys[n][0] for n in names if keys[n][0])
        out[conversations[0] if conversations else keys[names[0]][1]] = sorted(names)
    return out


# ------------------------------------------------------------------------------ seen ledger

def _paraos_home(paraos_home):
    return Path(paraos_home) if paraos_home else Path(
        os.environ.get("PARAOS_HOME") or (Path.home() / ".paraos"))


def ingest_ledger_block(paraos_home):
    """The top-level `ingest_ledger` summary (`path`, `exists`, `load_error`) - not the
    ledger's own content, which can span every vault on the machine. `note_block` reads the
    full `mailboxes` map separately, once per scan, to compute each note's `routed_vaults`."""
    ledger = ingest_ledger(paraos_home)
    path = _paraos_home(paraos_home) / "cache" / "ingest" / "ledger.json"
    block = {"path": str(path), "exists": ledger["exists"], "load_error": ledger["load_error"]}
    return block, ledger["mailboxes"]


def seen_ledger_block(paraos_home, vault_name):
    path = _paraos_home(paraos_home) / "cache" / "triage-email" / f"{vault_name}.json"
    exists = path.is_file()
    entries_count, legacy_count, load_error = 0, 0, None
    if exists:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not a JSON object")
            entries_count = len(data)
            for entry in data.values():
                if isinstance(entry, dict) and watermark(entry).get("legacy"):
                    legacy_count += 1
        except (OSError, ValueError) as err:
            load_error = str(err)
    return {"path": str(path), "exists": exists, "entries": entries_count,
            "legacy": legacy_count, "load_error": load_error}


# ---------------------------------------------------------------------------------- threads

def threads_block(threads_data, seen_ledger_path, loose_items):
    ledger_data = {}
    if seen_ledger_path.is_file():
        try:
            loaded = json.loads(seen_ledger_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                ledger_data = loaded
        except (OSError, ValueError):
            ledger_data = {}

    name_hashes = {item["name"]: note_name_parts(item["name"]) for item in loose_items}
    out = []
    for thread in threads_data:
        if not isinstance(thread, dict):
            continue
        thread_id = thread.get("thread_id")
        the_hash = thread_hash(thread_id) if thread_id else None
        staged = sorted(name for name, parts in name_hashes.items()
                        if parts and parts["hash"] == the_hash)
        entry = ledger_data.get(thread_id) if thread_id is not None else None
        mark = watermark(entry, newest_date=thread.get("newest_date"),
                         newest_key=thread.get("newest_key"))
        out.append({"thread_id": thread_id, "thread_hash": the_hash, "staged_notes": staged,
                    "ledger": entry, "watermark": mark})
    return out


# ---------------------------------------------------------------------------- over-threshold

def over_threshold_block(vault):
    out = []
    for path in action_files(vault):
        count = len(open_tasks(path))
        if count >= WIP_THRESHOLD:
            out.append({"file": rel_posix(vault, path), "open": count})
    return sorted(out, key=lambda r: -r["open"])


# -------------------------------------------------------------------------------- snapshot

def build_snapshot(vault):
    """Every file directly in triage/, twins included, so `paraos_vault.py changed` can tell
    a file that arrived after the scan from one the operator was shown."""
    triage_dir = vault / "triage"
    if not triage_dir.is_dir():
        return {}
    return snapshot(sorted(abspath(p) for p in triage_dir.iterdir()
                           if p.is_file() and p.name != ".gitkeep"))


# ------------------------------------------------------------------------------------- plan

def plan(vault, paraos_home, now, threads_data):
    vault = Path(vault).resolve()
    entries = registry(paraos_home)
    vault_info = vault_block(vault, entries)
    vault_name = vault_info["name"]

    ingest, newest_write = ingest_block(vault, entries, vault_name, paraos_home, now)
    sources = sources_block(vault, entries, vault_name, ingest, newest_write)

    ingest_ledger_summary, ledger_mailboxes = ingest_ledger_block(paraos_home)

    loose = build_loose(vault, entries, vault_name, ledger_mailboxes)
    subdirectories = subdirectories_block(vault)
    items = {
        "loose": loose, "subdirectories": subdirectories,
        "empty": not loose and not subdirectories,
        "only_subdirectories": not loose and bool(subdirectories),
        "subdirectories_line": subdirectories_line(subdirectories),
        "same_thread": same_thread_block(loose),
    }

    seen_ledger = seen_ledger_block(paraos_home, vault_name)

    report = {
        "vault": vault_info, "sources": sources, "ingest": ingest,
        "ingest_ledger": ingest_ledger_summary, "items": items,
        "seen_ledger": seen_ledger, "over_threshold": over_threshold_block(vault),
        "snapshot": build_snapshot(vault),
        "snapshot_folders": [str(abspath(vault / "triage"))],
    }
    if threads_data is not None:
        report["threads"] = threads_block(threads_data, Path(seen_ledger["path"]), loose)
    return report


# ------------------------------------------------------------------------------ saved copy

SAVED_KEEP_DAYS = 7


def save_report(report, vault, paraos_home, now):
    """Keep a copy of the report outside the vault, where `paraos_vault.py changed` reads its
    snapshot before each delete or move, and return (path, error). Written by the scan so the
    re-check never depends on a run remembering to redirect its output. Copies older than a
    week are pruned; a copy that would land inside the vault is refused."""
    folder = _paraos_home(paraos_home) / "data" / "scans"
    name = re.sub(r"[^\w.-]+", "-", report["vault"]["name"] or "vault").strip("-") or "vault"
    target = folder / f"triage-{name}-{now.strftime('%Y%m%dT%H%M%S')}.json"
    try:
        target.resolve().relative_to(Path(vault).resolve())
        return None, f"{target} is inside the vault; not saved"
    except ValueError:
        pass
    report["saved_to"], report["save_error"] = str(target), None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as err:
        return None, f"cannot write {target}: {err}"
    cutoff = (now - timedelta(days=SAVED_KEEP_DAYS)).timestamp()
    for old in folder.glob("triage-*.json"):
        try:
            if old != target and old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            pass
    return str(target), None


# ------------------------------------------------------------------------------ entry point

def _parse_now(text):
    if text is None:
        return datetime.now().astimezone()
    instant = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    return instant if instant.tzinfo else instant.astimezone()


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Scan a vault for /para-triage's mechanical checks.")
    ap.add_argument("--vault", default=".", help="vault root (default: current directory)")
    ap.add_argument("--now", help="ISO-8601 instant to measure against (default: system time)")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    ap.add_argument("--threads", help="a JSON file of fetched threads to fold against staged "
                                      "notes, written by the skill after a local connector pull")
    ap.add_argument("--indent", type=int, default=None, help="pretty-print the JSON")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    try:
        now = _parse_now(args.now)
    except ValueError:
        ap.error("--now wants an ISO-8601 instant")

    threads_data = None
    if args.threads:
        try:
            threads_data = json.loads(Path(args.threads).read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            ap.error(f"cannot read {args.threads}: {err}")
        if not isinstance(threads_data, list):
            ap.error(f"{args.threads} must hold a JSON list")

    root = Path(args.vault).resolve()
    entries = registry(args.paraos_home)
    info = vault_block(root, entries)
    if not info["root"]:
        json.dump({"vault": info}, sys.stdout, ensure_ascii=False, indent=args.indent)
        sys.stdout.write("\n")
        hint = f" (registry: {info['hint']['name']} at {info['hint']['path']})" \
            if info["hint"] else ""
        print(f"triage_scan: not a vault root: {root} (missing "
              f"{', '.join(info['missing'])}){hint}", file=sys.stderr)
        return 3

    report = plan(root, args.paraos_home, now, threads_data)
    report["saved_to"], report["save_error"] = save_report(report, root, args.paraos_home, now)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
