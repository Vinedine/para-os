#!/usr/bin/env python3
"""Steps 1 to 4 of /para-ingest, everything but the routing judgment.

    py -3 ingest_scan.py prepare --mode preview|write [--days N] [--now <ISO-8601>]
                                 [--paraos-home DIR]
    py -3 ingest_scan.py route --work <dir> [--connectors <threads.json>]
                               [--unread <mailbox> ...] [--paraos-home DIR]

`prepare` reads the registry and each active vault's `## Triage sources`, skips a row a
`pulled by` marker reserves for another roster writer, and groups the connector and
fetch-script rows by mailbox. A vault with no readable `CLAUDE.md` is an error row that stays
a candidate for the mailboxes the newest run log listed it under.

It re-checks the newest earlier write log's `undelivered`: a record is `resolved` where the
ingest ledger's watermark reaches its `received`, or where every owed vault holds the thread,
by all its `keys` in `by_message_id` or a note named for `thread_hash` in its `triage/`;
otherwise it stays `undelivered`, owing only the vaults left. Each mailbox's window then
starts, in write mode, a day before the newest earlier write run that read it (its log lists
the mailbox and no error names it), else 2 days back, or a day before a thread it still owes
where that is earlier; in preview 30 days back; `--days` sets every one. In write mode, a
mailbox no write run has read gets its `carry_over`: each thread a preview since the last
write run routed (the newest decision on it wins), absent from the ledger and older than the
window, with the `days` that reach it with a day to spare.

It runs every sync script dry and, in write mode, again with `--write` where the dry run's
last `would write: N` is 20 or fewer; a count it cannot read is an error and is never written.
It runs each fetch-script mailbox once, from the first vault declaring it whose copy exists
(as given, else under `resources/scripts/`), as `<script> fetch --account <mailbox> --days N`,
N the whole days that reach its window, and keeps the JSON list it prints. Everything lands in
a new work folder under `<paraos home>/cache/ingest/work/` (folders older than 7 days are
removed), and stdout names it with the totals, the sync and fetch runs, the skipped rows, the
errors, each drive whose every active vault is unmounted (`drives`), and the connector
mailboxes left for the model to fetch, each with its `since`.

`route` reads the fetch scripts' threads and the model's connector threads (stage.py's
thread shape without `routed` and `reason`), then, per thread:

- drops it where the ingest ledger's watermark covers its newest message, and takes out a
  candidate vault whose own triage seen-ledger (`cache/triage-email/<vault>.json`) does;
  a thread left with no candidate is dropped too;
- passes a connector thread marked `"signin": true`, which needs only its mailbox, thread id
  and each message's `received` and `message_id`, straight to the run file;
- decides it unrouted where the operator's exclusions drop it;
- applies routing rule 1. A counterparty is a sender other than the mailbox, a message its
  fetch script marks `from_owner`, and, per vault, its roster writers' card addresses. Each
  candidate vault is searched for the address in the `.md` and `.txt` files of
  `areas/network/` and every lifecycle PARA home (cut at its first placeholder), never under
  `triage/` or a `sources/` folder. Where the addresses known to just one vault all name the
  same vault, that vault decides, `contact: <address>`; otherwise the vaults the hits name
  narrow the candidates, for the model to judge.

It writes `run.json` beside the plan, ready for stage.py: every thread kept, `routed` null and
`candidates` set where undecided, with the run's `invocation`, `window_days` (its widest
window), the plan's `undelivered`, `resolved` and `carry_over`, and a `source_plan` counting
the mailboxes planned, read and errored. A fetch script that failed is errored, and so is each
connector mailbox passed as `--unread`, one the model could not read, which also lands in
`errors`. stdout holds the counts, each undecided thread's subject, sender, snippet,
candidates, `contacts` and `boards` (a domain a candidate's lifecycle homes hold an address
at: evidence, never a decision), each candidate's purpose and `Relevant when` once, and the
decided threads by subject and sender.

Refused with exit 2: no registry, a ledger that does not parse (by either command), a work
folder with no plan, a connector thread for a mailbox the plan does not hold or missing what
stage.py needs, or an `--unread` mailbox that is not a connector mailbox in the plan.
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from email.utils import parseaddr
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = next((root / "para-shared" / "scripts"
               for root in (HERE.parents[1], HERE.parents[2] / "base" / ".claude" / "skills")
               if (root / "para-shared" / "scripts" / "paraos_mail.py").is_file()), None)
if SHARED is None:
    print("ingest_scan: para-shared/ belongs beside this skill. Install it", file=sys.stderr)
    sys.exit(2)
sys.path.insert(0, str(SHARED))

from paraos_mail import (  # noqa: E402
    apply_exclusions, dedup_key, ingest_ledger, ingest_logs, load_exclusions, log_instant,
    note_name_parts, received_instant, thread_hash, watermark,
)
from paraos_vault import (  # noqa: E402
    EMAIL_RE, TEXT_SUFFIXES, down_drives, lifecycles, operator_card, paraos_home_dir,
    registry, reserved_for, roster, triage_sources, writer,
)

WINDOW_DAYS = {"write": 2, "preview": 30}
DAY = timedelta(days=1)
OVERLAP = DAY
GATE = 20
SCRIPT_TIMEOUT = 300
KEEP_WORK_DAYS = 7
SNIPPET_CAP = 300
WOULD_WRITE_RE = re.compile(r"would write:\s*(\d+)")
WROTE_RE = re.compile(r"(?<!would )wrote:\s*(\d+)")
SKIPPED_KIND = {"drive": "a drive row is /para-triage's lookup",
                "recording": "/para-triage pulls recordings in its own vault"}


def parse_now(text):
    if not text:
        return datetime.now().astimezone()
    instant = received_instant(text)
    if instant is None:
        raise ValueError(f"--now {text!r} is not an ISO-8601 instant with its offset")
    return instant


def resolve(root, declared):
    for path in (root / declared, root / "resources" / "scripts" / Path(declared).name):
        if path.is_file():
            return path
    return None


def launcher(script):
    if script.suffix == ".py":
        return [sys.executable]
    if script.suffix in (".js", ".mjs"):
        return ["node"]
    return None


def run_script(cmd, cwd):
    """(stdout, error): the error a short line, None where the command exited 0."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=SCRIPT_TIMEOUT, env=env)
    except (OSError, subprocess.TimeoutExpired) as err:
        return "", str(err)
    if done.returncode != 0:
        last = (done.stderr or done.stdout or "").strip().splitlines()
        return done.stdout, f"exit {done.returncode}: {last[-1] if last else 'no output'}"
    return done.stdout, None


