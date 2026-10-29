#!/usr/bin/env python3
"""Step 5 of /para-ingest: the staged notes, the central ledger and the run log, written from
one run's fetched and routed threads.

    py -3 stage.py <run.json> [--paraos-home DIR]

`<run.json>` is the run so far, as one JSON object:

    {"mode": "preview" | "write", "started_at": "<ISO-8601 with offset, default now>",
     "source_plan": {"declaring_vaults": {<mailbox>: [<vault>, ...]}, ...},
     "threads": [{
        "mailbox", "source" (the connector or fetch script), "thread_id", "subject", "link",
        "conversation_id" (where the source has one),
        "read" (the newest message's id as the source's read tool takes it, or a fetch
                script's read command; a message's own `read` wins),
        "routed": [<registry name>, ...], "reason" (routing.md's),
        "text": "preview" | "body" (what stands in for each message),
        "own_messages": whether the operator's own messages were fetched,
        "messages": [{"message_id", "from", "from_name", "received", "subject",
                      "text" (else "preview")}, ...]
     }, ...]}

A fetch script's thread record passes as it is, with the routing fields added. Every fetched
thread is passed, routed or not. A sign-in or security code is `"signin": true` with only
its `mailbox`, `thread_id`, and each message's `received` and `message_id`, else
`provider_id`. Every other key (`sync_runs`, `errors`, `carry_over`, `resolved`, ...) is
copied into the log as given.

Refused with exit 2 before anything is written: a route to a vault the registry does not
list as active, a routed thread missing what its note needs, a message no dedup key or
received instant fits, an unparseable ledger or registry, or a run whose log already exists.

What it does, threads with the most messages first so the best-grouped copy of a
conversation stages and `by_message_id` suppresses the others:

- Each message is keyed by `paraos_mail.dedup_key`. A thread the ledger already holds keeps
  only the messages after its watermark (connectors.md step 5).
- Per routed vault, the messages `by_message_id` already records against it are dropped, and
  a vault left with none is `suppressed`. A vault whose path is not a folder holding
  `CLAUDE.md`, or whose note cannot be written, is `owed`.
- The note is `<triage>/YYYYMMDD <subject> <thread_hash>.md`, dated by its newest message in
  local time, the subject's path-hostile characters made spaces and capped. A note already
  there with the same `Message id` is this one: nothing is written. Another takes ` 2`, ` 3`.
  It is never overwritten.
- The ledger entry is written only when no vault is owed, its watermark the newest message
  and never moved back, its `routed` the union with what it held. A sign-in code is
  ledgered with no subject and staged nowhere.
- In preview the same decisions are made and only the log is written.

The log, `runs/YYYYMMDD-HHMMSS.json` by `started_at` in local time, holds `mode`,
`started_at`, `files_written` (every note written), `counts` (`per_vault` with 0 for every
vault the source plan or a route names, `unrouted` and `signin_codes` per mailbox),
`decisions` (one per thread), `undelivered` (owed vaults, with the keys of the messages
owed), `suppressed`, and in preview
`outside_write_window` (routed threads whose newest message is older than the write window).
stdout is the same minus the decisions and what was copied, plus the log's path.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from email.utils import parseaddr
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = next((root / "para-shared" / "scripts"
               for root in (HERE.parents[1], HERE.parents[2] / "base" / ".claude" / "skills")
               if (root / "para-shared" / "scripts" / "paraos_mail.py").is_file()), None)
if SHARED is None:
    print("stage: para-shared/ belongs beside this skill. Install it", file=sys.stderr)
    sys.exit(2)
sys.path.insert(0, str(SHARED))

from paraos_mail import (  # noqa: E402
    apply_exclusions, dedup_key, load_exclusions, received_instant, thread_hash, watermark,
)
from paraos_vault import paraos_home_dir, registry  # noqa: E402

WRITE_WINDOW_DAYS = 2
SIGNIN = "sign-in or security code"
SUBJECT_CAP = 80
HOSTILE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
EDGES_RE = re.compile(r"^[ .]+|[ .]+$")
MESSAGE_ID_RE = re.compile(r"^- \*\*Message id:\*\* (.*)$", re.MULTILINE)


def safe_subject(subject):
    text = " ".join(HOSTILE_RE.sub(" ", str(subject or "")).split())
    return EDGES_RE.sub("", EDGES_RE.sub("", text)[:SUBJECT_CAP]) or "no subject"


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def sender(message):
    name, address = parseaddr(str(message.get("from") or ""))
    name = name or message.get("from_name")
    return f"{name} <{address}>" if name and address else address


def checked(run, vaults):
    """The run's threads, each message carrying its `instant` and `key`, oldest first."""
    if run.get("mode") not in ("preview", "write"):
        raise ValueError(f"mode is preview or write, not {run.get('mode')!r}")
    threads = []
    for n, thread in enumerate(run.get("threads") or [], 1):
        where = f"thread {n}"
        if not isinstance(thread, dict):
            raise ValueError(f"{where}: not an object")
        signin = thread.get("signin") is True
        routed = [] if signin else list(thread.get("routed") or [])
        for name in routed:
            if (vaults.get(name) or {}).get("active") is not True:
                raise ValueError(f"{where}: routed to {name}, which the registry does not "
                                 "list as active")
        needed = ["mailbox", "thread_id"] + ([] if signin else ["reason"])
        if routed:
            needed += ["source", "link", "text", "own_messages"]
        for field in needed:
            if thread.get(field) in (None, ""):
                raise ValueError(f"{where}: no {field}")
        if routed and thread["text"] not in ("preview", "body"):
            raise ValueError(f"{where}: text is preview or body, not {thread['text']!r}")
        messages = []
        for m, message in enumerate(thread.get("messages") or [], 1):
            spot = f"{where} message {m}"
            if not isinstance(message, dict):
                raise ValueError(f"{spot}: not an object")
            instant = received_instant(message.get("received"))
            if instant is None:
                raise ValueError(f"{spot}: received {message.get('received')!r} is not an "
                                 "instant with its offset")
            try:
                key = dedup_key(dict(message, mailbox=thread["mailbox"]))
            except ValueError as err:
                raise ValueError(f"{spot}: {err}") from None
            messages.append(dict(message, instant=instant, key=key))
        if not messages:
            raise ValueError(f"{where}: no messages")
        messages.sort(key=lambda message: message["instant"])
        if routed and not (messages[-1].get("read") or thread.get("read")):
            raise ValueError(f"{where}: no read for its newest message")
        threads.append(dict(thread, signin=signin, routed=routed, messages=messages))
    return threads


