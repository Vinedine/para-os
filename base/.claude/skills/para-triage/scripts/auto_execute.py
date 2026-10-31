#!/usr/bin/env python3
"""The only writer of an unattended /para-triage run, and the decision ledger both paths keep.

    py -3 auto_execute.py run --scan <saved scan> --decisions <file.json> [--cap 25]
    py -3 auto_execute.py restore --vault-name <name> --run <run> [--item <name>]
    py -3 auto_execute.py status --vault-name <name> [--vault <root>]
    py -3 auto_execute.py record --vault-name <name> --decisions <file.json> [--scan <saved scan>]
                                 [--proposal <path>]
    py -3 auto_execute.py switch --vault-name <name> (--on | --off) <action>
    py -3 auto_execute.py add-exclusion --mailbox <mailbox> (--from <address> | --domain <domain>)
                                        --reason <text>
    py -3 auto_execute.py purge [--days 30]

Every command takes `--paraos-home DIR`, and prints one JSON document. State lives under the
para-os home, never in a vault:

    auto-triage.json                    {vault name: {"on": [action], "demoted": [...]}}
    auto-triage.off                     the kill switch: while it exists, `run` acts on nothing
    cache/triage/decisions/<vault>.jsonl  one line per decided item, from either path, with the
                                        sender's address (`from`) and `mailbox` where known
    cache/triage/proposals/<vault>-<YYYYMMDD-HHMM>.md  what a run left for the operator
    quarantine/<vault>/<run>/           the items a run took out, with manifest.json
    triage-exclusions.json              read by the fetch; `add-exclusion` is this script's write

`run` reads the triage scan's saved copy (`saved_to`) and a decisions file, a JSON list of
`{"item", "action", "reason", "survivor", "hold"}`, plus `entity` and `name` for `File it`,
and removes the decisions file once the run is written; one older than the scan is refused,
and removed. An item is acted on only where its action is switched on for this vault, it
carries no `hold`, it is a loose file of the scan, its bytes still match the scan's
snapshot, and the run is under `--cap`; and per action:

- `Delete (...)`, `Dismiss (...)`: the scan lists no inbound link to it and, for
  `Delete (duplicate)`, a byte match. Acting moves it into the quarantine, never deletes it.
- `File it`: the vault root is the top of a git working tree, `entity` is one of its projects, areas or
  ideas as `paraos_vault.py` lists them, and `name` is a bare file name with the item's
  extension and no leading dot, with nothing at `<entity>/sources/<name>`. Acting is
  `paraos_vault.py move`, which repoints inbound links and may create `sources/`, nothing else.

Everything else goes into the run's proposal, with each item's name, size, mtime and md5, and
`refused` says why. The whole run is refused while the kill switch exists, and for a vault
whose `CLAUDE.md` has a `## Who writes this vault` roster. A run commits what `File it`
moved and the links it rewrote, by name, one commit per run (`commit`); a quarantine move is
the operator's to commit.

`restore` moves a run's items back, a filed one through the same move, checks each md5,
switches the item's action off for the vault (`demoted`), and commits a filed one's return.
`status` reads the switched-on actions, the kill switch, the runs and proposal waiting since
the last interactive decision, each proposed item as `unchanged`, `changed` or `missing`,
`nothing_new` with `--vault` (every loose file a proposed item, unchanged: a scheduled run
skips the vault), and `offers`: each `Delete` or `Dismiss` action whose last 50 interactive
decisions in the vault were at least 95% the recommendation unchanged, not yet switched on;
the ledger holds no destination, so `File it` is switched on by the operator, never offered. `record` appends the interactive path's decisions, `{"item", "recommended",
"chosen"}` plus a fetched thread's `from` and `mailbox`, which `--scan` fills for a staged
note from its `From` line, and moves a decided proposal into `proposals/decided/`.

Both return `exclusion_offers`, `status` for the unattended decisions since the last
interactive one, `record` for the rows it appended: each sender such a `Dismiss (noise)` names
whose address or domain the ledger shows dismissed as noise at least twice in that mailbox,
and that the exclusions file does not hold for the mailbox or `*`. Its `entry` is a `domain`
where those dismissals span several addresses of it, else a `from`. `add-exclusion` copies the
file to `triage-exclusions.json.bak-<YYYYMMDD>` (`-<HHMMSS>` added where that exists), then
appends the entry with its `reason` and today as `added`; a file that does not parse is
refused. `switch` is the operator's standing approval, or its withdrawal. `purge` moves each
quarantined run older than `--days` to the system trash, keeping one where no trash is
reachable.

Exit codes: 0 answered; 2 the library is missing; 3 refused, `refused` saying why; 4 a
restored md5 differs.
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (entity_candidates, git, move, paraos_home_dir,  # noqa: E402
                              same_place, snapshot, trash)
except ImportError as missing:
    print(f"auto_execute: {missing}. install para-shared beside this skill", file=sys.stderr)
    sys.exit(2)

QUARANTINE_RE = re.compile(r"^(Delete|Dismiss) \(")
FILE_IT = "File it"
ENTITY_BUCKETS = ("projects", "areas", "resources/ideas")
ROSTER_RE = re.compile(r"^## Who writes this vault\s*$", re.MULTILINE)
OFFER_WINDOW, OFFER_SHARE = 50, 0.95
NOISE, SENDER = "Dismiss (noise)", ("from", "mailbox")


class Refused(Exception):
    pass


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        if default is not None:
            return default
        raise Refused(f"no such file: {path}")
    except (OSError, ValueError) as err:
        raise Refused(f"cannot read {path}: {err}")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


class State:
    def __init__(self, paraos_home, vault):
        self.home = paraos_home_dir(paraos_home)
        self.vault = vault
        self.config_path = self.home / "auto-triage.json"
        self.ledger = self.home / "cache" / "triage" / "decisions" / f"{vault}.jsonl"
        self.proposals = self.home / "cache" / "triage" / "proposals"
        self.quarantine = self.home / "quarantine" / vault

    def config(self):
        return load_json(self.config_path, {})

    def switched_on(self):
        return list(self.config().get(self.vault, {}).get("on", []))

    def switch(self, action, on, demotion=None):
        config = self.config()
        row = config.setdefault(self.vault, {"on": [], "demoted": []})
        row["on"] = sorted(set(row.get("on", [])) | {action}) if on else \
            [a for a in row.get("on", []) if a != action]
        if demotion:
            row.setdefault("demoted", []).append(demotion)
        write_json(self.config_path, config)
        return row

    def append(self, lines):
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", encoding="utf-8") as fh:
            for line in lines:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    def decisions(self):
        try:
            text = self.ledger.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        return [json.loads(ln) for ln in text.splitlines() if ln.strip()]

    def runs(self):
        if not self.quarantine.is_dir():
            return []
        return sorted(d.name for d in self.quarantine.iterdir() if (d / "manifest.json").is_file())


def now_stamp():
    return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def sender(row, entry=None):
    """`from` and `mailbox`, lowercased: a staged note's own `From` line and mailbox from the
    scan's loose `entry`, else what the row carries; empty where either is missing."""
    note = (entry or {}).get("note") or {}
    found = {"from": parseaddr((note.get("fields") or {}).get("From") or "")[1],
             "mailbox": note.get("mailbox")}
    if not all(found.values()):
        found = {k: row.get(k) for k in SENDER}
    found = {k: str(v or "").strip().lower() for k, v in found.items()}
    return found if "@" in found["from"] and found["mailbox"] else {}