def sync_run(vault, root, declared, write):
    record = {"vault": vault, "script": declared, "would_write": None, "written": 0,
              "error": None}
    script = resolve(root, declared)
    run_with = launcher(script) if script else None
    if script is None:
        record["error"] = f"{declared} not found in {vault}"
        return record
    if run_with is None:
        record["error"] = f"cannot run a {script.suffix} script"
        return record
    out, error = run_script(run_with + [str(script)], root)
    counts = WOULD_WRITE_RE.findall(out)
    if error or not counts:
        record["error"] = error or "its dry run printed no `would write: N` line: not written"
        return record
    record["would_write"] = n = int(counts[-1])
    if n > GATE:
        record["error"] = f"would write {n}, over the {GATE}-item gate: not written"
    elif write and n:
        out, error = run_script(run_with + [str(script), "--write"], root)
        wrote = WROTE_RE.findall(out)
        record["written"] = int(wrote[-1]) if wrote else n
        record["error"] = error
    return record


def fetch_run(mailbox, source, days, work, n):
    record = {"mailbox": mailbox, "vault": source["vault"], "source": source["script"].name,
              "file": None, "threads": 0, "error": None}
    run_with = launcher(source["script"])
    if run_with is None:
        record["error"] = f"cannot run a {source['script'].suffix} script"
        return record
    out, error = run_script(run_with + [str(source["script"]), "fetch", "--account", mailbox,
                                        "--days", str(days)], source["root"])
    try:
        threads = None if error else json.loads(out)
    except ValueError:
        threads = None
    if not isinstance(threads, list):
        record["error"] = error or "it printed no JSON list of threads"
        return record
    path = work / f"fetch-{n}.json"
    path.write_text(json.dumps(threads, ensure_ascii=False), encoding="utf-8")
    record.update(file=path.name, threads=len(threads))
    return record


