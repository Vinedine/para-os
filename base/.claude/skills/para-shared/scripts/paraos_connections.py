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
     "mailboxes": [{"address": "me@example.com", "owner": "Me", "label": "Work"}],
     "ignore": ["resources/scripts/probe.ps1"]}

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
- `ignore` (optional): scripts whose code reaches outside and that are not a connection, a
  sign-in helper or a probe, each a path, the end of one, or a file name.

What a file already declares is discovered, never listed again: each registered vault's
`## Triage sources` rows (a connector, a recording source, a script, a mailbox), its
`## Agenda sources` rows, the servers its `.mcp.json` names (the name and a `url` only, never a
command line, an argument or an environment value), and each `tasks.json` entry's `via`
(para-shared/scripts/paraos_runs.py). A connector name is matched as `/para-triage` folds it,
a claude.ai calendar connector to one name, a remark in parentheses after it dropped, so two
spellings of one connector are one; a script written as a bare file name matches the entry
whose path ends on it.

What a script's own code shows is discovered too, so a script nobody listed is still seen.
The scripts read are those of each registered vault whose folder is on disk, one pulled on
another machine included: every script in a folder
named `scripts` or below one (tests, `archive/`, `triage/`, an environment's or a package
manager's folders and every folder whose name starts with a dot left out), and for each of the
vault's own skills (a folder in `.claude/skills/` whose name does not start `para-`) the
scripts the skill holds and the ones its text names: an absolute path, a path from the vault's
root, or a path from the folder of the last `cd <absolute folder>` written on its line or
above it in the same file, which is how a skill runs a script that lives in a code repo. A
script reaches outside when its code, with a docstring, a block comment and every comment line
dropped, runs a CLI the registry lists (its name where a command starts, as in `az account
show` or `"az", [...]`, never inside a sentence) or makes a network call (`fetch(`, `urllib`,
`requests.`, `Invoke-RestMethod`, `curl` and the like) and names an `http(s)://` host. A host
that names a format or an example (`www.w3.org`, `schemas.*`, `example.com`) is not one. This
is a reading of text, not a run: a call through a library that hides its host is not seen, and
a script wrongly read as reaching outside goes in `ignore`. A script marked `para-os-retired`
in its first ten lines is kept as reference and reaches nothing. A listed CLI in the code of a
skill's text (a fenced block or an inline span) is a use of that CLI.

`list` prints `{registry, exists, error, connections, mailboxes}`. Each connection carries its
registry fields (null where only discovered), `declared` (whether the registry lists it) and
`used_by`, one `{vault, via}` per use: `via` is `triage`, `agenda`, `mcp.json`, `task:<id>`,
`scripts` (found in a scripts folder), `skill:<name>` (held, named or run by that skill) or
`registry` (a vault the entry lists that nothing else shows using it). A discovered `.mcp.json`
server adds its `url` where it has one. A discovered script has `path` (from its vault's root,
or whole when it lives outside the vault), an `id` made from it, and `calls`, `{hosts, clis}`:
the hosts its code names and the listed CLIs it runs; a declared script has `calls` too where
its code shows any. Each mailbox carries `vaults`, every vault whose triage sources read it.

`check` prints `{registry, exists, findings}`; each finding is `{connection, kind, detail,
fix}`, kind one of:
- `invalid`: the file does not parse, or an entry breaks the shape above, or repeats an id.
- `unknown_vault`: an entry names a vault the registry of vaults does not.
- `missing_script`: a script's `path` is not there, in a listed vault on this machine (one with
  no `machine` in `vaults.json` and a folder on disk) or as an absolute path.
- `retired_script`: a listed script whose first ten lines carry `para-os-retired: YYYY-MM-DD`,
  the mark on a script kept as reference and no longer run.
- `undeclared`: a connector, a script or a task's `via` that neither the registry nor a
  vault's `.mcp.json` names, a script whose code reaches outside among them.
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
    _normalize_connector, _triage_kind, paraos_home_dir, read_json, read_text, register_rows,
    registry, triage_sources, utf8_stdout,
)
from paraos_runs import load_tasks  # noqa: E402

KINDS = ("mcp", "connector", "script", "cli", "browser")
START = "<!-- paraos-connections:start -->"
END = "<!-- paraos-connections:end -->"
MANIFEST_COLUMNS = ("Connection", "Kind", "Reaches", "Vaults", "Secret", "Writes", "Read-only")
SCRIPT_TYPES = (".py", ".js", ".mjs", ".cjs", ".ts", ".ps1", ".sh")
SKIPPED = frozenset(("node_modules", "venv", "site-packages", "archive", "triage", "tests",
                     "test", "__pycache__"))