def exclusions_file(home):
    return home / "triage-exclusions.json"


def held(exclusions, mailbox, value):
    """Whether the exclusions file already drops `value`, an address or a domain, for the
    mailbox or every mailbox: a `from` equal to it, or a `domain` it equals or sits under."""
    domain = value.rpartition("@")[2]
    for key in (mailbox, "*"):
        entries = exclusions.get(key)
        for entry in entries if isinstance(entries, list) else []:
            matchers = entry.get("any", [entry]) if isinstance(entry, dict) else []
            for m in matchers if isinstance(matchers, list) else []:
                if not isinstance(m, dict):
                    continue
                d = str(m.get("domain") or "").lower()
                if str(m.get("from") or "").lower() == value or \
                        d and (domain == d or domain.endswith("." + d)):
                    return True
    return False


def exclusion_offers(home, lines, triggers):
    try:
        exclusions = json.loads(exclusions_file(home).read_text(encoding="utf-8"))
    except FileNotFoundError:
        exclusions = {}
    except (OSError, ValueError):
        return []
    if not isinstance(exclusions, dict):
        return []
    noise = [ln for ln in lines if ln.get("chosen") == NOISE and ln.get("from")]
    offers, made = [], set()
    for t in triggers:
        if t.get("chosen") != NOISE or not t.get("from"):
            continue
        mailbox, domain = t["mailbox"], t["from"].rpartition("@")[2]
        same = [ln for ln in noise if ln.get("mailbox") == mailbox and
                ln["from"].rpartition("@")[2] == domain]
        senders = sorted({ln["from"] for ln in same})
        kind, value = ("domain", domain) if len(senders) > 1 else ("from", t["from"])
        if len(same) < 2 or (mailbox, value) in made or held(exclusions, mailbox, value):
            continue
        made.add((mailbox, value))
        offers.append({"mailbox": mailbox, "entry": {kind: value}, "senders": senders,
                       "items": [ln["item"] for ln in same],
                       "first": min(ln["date"] for ln in same),
                       "last": max(ln["date"] for ln in same)})
    return offers