def read_ledger(home):
    ledger = ingest_ledger(home)
    if ledger["load_error"]:
        raise ValueError(f"the ingest ledger does not parse: {ledger['load_error']}")
    return ledger


def before(log, now):
    instant = log_instant(log)
    return instant if instant and instant < now else None


def last_read(logs, mailbox, now):
    """The start of the newest write run before `now` that read `mailbox`: its log lists the
    mailbox and no error names it, the coverage /para-triage reads."""
    return next((before(log, now) for log in logs
                 if log["mode"] == "write" and before(log, now)
                 and mailbox in (log["declaring_vaults"] or {})
                 and not any(mailbox in str(e) for e in log["errors"])), None)


def delivered_to(record, vault, by_message_id, entries):
    """Every key of an undelivered record recorded against `vault`, or a note named for its
    thread in the vault's `triage/`. A missing note proves nothing: triage may have filed it."""
    keys = record.get("keys") or []
    if keys and all(vault in (by_message_id.get(k) if isinstance(by_message_id.get(k), list)
                              else []) for k in keys):
        return True
    path = (entries.get(vault) or {}).get("path")
    triage = Path(str(path)) / "triage" if path else None
    if triage is None or not triage.is_dir():
        return False
    mark = thread_hash(record["thread_id"])
    return any((note_name_parts(p.name) or {}).get("hash") == mark for p in triage.iterdir())


def recheck(logs, ledger, entries, now):
    """(still owed, resolved): the newest write log's `undelivered`, each record settled by a
    ledger entry whose watermark reaches its newest message, else vault by vault."""
    newest = next((log for log in logs if log["mode"] == "write" and before(log, now)), None)
    still, resolved = [], []
    for record in (newest or {}).get("undelivered") or []:
        if not isinstance(record, dict) or not record.get("mailbox") or not record.get("thread_id"):
            continue
        held = ledger["mailboxes"].get(record["mailbox"])
        entry = held.get(record["thread_id"]) if isinstance(held, dict) else None
        if isinstance(entry, dict) and (not record.get("received") or watermark(
                entry, record["received"])["verdict"] == "seen"):
            resolved.append(record)
            continue
        owed = record.get("owed") if isinstance(record.get("owed"), list) else []
        settled = [v for v in owed if isinstance(v, str)
                   and delivered_to(record, v, ledger["by_message_id"], entries)]
        if settled == owed:
            resolved.append(record)
        elif settled:
            still.append(dict(record, owed=[v for v in owed if v not in settled],
                              delivered=list(record.get("delivered") or []) + settled))
        else:
            still.append(record)
    return still, resolved


def window(mailbox, mode, days, logs, still, now):
    """(start, first): where this run reads `mailbox` from, and whether no write run has."""
    if mode == "preview":
        return now - timedelta(days=days or WINDOW_DAYS["preview"]), False
    read = last_read(logs, mailbox, now)
    if days:
        return now - timedelta(days=days), read is None
    start = read - OVERLAP if read else now - timedelta(days=WINDOW_DAYS["write"])
    for record in still:
        received = received_instant(record.get("received"))
        if record["mailbox"] == mailbox and received:
            start = min(start, received - OVERLAP)
    return start, read is None