def load_ledger(path):
    if not path.is_file():
        return {"mailboxes": {}, "by_message_id": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ValueError(f"the ledger at {path} does not parse: {err}") from None
    if not isinstance(data, dict) or not all(isinstance(data.get(k, {}), dict)
                                             for k in ("mailboxes", "by_message_id")):
        raise ValueError(f"the ledger at {path} is not the ledger's shape")
    data.setdefault("mailboxes", {})
    data.setdefault("by_message_id", {})
    return data


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def reachable(entry):
    root = Path(entry["path"])
    return root.is_dir() and (root / "CLAUDE.md").is_file()


def render_note(thread, subject, messages, read, routed_line, content_line):
    newest = messages[-1]
    lines = [f"# {subject or 'no subject'}", "",
             f"- **Source:** {thread['source']} ({thread['mailbox']})",
             f"- **From:** {sender(newest)}",
             f"- **Received:** {newest['instant'].isoformat()}",
             f"- **Routed:** {routed_line}",
             f"- **Content:** {content_line}",
             f"- **Link:** {thread['link']}",
             f"- **Message id:** {read}"]
    if thread.get("conversation_id"):
        lines.append(f"- **Conversation id:** {thread['conversation_id']}")
    for message in messages:
        text = str(message.get("text") or message.get("preview") or "").strip()
        lines += ["", f"**{sender(message)}**, {message['instant'].isoformat()}", "",
                  text or "(no text)"]
    return "\n".join(lines) + "\n"


def note_path(triage, stem, read):
    """(path, already there): a note of this stem whose `Message id` is `read` is this note;
    otherwise the first free name of `<stem>.md`, `<stem> 2.md`, ..."""
    names = {p.name for p in triage.iterdir()} if triage.is_dir() else set()
    for name in sorted(names):
        if name == f"{stem}.md" or (name.startswith(f"{stem} ") and name.endswith(".md")):
            try:
                text = (triage / name).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            found = MESSAGE_ID_RE.search(text)
            if found and found.group(1).strip() == read:
                return triage / name, True
    n = 1
    while (f"{stem}.md" if n == 1 else f"{stem} {n}.md") in names:
        n += 1
    return triage / (f"{stem}.md" if n == 1 else f"{stem} {n}.md"), False


def stage(run, paraos_home=None):
    home = paraos_home_dir(paraos_home)
    vaults = {e.get("name"): e for e in registry(home) if isinstance(e, dict)}
    if not vaults:
        raise ValueError(f"no registry at {home / 'vaults.json'}, or it does not parse")
    threads = checked(run, vaults)
    exclusions, exclusions_error = load_exclusions(home)
    kept, dropped, exclusion_counts = apply_exclusions(threads, exclusions)
    threads = kept + dropped     # a dropped thread still reaches the ledger, as excluded
    ledger_path = home / "cache" / "ingest" / "ledger.json"
    ledger = load_ledger(ledger_path)
    started = received_instant(run.get("started_at")) or datetime.now().astimezone()
    log_path = home / "cache" / "ingest" / "runs" / f"{started.astimezone():%Y%m%d-%H%M%S}.json"
    if log_path.exists():
        raise ValueError(f"{log_path} exists: this run was staged already")
    write = run["mode"] == "write"
    by_message_id = ledger["by_message_id"]

    def recorded(key):
        vaults_for = by_message_id.get(key)
        return vaults_for if isinstance(vaults_for, list) else []

    plan = run.get("source_plan") if isinstance(run.get("source_plan"), dict) else {}
    declaring = plan.get("declaring_vaults")
    covered = [v for names in (declaring.values() if isinstance(declaring, dict) else [])
               if isinstance(names, list) for v in names]
    per_vault = {name: 0 for name in covered + [v for t in threads for v in t["routed"]]}
    unrouted, signin_codes, excluded = {}, {}, {}
    files_written, decisions, undelivered, suppressed, errors = [], [], [], [], []

    for thread in sorted(threads, key=lambda t: -len(t["messages"])):
        mailbox, thread_id, messages = thread["mailbox"], thread["thread_id"], thread["messages"]
        held = ledger["mailboxes"].get(mailbox)
        held = held if isinstance(held, dict) else {}
        before = held.get(thread_id) if isinstance(held.get(thread_id), dict) else None
        mark = received_instant(watermark(before)["watermark"]) if before else None
        fresh = [m for m in messages if mark is None or m["instant"] > mark]
        newest = messages[-1]
        subject = SIGNIN if thread["signin"] else \
            " ".join(str(thread.get("subject") or newest.get("subject") or "").split())
        reason = SIGNIN if thread["signin"] else thread["reason"]
        routed_line = reason
        earlier = (before or {}).get("routed") or []
        if before:
            disposition = f"routed to {', '.join(earlier)}" if earlier else "unrouted"
            day = before.get("date") or str(before.get("seen_date") or "")[:10]
            routed_line += (f"; resurfaced; previously {disposition} {day}, "
                            f"reason: {before.get('reason')}")
        decision = {"mailbox": mailbox, "thread_id": thread_id, "subject": subject,
                    "received": newest["instant"].isoformat(), "routed": thread["routed"],
                    "reason": reason, "resurfaced": before is not None,
                    "staged": [], "suppressed": [], "owed": []}

        for name in thread["routed"]:
            entry = vaults[name]
            todo = [m for m in fresh if name not in recorded(m["key"])]
            if not todo:
                decision["suppressed"].append(name)
                continue
            if not reachable(entry):
                decision["owed"].append(name)
                continue
            content = (f"full text of {plural(len(todo), 'message')}" if thread["text"] == "body"
                       else f"preview of {plural(len(todo), 'message')}, not the full text")
            if not thread["own_messages"]:
                content += "; own messages not fetched"
            if len(messages) > len(todo):
                content += (f"; {plural(len(messages) - len(todo), 'earlier message')} left "
                            "out, already seen")
            triage = Path(entry["path"]) / "triage"
            stem = (f"{todo[-1]['instant'].astimezone():%Y%m%d} {safe_subject(subject)} "
                    f"{thread_hash(thread_id)}")
            read = str(todo[-1].get("read") or thread.get("read"))
            try:
                path, already = note_path(triage, stem, read)
                if write and not already:
                    triage.mkdir(exist_ok=True)
                    with path.open("x", encoding="utf-8") as note:
                        note.write(render_note(thread, subject, todo, read, routed_line,
                                               content))
                    files_written.append(path.as_posix())
            except OSError as err:
                errors.append(f"{name}: {err}")
                decision["owed"].append(name)
                continue
            for message in todo:
                by_message_id[message["key"]] = recorded(message["key"]) + [name]
            if already:
                decision["suppressed"].append(name)
                continue
            decision["staged"].append(name)
            per_vault[name] += 1

        if thread["signin"]:
            signin_codes[mailbox] = signin_codes.get(mailbox, 0) + 1
        elif thread.get("excluded"):
            excluded[mailbox] = excluded.get(mailbox, 0) + 1
        elif not thread["routed"]:
            unrouted[mailbox] = unrouted.get(mailbox, 0) + 1
        if decision["suppressed"]:
            suppressed.append({"mailbox": mailbox, "thread_id": thread_id, "subject": subject,
                               "vaults": decision["suppressed"]})
        if decision["owed"]:
            undelivered.append({"mailbox": mailbox, "thread_id": thread_id, "subject": subject,
                                "routed": thread["routed"],
                                "delivered": [v for v in thread["routed"]
                                              if v not in decision["owed"]],
                                "owed": decision["owed"], "keys": [m["key"] for m in fresh]})
        elif fresh:
            held[thread_id] = {
                "routed": earlier + [v for v in thread["routed"] if v not in earlier],
                "reason": reason, "date": f"{newest['instant'].astimezone():%Y-%m-%d}",
                "subject": subject, "seen_through": newest["key"],
                "seen_date": newest["instant"].isoformat()}
            ledger["mailboxes"][mailbox] = held
        decisions.append(decision)

    if write:
        write_json(ledger_path, ledger)
    summary = {"mode": run["mode"], "started_at": started.isoformat(),
               "files_written": files_written,
               "counts": {"per_vault": per_vault, "unrouted": unrouted,
                          "signin_codes": signin_codes, "excluded": excluded},
               "exclusions_applied": {"by_entry": exclusion_counts, "dropped": len(dropped),
                                      "file": exclusions_error or "applied"},
               "undelivered": undelivered, "suppressed": suppressed}
    if not write:
        cutoff = started - timedelta(days=WRITE_WINDOW_DAYS)
        summary["outside_write_window"] = [
            {k: d[k] for k in ("mailbox", "thread_id", "subject", "routed", "received")}
            for d in decisions if d["routed"] and received_instant(d["received"]) < cutoff]
    given = {k: v for k, v in run.items() if k != "threads"}
    log = dict(given, **summary, decisions=decisions,
               errors=list(run.get("errors") or []) + errors)
    write_json(log_path, log)
    return dict(summary, errors=log["errors"], log=log_path.as_posix())


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stage one /para-ingest run: its notes, the "
                                             "ledger and the run log.")
    ap.add_argument("run", help="the run's routed threads, as JSON (this script's docstring)")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    args = ap.parse_args(argv)

    # A Windows console defaults to a codepage that cannot encode a subject.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    try:
        run = json.loads(Path(args.run).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        ap.error(f"cannot read {args.run}: {err}")
    if not isinstance(run, dict):
        ap.error(f"{args.run} holds no JSON object")
    try:
        summary = stage(run, args.paraos_home)
    except ValueError as err:
        ap.error(str(err))
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