def item_record(path):
    st = path.stat()
    return {"size": st.st_size, "mtime": int(st.st_mtime), "md5": md5(path)}


def unattended(action):
    return bool(QUARANTINE_RE.match(action)) or action == FILE_IT


def in_git(root):
    top = (git(root, ["rev-parse", "--show-toplevel"]) or "").strip()
    return bool(top) and same_place(top) == same_place(root)


def filing_target(d):
    entity = str(d.get("entity") or "").replace("\\", "/").strip("/")
    return entity, f"{entity}/sources/{d.get('name') or ''}"


def filing_refusal(root, d, item, entities):
    entity, target = filing_target(d)
    name = str(d.get("name") or "")
    if entity not in entities:
        return f"{entity or 'no entity'} is no project, area or idea of this vault"
    if Path(name).name != name or "/" in name or "\\" in name or name.startswith(".") or \
            Path(name).suffix.lower() != Path(item).suffix.lower():
        return f"{name or 'no name'} is not a bare file name with the item's extension"
    if (root / target).exists():
        return f"{target} exists"
    return None


def commit(root, paths, message):
    """Stage and commit `paths` alone, one deleted that git never tracked left out: the short
    hash, or None where git refused."""
    literal = ["--literal-pathspecs"]
    paths = [p for p in dict.fromkeys(paths)
             if (root / p).exists() or git(root, [*literal, "ls-files", "--", p])]
    if git(root, [*literal, "add", "-A", "--", *paths]) is None or \
            git(root, [*literal, "commit", "-q", "-m", message, "--", *paths]) is None:
        return None
    return (git(root, ["rev-parse", "--short", "HEAD"]) or "").strip() or None


def moved_paths(plan, *ends):
    return [*ends, *(r["file"] for r in plan["inside"] + plan["inbound"])]


def write_proposal(state, run, vault_root, rows):
    lines = ["# Unattended triage: waiting for the operator", "",
             "| Item | Recommended | Why | Held because |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['item']} | {r.get('action') or ''} | {r.get('reason') or ''} | "
                     f"{r['refused']} |")
    manifest = {"vault": state.vault, "root": str(vault_root), "run": run,
                "items": [{"item": r["item"], **r["file"]} for r in rows if r.get("file")]}
    lines += ["", "```json", json.dumps(manifest, ensure_ascii=False, indent=1), "```", ""]
    path = state.proposals / f"{state.vault}-{run[:13]}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def proposal_manifest(path):
    text = Path(path).read_text(encoding="utf-8")
    block = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
    return json.loads(block.group(1)) if block else {"items": []}