def carry_over(logs, ledger, since, now):
    """Threads a preview since the last write routed in one of `since`'s mailboxes, absent
    from the ledger and older than the mailbox's start, with the `--days` that reaches them."""
    last_write = max((before(log, now) for log in logs
                      if log["mode"] == "write" and before(log, now)), default=None)
    seen, found = set(), []
    for log in logs:
        instant = before(log, now)
        if log["mode"] != "preview" or not instant or (last_write and instant <= last_write):
            continue
        for decision in log["decisions"] or []:
            if not isinstance(decision, dict):
                continue
            mailbox, thread_id = decision.get("mailbox"), decision.get("thread_id")
            if mailbox not in since or not thread_id or (mailbox, thread_id) in seen:
                continue
            seen.add((mailbox, thread_id))
            received = received_instant(decision.get("received"))
            held = ledger["mailboxes"].get(mailbox)
            if (decision.get("routed") and received and received < since[mailbox]
                    and not (isinstance(held, dict) and thread_id in held)):
                found.append({"mailbox": mailbox, "thread_id": thread_id,
                              "subject": decision.get("subject"), "routed": decision["routed"],
                              "received": decision["received"],
                              "days": math.ceil((now - received + OVERLAP) / DAY)})
    return found


def new_work_folder(home, now):
    base = home / "cache" / "ingest" / "work"
    base.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - KEEP_WORK_DAYS * 86400
    for old in base.iterdir():
        if old.is_dir() and old.stat().st_mtime < cutoff:
            shutil.rmtree(old, ignore_errors=True)
    stamp = f"{now.astimezone():%Y%m%d-%H%M%S}"
    folder, n = base / stamp, 1
    while folder.exists():
        n += 1
        folder = base / f"{stamp}-{n}"
    folder.mkdir()
    return folder