BIGGEST = 400_000
CALLS = re.compile(
    r"\bfetch\s*\(|\burllib\b|\brequests\.|\bhttpx\b|\baiohttp\b|\bhttp\.client\b|"
    r"\bhttps?\.(?:request|get)\s*\(|\baxios\b|Invoke-RestMethod|Invoke-WebRequest|\bcurl\b|"
    r"\bwget\b|WebClient|HttpClient|XMLHttpRequest|\bplaywright\b|\bpuppeteer\b|\bselenium\b",
    re.I)
HOST = re.compile(r"https?://([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
FORMAT_HOSTS = ("www.w3.org", "json-schema.org", "purl.org", "xmlns.com")
BLOCKS = {".py": r'[rRbBuUfF]{0,2}("""|\'\'\').*?\1', ".ps1": r"<#.*?#>", ".sh": None}
NAMED = re.compile(r"[\w~.:/\\-]+\.(?:py|js|mjs|cjs|ts|ps1|sh)\b")
RUN_IN = re.compile(r"""\bcd\s+(?:"([^"]+)"|'([^']+)'|([^\s;&|"']+))""")
FENCE = r"(?ms)^[ \t]*```[^\n]*\n(.*?)^[ \t]*```"
RETIRED = re.compile(r"para-os-retired:\s*(\d{4}-\d{2}-\d{2})")


# --- the registry ---------------------------------------------------------------------------

def registry_file(home):
    return Path(home) / "connections.json"


def load(home):
    """`(data, error)`: the registry as `{"connections": [...], "mailboxes": [...], "ignore":
    [...]}`, empty where the file is missing, and why it could not be read where it does not
    parse."""
    path = registry_file(home)
    empty = {"connections": [], "mailboxes": [], "ignore": []}
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
    ignore = data.get("ignore", [])
    return {"connections": conns if isinstance(conns, list) else [],
            "mailboxes": boxes if isinstance(boxes, list) else [],
            "ignore": [p for p in ignore if isinstance(p, str)] if isinstance(ignore, list) else []}, None


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

def _here(entry, elsewhere=False):
    """A registry entry's folder when it is on disk and, unless `elsewhere`, pulled on this
    machine, else None."""
    path = entry.get("path")
    if (entry.get("machine") and not elsewhere) or not path or not Path(path).is_dir():
        return None
    return Path(path)


def _vaults_here(home, elsewhere=False):
    """`(folder, name)` for every registered vault `_here` finds."""
    out = []
    for entry in registry(home):
        if not isinstance(entry, dict):
            continue
        root, name = _here(entry, elsewhere), entry.get("name")
        if root is not None and isinstance(name, str) and name:
            out.append((root, name))
    return out


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
    data = read_json(Path(vault) / ".mcp.json")
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return {}
    return {name: (cfg.get("url") if isinstance(cfg, dict) and isinstance(cfg.get("url"), str)
                   else None) for name, cfg in servers.items()}


def discover(home):
    """Every use the files declare: `(uses, mailboxes)`. A use is `{kind, name, vault, via}`,
    kind `connector`, `script`, `mcp`, `browser` or `cli`; a mailbox use `{address, vault}`."""
    uses, boxes = [], []
    for root, name in _vaults_here(home):
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


# --- what a script's own code shows -----------------------------------------------------------

def _is_test(name):
    return name.startswith("test_") or bool(re.search(r"[._](?:test|spec)\.[A-Za-z]+$", name))


def _walk(folder, types, under=None):
    """Files of the given types below a folder, with tests, the SKIPPED folders and every
    folder whose name starts with a dot left out; with `under`, only those in a folder of
    that name or below one."""
    out = []
    for where, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIPPED and not d.startswith("."))
        if under and under not in (p.lower() for p in Path(where).relative_to(folder).parts):
            continue
        out += [Path(where) / f for f in sorted(files)
                if Path(f).suffix.lower() in types and not _is_test(f)]
    return out


def own_skills(root):
    """A vault's own skills: each folder in `.claude/skills/` that para-os does not ship,
    which is every name not starting `para-`."""
    base = Path(root) / ".claude" / "skills"
    if not base.is_dir():
        return []
    return sorted(d for d in base.iterdir() if d.is_dir() and not d.name.lower().startswith("para-"))


def _read(path):
    """A file's text, empty where it cannot be read or is too large to be a script."""
    try:
        if Path(path).stat().st_size > BIGGEST:
            return ""
    except OSError:
        return ""
    return read_text(path)