def run(args):
    scan = load_json(args.scan)
    decisions_file = Path(args.decisions)
    if decisions_file.is_file() and \
            decisions_file.stat().st_mtime < Path(args.scan).stat().st_mtime:
        decisions_file.unlink()
        raise Refused(f"{decisions_file} is older than the scan: its decisions were not "
                      "written this run. Removed it, so the next run's write lands")
    decisions = load_json(decisions_file)
    vault_root = Path(scan["vault"]["path"])
    state = State(args.paraos_home, scan["vault"]["name"])
    if (state.home / "auto-triage.off").exists():
        raise Refused("the kill switch auto-triage.off exists: nothing runs unattended")
    claude_md = vault_root / "CLAUDE.md"
    if claude_md.is_file() and ROSTER_RE.search(claude_md.read_text(encoding="utf-8")):
        raise Refused("this vault has a `## Who writes this vault` roster: never unattended")
    on = set(state.switched_on())
    loose = {e["name"]: e for e in scan["items"]["loose"]}
    snap = {same_place(p): d for p, d in (scan.get("snapshot") or {}).items()}
    git_vault = FILE_IT in on and in_git(vault_root)
    entities = {c["path"] for c in entity_candidates(vault_root, ENTITY_BUCKETS)}
    run_id = now_stamp()
    folder = state.quarantine / run_id
    acted, held, today = [], [], datetime.now().astimezone().date().isoformat()
    committed = []
    for d in decisions:
        name, action = d.get("item", ""), d.get("action", "")
        path = vault_root / "triage" / name
        why = None
        if Path(name).name != name or name not in loose:
            why = "not a loose file of the scan's triage/"
        elif not path.is_file():
            why = "no longer in triage/"
        elif d.get("hold"):
            why = d["hold"]
        elif not unattended(action):
            why = f"{action or 'no action'} is never unattended"
        elif action not in on:
            why = f"{action} is not switched on for this vault"
        elif action == FILE_IT and not git_vault:
            why = "File it runs only in a vault whose root is a git working tree"
        elif action == FILE_IT:
            why = filing_refusal(vault_root, d, name, entities)
        elif loose[name].get("inbound"):
            why = "other files link to it"
        elif action == "Delete (duplicate)" and not (loose[name].get("duplicates") or any(
                c.get("path") for c in loose[name].get("cross_vault") or ())):
            why = "the scan finds no byte match for it"
        if not why and list(snapshot([path]).values()) != [snap.get(same_place(path))]:
            why = "changed since the scan"
        elif not why and len(acted) >= args.cap:
            why = f"over the run's cap of {args.cap}"
        row = dict(d, file=item_record(path) if path.is_file() else None,
                   **sender(d, loose.get(name)))
        if not why and action == FILE_IT:
            filed = filing_target(d)[1]
            plan = move(vault_root, f"triage/{name}", filed)
            committed += moved_paths(plan, f"triage/{name}", filed)
            acted.append(dict(row, original=f"triage/{name}", filed=filed))
            continue
        if why:
            held.append(dict(row, refused=why))
            continue
        target = folder / "files" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
        acted.append(dict(row, original=f"triage/{name}"))
    report = {"vault": state.vault, "run": run_id, "kill_switch": False,
              "acted": [{"item": a["item"], "action": a["action"]} for a in acted],
              "refused": [{"item": h["item"], "reason": h["refused"]} for h in held],
              "quarantine": None, "proposal": None}
    if committed:
        filed = sum(1 for a in acted if a.get("filed"))
        report["commit"] = commit(vault_root, committed,
                                  f"Unattended triage {run_id}: file {filed} item(s)")
    if acted:
        write_json(folder / "manifest.json", {"vault": state.vault, "root": str(vault_root),
                                              "run": run_id, "items": acted})
        state.append({"date": today, "item": a["item"], "recommended": a["action"],
                      "chosen": a["action"], "path": "unattended",
                      **{k: a[k] for k in SENDER if k in a}} for a in acted)
        report["quarantine"] = str(folder)
    if held:
        report["proposal"] = str(write_proposal(state, run_id, vault_root, held))
    decisions_file.unlink()
    return report


