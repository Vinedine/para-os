#!/usr/bin/env python3
"""Connections: everything in place to reach an outside source, listed once per machine.

    py -3 paraos_connections.py list [--paraos-home <path>]
    py -3 paraos_connections.py check [--paraos-home <path>]
    py -3 paraos_connections.py manifest [--write] [--paraos-home <path>]

`$PARAOS_HOME/connections.json` (default `~/.paraos/`) is one object:

    {"connections": [{"id": "granola", "kind": "script", "provider": "Granola",
                      "vaults": ["work"], "machine": null, "secret": "granola.json",
                      "writes": "meeting notes into triage/", "read_only": true,
                      "path": "resources/scripts/granola.js"}],
     "mailboxes": [{"address": "me@example.com", "owner": "Me", "label": "Work"}]}

- `id`: the connection's name. For an MCP server or a hosted connector, the name a vault's
  `## Triage sources` or `## Agenda sources` Type cell writes after `connector:` and a task
  writes after `mcp:`; for a CLI, the tool; for the built-in browser, `browser`.
- `kind`: `mcp` (a server this machine runs), `connector` (one the host runs, such as a
  claude.ai connector), `script`, `cli` or `browser`.
- `provider`: the outside source it reaches. `vaults`: registry names, or `"*"`. `machine`:
  null for this machine, else the name of the machine that runs it, as in `vaults.json`.
- `secret`: the name of its file in `$PARAOS_HOME/secrets/`, never a value; null for none.
  This script never opens that folder.
- `writes`: what it writes and where, null for nothing. `read_only`: whether it never changes
  the outside source.
- `path` (a script only): from each listed vault's root, or absolute.
- `mailboxes`: every address a vault reads, with its `owner` and the `label` a page shows.

What a file already declares is discovered, never listed again: each registered vault's
`## Triage sources` rows (a connector, a recording source, a script, a mailbox), its
`## Agenda sources` rows, the servers its `.mcp.json` names (the name and a `url` only, never a
command line, an argument or an environment value), and each `tasks.json` entry's `via`
(para-shared/scripts/paraos_runs.py). A connector name is matched as `/para-triage` folds it,
a claude.ai calendar connector to one name, a remark in parentheses after it dropped, so two
spellings of one connector are one; a script written as a bare file name matches the entry
whose path ends on it.

`list` prints `{registry, exists, error, connections, mailboxes}`. Each connection carries its
registry fields (null where only discovered), `declared` (whether the registry lists it) and
`used_by`, one `{vault, via}` per use: `via` is `triage`, `agenda`, `mcp.json`, `task:<id>` or
`registry` (a vault the entry lists that nothing else shows using it). A discovered `.mcp.json`
server adds its `url` where it has one. Each mailbox carries `vaults`, every vault whose triage
sources read it.

`check` prints `{registry, exists, findings}`; each finding is `{connection, kind, detail,
fix}`, kind one of:
- `invalid`: the file does not parse, or an entry breaks the shape above, or repeats an id.
- `unknown_vault`: an entry names a vault the registry of vaults does not.
- `missing_script`: a script's `path` is not there, in a listed vault on this machine (one with
  no `machine` in `vaults.json` and a folder on disk) or as an absolute path.
- `undeclared`: a connector, a script or a task's `via` that neither the registry nor a
  vault's `.mcp.json` names.
- `unlabelled_mailbox`: an address a vault reads that `mailboxes` does not label.
With no registry file, everything a vault or task uses is `undeclared`.

`manifest` renders one table of every connection, `| Connection | Kind | Reaches | Vaults |
Secret | Writes | Read-only |`, between `<!-- paraos-connections:start -->` and
`<!-- paraos-connections:end -->` in `$PARAOS_HOME/README.md`, and prints `{file, changed,
written, block}`. `--write` replaces what the markers hold, or with no markers appends a
`## Connections` section holding them; the rest of the file is never touched.

Exit codes: 0 answered; 2 a bad argument.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paraos_vault import (  # noqa: E402
    _normalize_connector, _triage_kind, paraos_home_dir, read_text, register_rows, registry,
    triage_sources,
)
from paraos_runs import load_tasks  # noqa: E402

KINDS = ("mcp", "connector", "script", "cli", "browser")
START = "<!-- paraos-connections:start -->"
END = "<!-- paraos-connections:end -->"
MANIFEST_COLUMNS = ("Connection", "Kind", "Reaches", "Vaults", "Secret", "Writes", "Read-only")


# --- the registry ---------------------------------------------------------------------------

def registry_file(home):
    return Path(home) / "connections.json"


def load(home):
    """`(data, error)`: the registry as `{"connections": [...], "mailboxes": [...]}`, empty
    where the file is missing, and why it could not be read where it does not parse."""
    path = registry_file(home)
    empty = {"connections": [], "mailboxes": []}
    if not path.is_file():
        return empty, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        return empty, f"{path.name} does not parse: {err}"
    if not isinstance(data, dict):
        return empty, f"{path.name} is not an object holding connections and mailboxes"
    conns = data.get("connections", [])
    boxes = data.get("mailboxes", [])
    return {"connections": conns if isinstance(conns, list) else [],
            "mailboxes": boxes if isinstance(boxes, list) else []}, None


def key(name):
    """The name a connection is matched by: a connector folded as /para-triage folds it, a
    claude.ai calendar connector folded to one name however a vault spells it, and a
    trailing remark in parentheses dropped."""
    text = str(name or "").strip()
    lowered = text.lower()
    if "calendar" in lowered and "claude" in lowered:
        return "claude_ai_google_calendar"
    return re.sub(r"\s*\(.*\)\s*$", "", _normalize_connector(text)).lower()


def entry_problems(entry):
    """Why one registry entry breaks the shape, as short phrases; empty when it fits."""
    if not isinstance(entry, dict):
        return ["is not an object"]
    out = []
    if not isinstance(entry.get("id"), str) or not entry["id"].strip():
        out.append("has no id")
    if entry.get("kind") not in KINDS:
        out.append(f"kind {entry.get('kind')!r} is not one of {', '.join(KINDS)}")
    if not isinstance(entry.get("provider"), str):
        out.append("has no provider")
    vaults = entry.get("vaults")
    if vaults != "*" and not (isinstance(vaults, list) and all(isinstance(v, str) for v in vaults)):
        out.append('vaults is neither a list of vault names nor "*"')
    for field in ("machine", "secret", "writes"):
        if entry.get(field) is not None and not isinstance(entry.get(field), str):
            out.append(f"{field} is neither text nor null")
    secret = entry.get("secret")
    if isinstance(secret, str) and ("/" in secret or "\\" in secret):
        out.append("secret is a path, not a file name")
    if not isinstance(entry.get("read_only"), bool):
        out.append("read_only is not true or false")
    if entry.get("kind") == "script" and not isinstance(entry.get("path"), str):
        out.append("is a script with no path")
    return out


def mailbox_problems(box):
    if not isinstance(box, dict) or "@" not in str(box.get("address", "")):
        return ["has no address"]
    return [f"has no {f}" for f in ("owner", "label") if not isinstance(box.get(f), str)]


# --- what the files already declare -------------------------------------------------------------

def _here(entry):
    """A registry entry's folder when it is on this machine and on disk, else None."""
    path = entry.get("path")
    if entry.get("machine") or not path or not Path(path).is_dir():
        return None
    return Path(path)


