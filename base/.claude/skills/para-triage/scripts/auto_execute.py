#!/usr/bin/env python3
"""The only writer of an unattended /para-triage run, and the decision ledger both paths keep.

    py -3 auto_execute.py run --scan <saved scan> --decisions <file.json> [--cap 25]
    py -3 auto_execute.py restore --vault-name <name> --run <run> [--item <name>]
    py -3 auto_execute.py status --vault-name <name> [--vault <root>]
    py -3 auto_execute.py record --vault-name <name> --decisions <file.json> [--proposal <path>]
    py -3 auto_execute.py switch --vault-name <name> (--on | --off) <action>
    py -3 auto_execute.py purge [--days 30]

Every command takes `--paraos-home DIR`, and prints one JSON document. State lives under the
para-os home, never in a vault:

    auto-triage.json                    {vault name: {"on": [action], "demoted": [...]}}
    auto-triage.off                     the kill switch: while it exists, `run` acts on nothing
    cache/triage/decisions/<vault>.jsonl  one line per decided item, from either path
    cache/triage/proposals/<vault>-<YYYYMMDD-HHMM>.md  what a run left for the operator
    quarantine/<vault>/<run>/           the items a run took out, with manifest.json

`run` reads the triage scan's saved copy (`saved_to`) and a decisions file, a JSON list of
`{"item", "action", "reason", "survivor", "hold"}`, `item` a loose file's name in `triage/`.
An item is acted on only where its action is a `Delete (...)` or `Dismiss (...)` switched on
for this vault, it carries no `hold`, it is a loose file of the scan, the scan lists no
inbound link to it, its bytes still match the scan's snapshot, and the run is under `--cap`.
Acting moves it into the quarantine, never deletes it. Everything else goes into the run's
proposal, with each item's name, size, mtime and md5, and `refused` says why. The whole run
is refused while the kill switch exists, and for a vault whose `CLAUDE.md` has a
`## Who writes this vault` roster. Where the vault is a git repository, one commit names
each item it removed.

`restore` moves a run's items back, checks each md5, and switches the item's action off for
the vault (`demoted`). `status` reads the switched-on actions, the kill switch, the runs and
proposal waiting since the last interactive decision, each proposed item as `unchanged`,
`changed` or `missing`, `nothing_new` with `--vault` (every loose file is a proposed item,
unchanged, so a scheduled run can skip the vault), and `offers`: each action whose last 50
interactive decisions in the vault were at least 95% the recommendation unchanged, not yet
switched on. `record` appends
the interactive path's decisions, `{"item", "recommended", "chosen"}`, and moves a decided
proposal into `proposals/decided/`. `switch` is the operator's standing approval, or its
withdrawal. `purge` sends each quarantined run older than `--days` to the system trash, and
leaves one where no trash is reachable.

Exit codes: 0 answered; 2 the library is missing; 3 refused (kill switch, shared vault, an
unreadable scan or decisions file, a run or item not found); 4 a restored md5 differs.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import paraos_home_dir, same_place, snapshot  # noqa: E402
except ImportError as missing:
    print(f"auto_execute: {missing}. install para-shared beside this skill", file=sys.stderr)
    sys.exit(2)

QUARANTINE_RE = re.compile(r"^(Delete|Dismiss) \(")
ROSTER_RE = re.compile(r"^## Who writes this vault\s*$", re.MULTILINE)
OFFER_WINDOW, OFFER_SHARE = 50, 0.95


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


def item_record(path):
    st = path.stat()
    return {"size": st.st_size, "mtime": int(st.st_mtime), "md5": md5(path)}


def git_commit(vault, rels, message):
    """One commit for the items a run removed, where they were tracked; None where the vault
    is not a git repository or tracked none of them."""
    def git(*args):
        return subprocess.run(["git", "-C", str(vault), *args], capture_output=True, text=True)
    try:
        tracked = [r for r in rels if git("ls-files", "--error-unmatch", "--", r).returncode == 0]
    except OSError:
        return None
    if not tracked:
        return None
    done = git("commit", "-q", "-m", message, "--", *tracked)
    return "committed" if done.returncode == 0 else done.stderr.strip() or "commit failed"


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
    decisions = load_json(args.decisions)
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
    run_id = now_stamp()
    folder = state.quarantine / run_id
    acted, held, today = [], [], datetime.now().astimezone().date().isoformat()
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
        elif not QUARANTINE_RE.match(action):
            why = f"{action or 'no action'} is never unattended"
        elif action not in on:
            why = f"{action} is not switched on for this vault"
        elif loose[name].get("inbound"):
            why = "other files link to it"
        elif list(snapshot([path]).values()) != [snap.get(same_place(path))]:
            why = "changed since the scan"
        elif len(acted) >= args.cap:
            why = f"over the run's cap of {args.cap}"
        row = dict(d, file=item_record(path) if path.is_file() else None)
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
              "quarantine": None, "proposal": None, "commit": None}
    if acted:
        write_json(folder / "manifest.json", {"vault": state.vault, "root": str(vault_root),
                                              "run": run_id, "items": acted})
        state.append({"date": today, "item": a["item"], "recommended": a["action"],
                      "chosen": a["action"], "path": "unattended"} for a in acted)
        report["quarantine"] = str(folder)
        report["commit"] = git_commit(vault_root, [a["original"] for a in acted],
                                      "Unattended triage: " + "; ".join(
                                          f"{a['action']} {a['item']}" for a in acted))
    if held:
        report["proposal"] = str(write_proposal(state, run_id, vault_root, held))
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
    out, bad = [], []
    for item in picked:
        src, dst = folder / "files" / item["item"], root / item["original"]
        if dst.exists():
            bad.append({"item": item["item"], "reason": "a file is already at its path"})
            continue
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
    return {"restored": out, "failed": bad}


def status(args):
    state = State(args.paraos_home, args.vault_name)
    lines = state.decisions()
    last_interactive = max((ln["date"] for ln in lines if ln.get("path") == "interactive"),
                           default="")
    on, by_type = state.switched_on(), {}
    for ln in lines:
        if ln.get("path") == "interactive":
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
    return {"vault": state.vault, "on": on,
            "kill_switch": (state.home / "auto-triage.off").exists(), "offers": offers,
            "runs": runs, "proposal": proposal, "nothing_new": nothing_new}


def record(args):
    state = State(args.paraos_home, args.vault_name)
    today = datetime.now().date().isoformat()
    rows = load_json(args.decisions)
    state.append({"date": today, "item": r["item"], "recommended": r["recommended"],
                  "chosen": r["chosen"], "path": "interactive"} for r in rows)
    moved = None
    if args.proposal:
        src = Path(args.proposal)
        moved = state.proposals / "decided" / src.name
        moved.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(moved))
    return {"recorded": len(rows), "proposal": str(moved) if moved else None}


def switch(args):
    state = State(args.paraos_home, args.vault_name)
    if not QUARANTINE_RE.match(args.action):
        raise Refused(f"{args.action} is never unattended: only Delete and Dismiss actions are")
    return {"vault": state.vault, **state.switch(args.action, args.on)}


def trash(path):
    """The system trash, per operating-discipline.md; False where none is reachable."""
    if sys.platform == "win32":
        quoted = str(path).replace("'", "''")
        cmd = ["powershell", "-NoProfile", "-Command",
               "Add-Type -AssemblyName Microsoft.VisualBasic; "
               "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("
               f"'{quoted}', 'OnlyErrorDialogs', 'SendToRecycleBin')"]
    elif sys.platform == "darwin":
        quoted = str(path).replace("\\", "\\\\").replace('"', '\\"')
        cmd = ["osascript", "-e", f'tell application "Finder" to delete POSIX file "{quoted}"']
    else:
        cmd = ["gio", "trash", str(path)]
    try:
        return subprocess.run(cmd, capture_output=True).returncode == 0
    except OSError:
        return False


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
                "switch": switch, "purge": purge}
    parsers = {name: sub.add_parser(name) for name in commands}
    for name, p in parsers.items():
        p.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
        if name not in ("run", "purge"):
            p.add_argument("--vault-name", required=True)
    parsers["run"].add_argument("--scan", required=True)
    parsers["run"].add_argument("--decisions", required=True)
    parsers["run"].add_argument("--cap", type=int, default=25)
    parsers["restore"].add_argument("--run", required=True)
    parsers["restore"].add_argument("--item")
    parsers["status"].add_argument("--vault", help="the vault root, for `nothing_new`")
    parsers["record"].add_argument("--decisions", required=True)
    parsers["record"].add_argument("--proposal")
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