def restore(args):
    state = State(args.paraos_home, args.vault_name)
    folder = state.quarantine / args.run
    manifest = load_json(folder / "manifest.json")
    root = Path(manifest["root"])
    picked = [i for i in manifest["items"]
              if (not args.item or i["item"] == args.item) and not i.get("restored")]
    if not picked:
        raise Refused(f"no such item in run {args.run}")
    out, bad, committed = [], [], []
    for item in picked:
        src, dst = folder / "files" / item["item"], root / item["original"]
        if dst.exists():
            bad.append({"item": item["item"], "reason": "a file is already at its path"})
            continue
        if item.get("filed"):
            try:
                plan = move(root, item["filed"], item["original"])
            except ValueError as err:
                bad.append({"item": item["item"], "reason": str(err)})
                continue
            committed += moved_paths(plan, item["filed"], item["original"])
        else:
            shutil.move(str(src), str(dst))
        item["restored"] = True
        if md5(dst) != item["file"]["md5"]:
            bad.append({"item": item["item"], "reason": "md5 differs from the manifest"})
        state.switch(item["action"], False, {"action": item["action"], "run": args.run,
                                             "item": item["item"],
                                             "date": datetime.now().date().isoformat()})
        state.append([{"date": datetime.now().date().isoformat(), "item": item["item"],
                       "recommended": item["action"], "chosen": "restored",
                       "path": "unattended", "restored": True}])
        out.append({"item": item["item"], "to": item["original"], "demoted": item["action"]})
    write_json(folder / "manifest.json", manifest)
    result = {"restored": out, "failed": bad}
    if committed:
        result["commit"] = commit(root, committed, f"Restore unattended triage {args.run}")
    return result


def status(args):
    state = State(args.paraos_home, args.vault_name)
    lines = state.decisions()
    last_interactive = max((ln["date"] for ln in lines if ln.get("path") == "interactive"),
                           default="")
    on, by_type = state.switched_on(), {}
    for ln in lines:
        if ln.get("path") == "interactive" and ln.get("recommended"):
            by_type.setdefault(ln["recommended"], []).append(ln["chosen"] == ln["recommended"])
    offers = [t for t, hits in sorted(by_type.items()) if t not in on and QUARANTINE_RE.match(t)
              and len(hits) >= OFFER_WINDOW and
              sum(hits[-OFFER_WINDOW:]) >= OFFER_SHARE * OFFER_WINDOW]
    runs = []
    for r in state.runs():
        m = load_json(state.quarantine / r / "manifest.json")
        if r[:8] >= last_interactive.replace("-", ""):
            counts = {}
            for i in m["items"]:
                counts[i["action"]] = counts.get(i["action"], 0) + 1
            runs.append({"run": r, "acted": counts, "restore":
                         f"auto_execute.py restore --vault-name {state.vault} --run {r}"})
    proposal = None
    found = sorted(state.proposals.glob(f"{state.vault}-{'[0-9]' * 8}-{'[0-9]' * 4}.md"))
    if found:
        m = proposal_manifest(found[-1])
        items = []
        for i in m["items"]:
            p = Path(m["root"]) / "triage" / i["item"]
            items.append({"item": i["item"], "state": "missing" if not p.is_file()
                          else "unchanged" if md5(p) == i["md5"] else "changed"})
        proposal = {"path": str(found[-1]), "items": items}
    nothing_new = None
    if args.vault:
        waiting = {i["item"] for i in (proposal or {}).get("items", [])
                   if i["state"] == "unchanged"}
        loose = {p.name for p in (Path(args.vault) / "triage").glob("*")
                 if p.is_file() and p.name != ".gitkeep"}
        nothing_new = loose <= waiting
    since = max((n for n, ln in enumerate(lines) if ln.get("path") == "interactive"),
                default=-1)
    return {"vault": state.vault, "on": on,
            "kill_switch": (state.home / "auto-triage.off").exists(), "offers": offers,
            "exclusion_offers": exclusion_offers(state.home, lines, lines[since + 1:]),
            "runs": runs, "proposal": proposal, "nothing_new": nothing_new}