def _code(text, suffix):
    """A script's text with what only a reader sees dropped: a block comment or a docstring
    that starts its line, then every line that is a comment."""
    block = BLOCKS.get(suffix, r"/\*.*?\*/")
    if block:
        text = re.sub(r"(?ms)^[ \t]*" + block, "", text)
    mark = "#" if suffix in (".py", ".ps1", ".sh") else "//"
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(mark))


def _format_host(host):
    """Whether a host names a format or an example, not a place a script calls."""
    return (host in FORMAT_HOSTS or host.startswith("schemas.")
            or re.search(r"(?:^|\.)example\.(?:com|org|net)$", host) is not None)


def _runs(code, clis):
    """The listed CLIs a piece of code runs: the name where a command starts (a line, a
    quote, or after one of `; & | ( = !`), then a subcommand or, as the first element of an
    argument list, a closing quote and a comma. The name inside a sentence is not a run."""
    return [c for c in clis if re.search(
        rf"(?m)(?:^|[;&|(=!\"'`])[ \t]*{re.escape(c)}(?:\.cmd|\.exe)?(?:\s+[a-z]|[\"']\s*,)", code)]


def reach(text, suffix, clis=()):
    """`(hosts, clis)`: the outside hosts a script's code names, read only where the code
    makes a network call, and the listed CLIs it runs."""
    code = _code(text, suffix)
    hosts = []
    if CALLS.search(code):
        for host in HOST.findall(code):
            host = host.lower()
            if host not in hosts and not _format_host(host):
                hosts.append(host)
    return hosts, _runs(code, clis)


def _is_file(path):
    try:
        return path.is_file()
    except (OSError, ValueError):
        return False


def _expand(text):
    """A path as written, its leading `~` resolved where it names a home that is known."""
    try:
        return Path(text).expanduser()
    except RuntimeError:
        return Path(text)


def named_scripts(text, root):
    """The script files a skill's text names and that are there: an absolute path, a path
    from the folder of the last `cd <absolute folder>` written on its line or above it, or a
    path from the vault's root."""
    out, bases = [], [Path(root)]
    for line in text.splitlines():
        for cd in ("".join(groups) for groups in RUN_IN.findall(line)):
            if _expand(cd).is_absolute():
                bases = [_expand(cd), Path(root)]
        for token in NAMED.findall(line):
            path = _expand(token)
            hit = next((c for c in ([path] if path.is_absolute() else [b / path for b in bases])
                        if _is_file(c)), None)
            if hit is not None and hit not in out:
                out.append(hit)
    return out


def _spans(text):
    """The code in a skill's text: its fenced blocks and its inline spans."""
    return "\n".join(re.findall(FENCE, text) + re.findall(r"`([^`\n]+)`", re.sub(FENCE, "", text)))


def _label(path, root):
    """A script as a use names it: from the vault's root when it is in the vault, else whole."""
    path, root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _ignored(label, ignore):
    name = _norm_path(label)
    return any(name == p or name.endswith("/" + p) for p in map(_norm_path, ignore) if p)


def scan(home, clis=(), ignore=()):
    """What the code shows, as uses: `{kind: "script", name, vault, via, calls}` for every
    script that reaches outside, `calls` being `{hosts, clis}`, and `{kind: "cli", name, vault,
    via}` for every listed CLI a vault's own skill runs in its text. `via` is `scripts` for a
    script in a scripts folder, `skill:<name>` for what a skill holds, names or runs."""
    uses = []
    machines = {e.get("name"): e.get("machine") or None for e in registry(home) if isinstance(e, dict)}
    for root, name in _vaults_here(home, elsewhere=True):
        read = {}
        found = [(p, "scripts") for p in _walk(root, SCRIPT_TYPES, "scripts")]
        for skill in own_skills(root):
            via = f"skill:{skill.name}"
            found += [(p, via) for p in _walk(skill, SCRIPT_TYPES)]
            for doc in _walk(skill, (".md",)):
                text = _read(doc)
                found += [(p, via) for p in named_scripts(text, root)]
                for cli in _runs(_spans(text), clis):
                    use = {"kind": "cli", "name": cli, "vault": name, "via": via}
                    if use not in uses:
                        uses.append(use)
        seen = set()
        for path, via in found:
            label = _label(path, root)
            if (label.lower(), via) in seen or _ignored(label, ignore):
                continue
            seen.add((label.lower(), via))
            if label not in read:
                text = _read(path)
                retired = RETIRED.search("\n".join(text.splitlines()[:10]))
                read[label] = ([], []) if retired else reach(text, path.suffix.lower(), clis)
            hosts, ran = read[label]
            if hosts or ran:
                uses.append({"kind": "script", "name": label, "vault": name, "via": via,
                             "machine": machines.get(name),
                             "calls": {"hosts": list(hosts), "clis": list(ran)}})
    return uses