def _norm_path(path):
    return str(path or "").strip().replace("\\", "/").lower()


def agenda_rows(vault):
    """Connector names a vault's `## Agenda sources` rows read."""
    out = []
    for r in register_rows(Path(vault) / "CLAUDE.md"):
        if (r.get("section") or "").strip().lower() != "agenda sources":
            continue
        cells = {k.strip().lower(): v for k, v in r.items() if isinstance(k, str)}
        kind, name = _triage_kind(cells.get("type", "").replace("`", "").strip())
        if kind in ("connector", "recording") and name:
            out.append(name)
    return out


def mcp_servers(vault):
    """`{name: url or None}` for the servers a vault's `.mcp.json` names. Nothing else of a
    server is read: a command line or an environment value can carry a token."""
    try:
        data = json.loads((Path(vault) / ".mcp.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return {}
    return {name: (cfg.get("url") if isinstance(cfg, dict) and isinstance(cfg.get("url"), str)
                   else None) for name, cfg in servers.items()}


def discover(home):
    """Every use the files declare: `(uses, mailboxes)`. A use is `{kind, name, vault, via}`,
    kind `connector`, `script`, `mcp`, `browser` or `cli`; a mailbox use `{address, vault}`."""
    uses, boxes = [], []
    for entry in registry(home):
        if not isinstance(entry, dict):
            continue
        root, name = _here(entry), entry.get("name")
        if root is None or not isinstance(name, str) or not name:
            continue
        for row in triage_sources(root)["rows"]:
            if row["kind"] in ("connector", "recording") and row["connector"]:
                uses.append({"kind": "connector", "name": row["connector"], "vault": name,
                             "via": "triage"})
            elif row["kind"] in ("sync-script", "fetch-script") and row["path"]:
                uses.append({"kind": "script", "name": row["path"], "vault": name, "via": "triage"})
            if row["mailbox"]:
                boxes.append({"address": row["mailbox"].lower(), "vault": name})
        for connector in agenda_rows(root):
            uses.append({"kind": "connector", "name": connector, "vault": name, "via": "agenda"})
        for server, url in mcp_servers(root).items():
            uses.append({"kind": "mcp", "name": server, "vault": name, "via": "mcp.json",
                         "url": url})
    tasks, _ = load_tasks(home)
    for task in tasks if isinstance(tasks, list) else []:
        if not isinstance(task, dict):
            continue
        vaults = task.get("vaults") if isinstance(task.get("vaults"), list) else ["*"]
        for source in task.get("sources") or []:
            for via in (source.get("via") or []) if isinstance(source, dict) else []:
                kind, _, rest = str(via).partition(":")
                kind = "connector" if kind == "mcp" else kind
                if kind == "browser":
                    rest = "browser"
                if kind in ("connector", "script", "cli", "browser") and rest:
                    for vault in vaults:
                        uses.append({"kind": kind, "name": rest, "vault": vault,
                                     "via": f"task:{task.get('id')}"})
    return uses, boxes


def _matches(entry, use):
    if use["kind"] == "script":
        if entry.get("kind") != "script":
            return False
        mine, used = _norm_path(entry.get("path")), _norm_path(use["name"])
        return mine == used or ("/" not in used and mine.rsplit("/", 1)[-1] == used)
    if use["kind"] == "browser":
        return entry.get("kind") == "browser"
    if use["kind"] == "cli":
        return entry.get("kind") == "cli" and key(entry.get("id")) == key(use["name"])
    return entry.get("kind") in ("mcp", "connector") and key(entry.get("id")) == key(use["name"])


# --- list -----------------------------------------------------------------------------------

def _record(entry, declared):
    fields = ("id", "kind", "provider", "vaults", "machine", "secret", "writes", "read_only", "path")
    out = {f: entry.get(f) for f in fields}
    out.update(declared=declared, used_by=[])
    return out


def list_all(paraos_home=None):
    listed, _, _ = gather(paraos_home)
    return listed


def gather(paraos_home=None):
    """`(listed, unmatched, box_uses)`: what `list` prints, the uses no registry entry
    matched, and every mailbox use, the last two for `check`."""
    home = paraos_home_dir(paraos_home)
    data, error = load(home)
    uses, box_uses = discover(home)
    entries = [e for e in data["connections"] if not entry_problems(e)]
    out = [_record(e, True) for e in entries]
    unmatched = []
    for use in uses:
        hit = next((i for i, e in enumerate(entries) if _matches(e, use)), None)
        if hit is None:
            unmatched.append(use)
            continue
        ref = {"vault": use["vault"], "via": use["via"]}
        if ref not in out[hit]["used_by"]:
            out[hit]["used_by"].append(ref)
    discovered = {}
    for use in unmatched:
        if use["kind"] != "mcp":
            continue
        rec = discovered.get(key(use["name"]))
        if rec is None:
            rec = _record({"id": use["name"], "kind": "mcp", "vaults": []}, False)
            rec["url"] = use.get("url")
            discovered[key(use["name"])] = rec
            out.append(rec)
        rec["vaults"].append(use["vault"])
        rec["used_by"].append({"vault": use["vault"], "via": use["via"]})
    for rec in out:
        if rec["declared"] and isinstance(rec["vaults"], list):
            seen = {u["vault"] for u in rec["used_by"]}
            rec["used_by"] += [{"vault": v, "via": "registry"} for v in rec["vaults"] if v not in seen]
    boxes = []
    for box in data["mailboxes"]:
        if mailbox_problems(box):
            continue
        address = box["address"].lower()
        boxes.append({"address": box["address"], "owner": box["owner"], "label": box["label"],
                      "vaults": sorted({u["vault"] for u in box_uses if u["address"] == address})})
    listed = {"registry": str(registry_file(home)), "exists": registry_file(home).is_file(),
              "error": error, "connections": out, "mailboxes": boxes}
    return listed, unmatched, box_uses


# --- check ----------------------------------------------------------------------------------

def finding(connection, kind, detail, fix):
    return {"connection": connection, "kind": kind, "detail": detail, "fix": fix}


def check(paraos_home=None):
    home = paraos_home_dir(paraos_home)
    data, error = load(home)
    listed, unmatched, box_uses = gather(home)
    vault_entries = [e for e in registry(home) if isinstance(e, dict)]
    names = {e.get("name") for e in vault_entries}
    findings = []
    if error:
        findings.append(finding(None, "invalid", error, "Fix the file's JSON; nothing in it was read."))
    seen = set()
    for entry in data["connections"]:
        cid = entry.get("id") if isinstance(entry, dict) else None
        problems = entry_problems(entry)
        if cid and key(cid) in seen:
            problems.append("repeats an id listed above it")
        if problems:
            findings.append(finding(cid, "invalid", f"The entry {'; '.join(problems)}.",
                                    "Correct it to the shape in paraos_connections.py; until then it is not read."))
            continue
        seen.add(key(cid))
        if isinstance(entry["vaults"], list):
            for vault in entry["vaults"]:
                if vault not in names:
                    findings.append(finding(cid, "unknown_vault",
                                            f"It names the vault {vault!r}, which vaults.json does not list.",
                                            "Use the vault's registry name, or drop it from the entry."))
        if entry["kind"] == "script" and not entry.get("machine"):
            findings += _script_findings(entry, vault_entries)
    for box in data["mailboxes"]:
        problems = mailbox_problems(box)
        if problems:
            label = box.get("address") if isinstance(box, dict) else None
            findings.append(finding(label, "invalid", f"A mailbox {'; '.join(problems)}.",
                                    "Give each mailbox an address, an owner and a label."))
    reported = set()
    for use in unmatched:
        if use["kind"] == "mcp":
            continue
        tag = _use_tag(use)
        if tag in reported:
            continue
        reported.add(tag)
        users = sorted({f"{u['vault']} ({u['via']})" for u in unmatched if _use_tag(u) == tag})
        findings.append(finding(use["name"], "undeclared",
                                f"The {use['kind']} {use['name']!r} is used by {', '.join(users)}, and the registry does not list it.",
                                "Add its entry to connections.json: kind, provider, vaults, secret, what it writes, read_only."))
    labelled = {str(b.get("address", "")).lower() for b in data["mailboxes"] if isinstance(b, dict)}
    for address in sorted({u["address"] for u in box_uses} - labelled):
        users = sorted({u["vault"] for u in box_uses if u["address"] == address})
        findings.append(finding(address, "unlabelled_mailbox",
                                f"{', '.join(users)} read {address}, which mailboxes does not label.",
                                "Add it to mailboxes with its owner and the label a page shows."))
    return {"registry": listed["registry"], "exists": listed["exists"], "findings": findings}


def _use_tag(use):
    """One undeclared connection however many vaults use it: a script by its path, the rest
    by their folded name."""
    return use["kind"], _norm_path(use["name"]) if use["kind"] == "script" else key(use["name"])


def _script_findings(entry, vault_entries):
    path = Path(entry["path"])
    if path.is_absolute():
        return [] if path.exists() else [finding(
            entry["id"], "missing_script", f"Its path {entry['path']} is not there.",
            "Correct the path, or remove the entry if the script is gone.")]
    if entry["vaults"] == "*":
        return []
    out = []
    for vault in entry["vaults"]:
        reg = next((e for e in vault_entries if e.get("name") == vault), None)
        root = _here(reg) if reg else None
        if root is not None and not (root / path).exists():
            out.append(finding(entry["id"], "missing_script",
                               f"{vault} has no {entry['path']}.",
                               "Install the script there, correct the path, or drop the vault from the entry."))
    return out


# --- manifest -------------------------------------------------------------------------------

def _cell(text):
    return str(text if text is not None else "").replace("|", "\\|").strip()


def manifest_block(listed):
    rows = [START, "", "| " + " | ".join(MANIFEST_COLUMNS) + " |", "|" + "---|" * len(MANIFEST_COLUMNS)]
    for c in sorted(listed["connections"], key=lambda c: (KINDS.index(c["kind"]), c["id"].lower())):
        vaults = c["vaults"] if c["vaults"] == "*" else ", ".join(c["vaults"] or [])
        read_only = "" if c["read_only"] is None else ("yes" if c["read_only"] else "no")
        name = f"`{c['id']}`" + ("" if c["declared"] else " (from .mcp.json)")
        rows.append("| " + " | ".join(_cell(x) for x in (
            name, c["kind"], c["provider"], vaults, c["secret"] and f"`{c['secret']}`",
            c["writes"], read_only)) + " |")
    rows += ["", END]
    return "\n".join(rows)


def manifest(paraos_home=None, write_it=False):
    home = paraos_home_dir(paraos_home)
    path = Path(home) / "README.md"
    block = manifest_block(list_all(home))
    crlf = path.is_file() and b"\r\n" in path.read_bytes()
    text = read_text(path).replace("\r\n", "\n") if path.is_file() else ""
    if START in text and END in text and text.index(START) < text.index(END):
        before, rest = text.split(START, 1)
        after = rest.split(END, 1)[1]
        new = before + block + after
    else:
        new = text.rstrip("\n") + ("\n\n" if text.strip() else "") + "## Connections\n\n" + block + "\n"
    out = {"file": str(path), "changed": new != text, "written": False, "block": block}
    if write_it and out["changed"]:
        _write(path, new, crlf)
        out["written"] = True
    return out


def _write(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".readme.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description="Connections: the registry, its check and its manifest block.")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="every connection, declared or discovered, with its uses")
    sub.add_parser("check", help="what the registry gets wrong or misses")
    mf = sub.add_parser("manifest", help="the connections table in the machine manifest")
    mf.add_argument("--write", action="store_true", help="write the table into README.md")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    if args.cmd == "list":
        result = list_all(args.paraos_home)
    elif args.cmd == "check":
        result = check(args.paraos_home)
    else:
        result = manifest(args.paraos_home, args.write)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