def record(args):
    state = State(args.paraos_home, args.vault_name)
    today = datetime.now().date().isoformat()
    rows = load_json(args.decisions)
    loose = {e["name"]: e for e in load_json(args.scan)["items"]["loose"]} if args.scan else {}
    added = [{"date": today, "item": r["item"], "recommended": r["recommended"],
              "chosen": r["chosen"], "path": "interactive", **sender(r, loose.get(r["item"]))}
             for r in rows]
    state.append(added)
    moved = None
    if args.proposal:
        src = Path(args.proposal)
        moved = state.proposals / "decided" / src.name
        moved.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(moved))
    return {"recorded": len(rows), "proposal": str(moved) if moved else None,
            "exclusion_offers": exclusion_offers(state.home, state.decisions(), added)}


def add_exclusion(args):
    path = exclusions_file(paraos_home_dir(args.paraos_home))
    data = load_json(path, {})
    kind, value = ("from", args.sender) if args.sender else ("domain", args.domain)
    mailbox = args.mailbox.strip().lower()
    if not isinstance(data, dict) or not isinstance(data.setdefault(mailbox, []), list):
        raise Refused(f"{path} is not an object of entry lists keyed by mailbox")
    backup = None
    if path.is_file():
        backup = path.with_name(f"{path.name}.bak-{now_stamp()[:8]}")
        if backup.exists():
            backup = path.with_name(f"{path.name}.bak-{now_stamp()}")
        shutil.copy2(path, backup)
    entry = {kind: value.strip().lower(), "reason": args.reason,
             "added": datetime.now().date().isoformat()}
    data[mailbox].append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"mailbox": mailbox, "added": entry, "backup": str(backup) if backup else None}


def switch(args):
    state = State(args.paraos_home, args.vault_name)
    if not unattended(args.action):
        raise Refused(f"{args.action} is never unattended: only Delete, Dismiss and "
                      f"{FILE_IT} actions are")
    return {"vault": state.vault, **state.switch(args.action, args.on)}


def purge(args):
    root = paraos_home_dir(args.paraos_home) / "quarantine"
    cutoff = time.time() - args.days * 86400
    trashed, kept = [], []
    for manifest in sorted(root.glob("*/*/manifest.json")) if root.is_dir() else []:
        folder = manifest.parent
        if manifest.stat().st_mtime >= cutoff:
            continue
        (trashed if trash(folder) else kept).append(str(folder))
    return {"trashed": trashed, "no_trash": kept}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Unattended triage's executor and ledger.")
    sub = ap.add_subparsers(dest="command", required=True)
    commands = {"run": run, "restore": restore, "status": status, "record": record,
                "switch": switch, "add-exclusion": add_exclusion, "purge": purge}
    parsers = {name: sub.add_parser(name) for name in commands}
    for name, p in parsers.items():
        p.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
        if name not in ("run", "add-exclusion", "purge"):
            p.add_argument("--vault-name", required=True)
    parsers["run"].add_argument("--scan", required=True)
    parsers["run"].add_argument("--decisions", required=True)
    parsers["run"].add_argument("--cap", type=int, default=25)
    parsers["restore"].add_argument("--run", required=True)
    parsers["restore"].add_argument("--item")
    parsers["status"].add_argument("--vault", help="the vault root, for `nothing_new`")
    parsers["record"].add_argument("--decisions", required=True)
    parsers["record"].add_argument("--scan")
    parsers["record"].add_argument("--proposal")
    parsers["add-exclusion"].add_argument("--mailbox", required=True)
    parsers["add-exclusion"].add_argument("--reason", required=True)
    matcher = parsers["add-exclusion"].add_mutually_exclusive_group(required=True)
    matcher.add_argument("--from", dest="sender")
    matcher.add_argument("--domain")
    way = parsers["switch"].add_mutually_exclusive_group(required=True)
    way.add_argument("--on", action="store_true")
    way.add_argument("--off", action="store_true")
    parsers["switch"].add_argument("action")
    parsers["purge"].add_argument("--days", type=int, default=30)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    try:
        out = commands[args.command](args)
    except Refused as why:
        out, code = {"refused": str(why)}, 3
    else:
        code = 4 if out.get("failed") else 0
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