def _script_id(path, taken):
    """A discovered script's id: its file name in a vault, its last two folders and its name
    outside one, and the whole path where a connection already carries that."""
    parts = str(path).replace("\\", "/").split("/")
    short = "/".join(parts[-3:]) if re.match(r"(?:[A-Za-z]:)?/", str(path).replace("\\", "/")) else parts[-1]
    return str(path) if short.lower() in taken else short


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


def _add_calls(rec, use):
    """What a scanned script's code calls, kept on its connection, each name once."""
    for field, names in (use.get("calls") or {}).items():
        mine = rec.setdefault("calls", {"hosts": [], "clis": []})[field]
        mine += [n for n in names if n not in mine]


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
    uses += scan(home, [e["id"] for e in entries if e["kind"] == "cli"], data["ignore"])
    out = [_record(e, True) for e in entries]
    unmatched = []
    for use in uses:
        hits = [i for i, e in enumerate(entries) if _matches(e, use)]
        hit = next((i for i in hits if (entries[i].get("machine") or None) == use.get("machine")),
                   hits[0] if hits else None)
        if hit is None:
            unmatched.append(use)
            continue
        ref = {"vault": use["vault"], "via": use["via"]}
        if ref not in out[hit]["used_by"]:
            out[hit]["used_by"].append(ref)
        _add_calls(out[hit], use)
    discovered = {}
    for use in unmatched:
        if use["kind"] == "mcp":
            tag = ("mcp", key(use["name"]))
        elif use["kind"] == "script" and "calls" in use:
            tag = ("script", _norm_path(use["name"]))
        else:
            continue
        rec = discovered.get(tag)
        if rec is None and tag[0] == "mcp":
            rec = _record({"id": use["name"], "kind": "mcp", "vaults": []}, False)
            rec["url"] = use.get("url")
        elif rec is None:
            ident = _script_id(use["name"], {str(r["id"]).lower() for r in out})
            rec = _record({"id": ident, "kind": "script", "vaults": [], "path": use["name"]}, False)
        if tag not in discovered:
            discovered[tag] = rec
            out.append(rec)
        if use["vault"] not in rec["vaults"]:
            rec["vaults"].append(use["vault"])
        rec["used_by"].append({"vault": use["vault"], "via": use["via"]})
        _add_calls(rec, use)
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
        same = [u for u in unmatched if _use_tag(u) == tag]
        users = sorted({f"{u['vault']} ({u['via']})" for u in same})
        calls = {}
        for u in same:
            _add_calls(calls, u)
        if calls:
            names = calls["calls"]["clis"] + calls["calls"]["hosts"]
            findings.append(finding(use["name"], "undeclared",
                                    f"The script {use['name']!r}, used by {', '.join(users)}, calls {', '.join(names)}, and the registry does not list it.",
                                    "Add its entry to connections.json, or list its path under ignore where it is not a connection."))
            continue
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


def _retired(entry, file):
    marked = RETIRED.search("\n".join(read_text(file).splitlines()[:10]))
    return [finding(entry["id"], "retired_script",
                    f"{file.name} was retired on {marked.group(1)}, and the registry still lists it.",
                    "Remove the entry; the script stays as reference.")] if marked else []


def _script_findings(entry, vault_entries):
    path = Path(entry["path"])
    if path.is_absolute():
        return _retired(entry, path) if path.exists() else [finding(
            entry["id"], "missing_script", f"Its path {entry['path']} is not there.",
            "Correct the path, or remove the entry if the script is gone.")]
    if entry["vaults"] == "*":
        return []
    out = []
    for vault in entry["vaults"]:
        reg = next((e for e in vault_entries if e.get("name") == vault), None)
        root = _here(reg) if reg else None
        if root is None:
            continue
        if (root / path).exists():
            out += _retired(entry, root / path)
        else:
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
        found = c["kind"] == "script" and not c["declared"]
        name = f"`{c['id']}`" + ("" if c["declared"] else
                                 " (found by its code)" if found else " (from .mcp.json)")
        reaches = ", ".join(c["calls"]["clis"] + c["calls"]["hosts"]) if found else c["provider"]
        rows.append("| " + " | ".join(_cell(x) for x in (
            name, c["kind"], reaches, vaults, c["secret"] and f"`{c['secret']}`",
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
    utf8_stdout()
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