def prepare(mode, paraos_home=None, now=None, days=None):
    if mode not in WINDOW_DAYS:
        raise ValueError(f"mode is preview or write, not {mode!r}")
    home = paraos_home_dir(paraos_home)
    entries = [e for e in registry(home) if isinstance(e, dict)]
    if not entries:
        raise ValueError(f"no registry at {home / 'vaults.json'}, or it does not parse")
    now = parse_now(now) if isinstance(now, str) or now is None else now
    invocation = f"/para-ingest {mode}" + (f" --days {days}" if days else "")
    logs, ledger = ingest_logs(home), read_ledger(home)
    card = operator_card(home)
    vaults, mailboxes, syncs, skipped, errors = [], {}, [], [], []

    for entry in entries:
        if entry.get("active") is not True:
            continue
        name, root = entry.get("name"), Path(str(entry.get("path") or ""))
        if not (root / "CLAUDE.md").is_file():
            error = f"{name}: not mounted, or no CLAUDE.md at {entry.get('path')}"
            vaults.append({"name": name, "path": entry.get("path"), "declared": False,
                           "error": error})
            errors.append(error)
            continue
        sources = triage_sources(root)
        vaults.append({"name": name, "path": entry.get("path"), "declared": sources["declared"],
                       "error": None})
        writers = roster(root)
        me = writer(root, card) if writers else None
        for row in sources["rows"]:
            other = reserved_for(row, writers, me)
            if other or row["kind"] in SKIPPED_KIND:
                skipped.append({"vault": name, "source": row["source"],
                                "reason": f"pulled by {other}" if other
                                else SKIPPED_KIND[row["kind"]]})
            elif row["kind"] == "sync-script":
                syncs.append((name, root, row["path"]))
            elif row["kind"] in ("connector", "fetch-script") and row["mailbox"]:
                held = mailboxes.setdefault(row["mailbox"], {
                    "kind": row["kind"], "connector": row["connector"], "vaults": [],
                    "relevant_when": {}, "source": None})
                if name not in held["vaults"]:
                    held["vaults"].append(name)
                    held["relevant_when"][name] = row["relevant_when"]
                script = resolve(root, row["path"]) if row["path"] else None
                if held["kind"] == "fetch-script" and held["source"] is None and script:
                    held["source"] = {"vault": name, "root": root, "script": script}
            else:
                errors.append(f"{name}: source {row['source'] or row['line']} is a "
                              f"{row['type'] or 'blank'} row naming no mailbox")

    # An unmounted vault stays a candidate for what it last declared: stage.py then holds
    # its threads as undelivered instead of ledgering them as routed nowhere.
    for unread in (v["name"] for v in vaults if v["error"]):
        declared = next((log["declaring_vaults"] for log in logs
                         if any(unread in names for names in
                                (log["declaring_vaults"] or {}).values())), {})
        for mailbox, names in declared.items():
            if unread in names and mailbox in mailboxes:
                mailboxes[mailbox]["vaults"].append(unread)
                mailboxes[mailbox]["relevant_when"][unread] = ""

    still, resolved = recheck(logs, ledger, {e.get("name"): e for e in entries}, now)
    starts, first = {}, {}
    for mailbox, held in mailboxes.items():
        starts[mailbox], unwritten = window(mailbox, mode, days, logs, still, now)
        held["since"] = starts[mailbox].isoformat()
        if unwritten:
            first[mailbox] = starts[mailbox]
    reach = {mb: math.ceil((now - start) / DAY) for mb, start in starts.items()}

    work = new_work_folder(home, now)
    sync_runs = [sync_run(v, root, declared, mode == "write") for v, root, declared in syncs]
    fetch_runs = []
    for mailbox, held in mailboxes.items():
        if held["kind"] != "fetch-script":
            continue
        if held["source"] is None:
            fetch_runs.append({"mailbox": mailbox, "vault": None, "source": None, "file": None,
                               "threads": 0, "error": "no declaring vault holds its script"})
        else:
            fetch_runs.append(fetch_run(mailbox, held["source"], reach[mailbox], work,
                                        len(fetch_runs) + 1))
    errors += [f"{r['vault']}: {r['script']}: {r['error']}" for r in sync_runs if r["error"]]
    errors += [f"{r['mailbox']}: {r['error']}" for r in fetch_runs if r["error"]]

    plan = {"mode": mode, "invocation": invocation, "started_at": now.isoformat(),
            "window_days": max(reach.values(), default=days or WINDOW_DAYS[mode]),
            "mailboxes": {mb: {k: held[k] for k in ("kind", "connector", "vaults",
                                                     "relevant_when", "since")}
                          for mb, held in mailboxes.items()},
            "purposes": {e.get("name"): e.get("purpose") for e in entries},
            "sync_runs": sync_runs, "fetch_runs": fetch_runs, "skipped": skipped,
            "errors": errors, "undelivered": still, "resolved": resolved,
            "carry_over": carry_over(logs, ledger, first, now)}
    (work / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
    return {"work": work.as_posix(), "mode": mode, "started_at": plan["started_at"],
            "totals": {"vaults": sum(1 for v in vaults if not v["error"]),
                       "mailboxes": len(mailboxes), "script_runs": len(syncs)},
            "vaults": vaults,
            "connectors": [{"mailbox": mb, "connector": held["connector"],
                            "vaults": held["vaults"], "relevant_when": held["relevant_when"],
                            "since": held["since"]}
                           for mb, held in mailboxes.items() if held["kind"] == "connector"],
            "fetch_scripts": fetch_runs, "sync_runs": sync_runs, "skipped": skipped,
            "errors": errors,
            "drives": down_drives([(v["name"], v["path"], bool(v["error"])) for v in vaults])}


# --- route ----------------------------------------------------------------------------------

def address(value):
    return parseaddr(str(value or ""))[1].lower()


def home_paths(root):
    """`areas/network/` and every lifecycle PARA home, each cut at its first placeholder."""
    homes = [root / "areas" / "network"]
    for lifecycle in lifecycles(root):
        for stage in lifecycle["stages"]:
            parts = []
            for part in re.sub(r"[{}]", "", stage["home"]).split("/"):
                if "<" in part:
                    break
                parts.append(part)
            if any(parts):
                homes.append(root.joinpath(*[p for p in parts if p]))
    return homes


def addresses_in(root, homes):
    """Every address in the text files under `homes`, outside `triage/` and `sources/`."""
    found = set()
    for home in homes:
        files = [home] if home.is_file() else sorted(home.rglob("*")) if home.is_dir() else []
        for path in files:
            parts = path.relative_to(root).parts
            if (path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file()
                    or "sources" in parts or parts[0] == "triage"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            found.update(a.lower() for a in EMAIL_RE.findall(text))
    return found


class VaultIndex:
    """Per vault, read once: the addresses rule 1 searches, its writers' and its boards'."""

    def __init__(self, entries):
        self.entries, self.cache = entries, {}

    def get(self, name):
        if name not in self.cache:
            root = Path(str(self.entries[name].get("path")))
            known = addresses_in(root, home_paths(root))
            boards = addresses_in(root, home_paths(root)[1:])
            writers = set()
            for row in roster(root) or []:
                cards = sorted((root / "areas" / "network").rglob(f"{row['card']}.md"))
                writers |= addresses_in(root, cards)
            self.cache[name] = {"known": known - writers,
                                "domains": {a.split("@", 1)[1] for a in boards - writers}}
        return self.cache[name]


def seen_by_vault(home, vault, thread_id, newest_date, newest_key):
    path = home / "cache" / "triage-email" / f"{vault}.json"
    try:
        entry = json.loads(path.read_text(encoding="utf-8")).get(thread_id)
    except (OSError, ValueError, AttributeError):
        return False
    return isinstance(entry, dict) and \
        watermark(entry, newest_date, newest_key)["verdict"] == "seen"


def from_fetch_script(record, mailbox, source):
    messages = [{k: m.get(k) for k in ("message_id", "from", "from_name", "from_owner", "to",
                                       "cc", "received", "subject", "preview", "id")
                 if m.get(k) is not None}
                for m in record.get("messages") or [record] if isinstance(m, dict)]
    return {"mailbox": mailbox, "source": source, "thread_id": record.get("thread_id"),
            "subject": record.get("subject"), "link": record.get("link"),
            "read": record.get("read"), "text": "preview", "own_messages": False,
            "messages": messages}


THREAD_FIELDS = ("mailbox", "source", "thread_id", "link", "text", "own_messages")


def as_planned(plan, mailbox):
    """`mailbox` as the plan spells it, matched in any case, else as given."""
    given = str(mailbox).strip()
    return next((mb for mb in plan["mailboxes"] if mb.lower() == given.lower()), given)


def connector_threads(path, plan):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} holds no JSON list of threads")
    for n, thread in enumerate(data, 1):
        where = f"connector thread {n}"
        if not isinstance(thread, dict):
            raise ValueError(f"{where}: not an object")
        where += f" ({thread.get('thread_id')})" if thread.get("thread_id") else ""
        signin = thread.get("signin") is True
        for field in ("mailbox", "thread_id") if signin else THREAD_FIELDS:
            if thread.get(field) in (None, ""):
                raise ValueError(f"{where}: no {field}")
        thread["mailbox"] = as_planned(plan, thread["mailbox"])
        if thread["mailbox"] not in plan["mailboxes"]:
            raise ValueError(f"{where}: mailbox {thread['mailbox']} is not in the plan")
        if not thread.get("messages"):
            raise ValueError(f"{where}: no messages")
    return data


def newest_of(thread, where):
    dated = []
    for m, message in enumerate(thread.get("messages") or [], 1):
        instant = received_instant(message.get("received")) if isinstance(message, dict) else None
        if instant is None:
            raise ValueError(f"{where} message {m}: received is not an instant with its offset")
        dated.append((instant, message))
    if not dated:
        raise ValueError(f"{where}: no messages")
    instant, message = max(dated, key=lambda pair: pair[0])
    try:
        key = dedup_key(dict(message, mailbox=thread["mailbox"]))
    except ValueError as err:
        raise ValueError(f"{where}: {err}") from None
    return instant, message, key


def rule_one(thread, candidates, index):
    """(decided vault, address) or (None, None), and the hits: address to candidate vaults."""
    owner = {thread["mailbox"].lower()} | {address(m.get("from")) for m in thread["messages"]
                                           if m.get("from_owner")}
    senders = []
    for message in sorted(thread["messages"], key=lambda m: str(m.get("received"))):
        sender = address(message.get("from"))
        if sender and sender not in owner and sender not in senders:
            senders.append(sender)
    hits = {}
    for sender in senders:
        vaults = [v for v in candidates if sender in index.get(v)["known"]]
        if vaults:
            hits[sender] = vaults
    single = {vaults[0] for vaults in hits.values() if len(vaults) == 1}
    if len(single) == 1:
        vault = single.pop()
        return vault, next(a for a, vs in hits.items() if vs == [vault]), hits
    return None, None, hits


def route(work, connectors=None, paraos_home=None, unread=()):
    work = Path(work)
    try:
        plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ValueError(f"no plan in {work}: {err}") from None
    unread = sorted({as_planned(plan, mb) for mb in unread or ()})
    for mailbox in unread:
        if (plan["mailboxes"].get(mailbox) or {}).get("kind") != "connector":
            raise ValueError(f"--unread {mailbox}: not a connector mailbox in the plan")
    home = paraos_home_dir(paraos_home)
    entries = {e.get("name"): e for e in registry(home) if isinstance(e, dict)}
    if not entries:
        raise ValueError(f"no registry at {home / 'vaults.json'}, or it does not parse")
    ledger = read_ledger(home)

    threads = []
    for run in plan["fetch_runs"]:
        if run.get("file"):
            records = json.loads((work / run["file"]).read_text(encoding="utf-8"))
            threads += [from_fetch_script(r, run["mailbox"], run["source"]) for r in records
                        if isinstance(r, dict)]
    if connectors:
        threads += connector_threads(connectors, plan)

    counts = {"fetched": len(threads), "already_seen": 0, "signin": 0, "excluded": 0,
              "decided": 0, "to_judge": 0}
    kept, signins = [], []
    for n, thread in enumerate(threads, 1):
        where = f"thread {n} ({thread.get('mailbox')} {thread.get('thread_id')})"
        instant, newest, key = newest_of(thread, where)
        held = ledger["mailboxes"].get(thread["mailbox"])
        before = held.get(thread["thread_id"]) if isinstance(held, dict) else None
        before = before if isinstance(before, dict) else None
        if before and watermark(before, instant.isoformat(), key)["verdict"] == "seen":
            counts["already_seen"] += 1
            continue
        if thread.get("signin") is True:
            signins.append(thread)
            continue
        candidates = [v for v in plan["mailboxes"][thread["mailbox"]]["vaults"]
                      if not seen_by_vault(home, v, thread["thread_id"], instant.isoformat(), key)]
        if not candidates:
            counts["already_seen"] += 1
            continue
        kept.append(dict(thread, candidates=candidates, resurfaced=before is not None,
                         newest=newest, routed=None, reason=None))

    exclusions, _ = load_exclusions(home)
    survivors, dropped, _ = apply_exclusions(kept, exclusions)
    counts["excluded"] = len(dropped)
    index = VaultIndex(entries)
    to_judge, decided, vaults = [], [], {}
    for thread in survivors:
        vault, hit, hits = rule_one(thread, thread["candidates"], index)
        newest = thread["newest"]
        line = {"mailbox": thread["mailbox"], "thread_id": thread["thread_id"],
                "subject": thread.get("subject") or newest.get("subject"),
                "from": newest.get("from")}
        if vault:
            thread.update(routed=[vault], reason=f"contact: {hit}")
            decided.append(dict(line, routed=[vault], reason=thread["reason"]))
            continue
        if hits:
            single = sorted({vs[0] for vs in hits.values() if len(vs) == 1})
            named = single or sorted({v for vs in hits.values() for v in vs})
            thread["candidates"] = [v for v in thread["candidates"] if v in named]
        snippet = " ".join(str(newest.get("preview") or newest.get("text") or "").split())
        item = dict(line, received=newest.get("received"), snippet=snippet[:SNIPPET_CAP],
                    candidates=thread["candidates"], resurfaced=thread["resurfaced"])
        if hits:
            item["contacts"] = hits
        domains = {address(m.get("from")).partition("@")[2] for m in thread["messages"]}
        boards = {d: [v for v in thread["candidates"] if d in index.get(v)["domains"]]
                  for d in sorted(domains) if d}
        if any(boards.values()):
            item["boards"] = {d: vs for d, vs in boards.items() if vs}
        to_judge.append(item)
        for v in thread["candidates"]:
            vaults.setdefault(v, {
                "purpose": plan["purposes"].get(v),
                "relevant_when": {mb: held["relevant_when"][v]
                                  for mb, held in plan["mailboxes"].items()
                                  if v in held["relevant_when"]}})
    counts.update(signin=len(signins), decided=len(decided), to_judge=len(to_judge))

    errored = sum(1 for r in plan["fetch_runs"] if r["error"]) + len(unread)
    run = {"mode": plan["mode"], "invocation": plan.get("invocation"),
           "window_days": plan["window_days"], "started_at": plan["started_at"],
           "source_plan": {"declaring_vaults": {mb: held["vaults"]
                                                for mb, held in plan["mailboxes"].items()},
                           "mailboxes": len(plan["mailboxes"]),
                           "mailboxes_read": len(plan["mailboxes"]) - errored,
                           "mailboxes_errored": errored},
           "sync_runs": [{k: r[k] for k in ("vault", "script", "written", "error")}
                         for r in plan["sync_runs"]],
           "errors": plan["errors"] + [f"{mb}: connector could not be read" for mb in unread],
           "undelivered": plan["undelivered"], "resolved": plan["resolved"],
           "carry_over": plan["carry_over"],
           "threads": [{k: v for k, v in t.items() if k not in ("newest", "resurfaced")}
                       for t in survivors + dropped] + signins}
    path = work / "run.json"
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"run": path.as_posix(), "counts": counts, "vaults": vaults, "to_judge": to_judge,
            "decided": decided}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Plan, fetch and prepare the routing of one "
                                             "/para-ingest run.")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="plan the run, run the sync and fetch scripts")
    p.add_argument("--mode", choices=sorted(WINDOW_DAYS), required=True)
    p.add_argument("--days", type=int)
    p.add_argument("--now", help="ISO-8601 instant with offset (default: now)")
    r = sub.add_parser("route", help="check fetched threads, apply rule 1, write run.json")
    r.add_argument("--work", required=True, help="the folder prepare printed")
    r.add_argument("--connectors", help="the connector threads the model fetched, as JSON")
    r.add_argument("--unread", action="append", default=[], metavar="MAILBOX",
                   help="a connector mailbox the model could not read (repeatable)")
    for parser in (p, r):
        parser.add_argument("--paraos-home", help="override for $PARAOS_HOME")
    args = ap.parse_args(argv)

    # A Windows console defaults to a codepage that cannot encode a subject.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    try:
        if args.command == "prepare":
            out = prepare(args.mode, args.paraos_home, parse_now(args.now), args.days)
        else:
            out = route(args.work, args.connectors, args.paraos_home, args.unread)
    except ValueError as err:
        ap.error(str(err))
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
