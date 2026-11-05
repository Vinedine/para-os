#!/usr/bin/env python3
"""The code repos a vault steers: one table shape, a reader for it, and a converter into it.

    py -3 paraos_repos.py list --vault <path> [--paraos-home <path>]
    py -3 paraos_repos.py convert --vault <path> [--write]

A vault that steers code keeps `.claude/rules/code-repos.md` (bootstrap-prompt.md, `## Code
repos`), and its repos are one table:

    | Repo | Role | What it is | Vault home | Site | Serves vault |

- `Repo`: the repo's folder name, in backticks.
- `Role`: `owned` (this vault steers its work), `reference` (kept to consult, no work steered)
  or `other` (queried now and then, its work at home elsewhere).
- `What it is`: free text.
- `Vault home`: a link to the project, area or idea that holds its work, empty where none does.
- `Site` (a bare domain) and `Serves vault` (a registry name): only for a repo that builds a
  website, and then both. `Serves vault` names the vault the site is for, which may not be the
  vault that steers the repo.

`list` prints `{file, shape, repos, problems}`. `shape` is `table` (every repo is a row of that
table), `legacy` (an older shape: bullets, another table, a role read from the line above) or
`absent` (no file). Each repo has `repo`, `role`, `what`, `home` (the cell as written),
`home_path` (the folder it links to, from the vault root, null when none), `site`, `serves` and
`line`. A legacy file's repos are read as `convert` reads them. `problems`, each `{line, repo,
problem}`: a role that is not one of the three, a site with no serving vault or the reverse, a
serving vault the registry does not name (checked only when a registry is found), and a repo
listed twice.

`convert` writes a legacy file's repos as the table and prints `{file, changed, written, text,
repos, to_fill, dropped}`. `text` is the whole new file; `--write` writes it in the file's own
line endings, and only when `changed`.
- A repo is a table row with a `Repo` column, or a list item that opens on a name in backticks,
  in bold or as a link label, or a bare name followed by ` - `. Its text after the name and its
  separator becomes `What it is` word for word, an indented continuation joined to it. Extra
  columns of an older table join `What it is` after a `; `, in column order.
- A role line is a line outside a list and a table that is a heading, opens in bold, or ends in
  `:`. Its lead (the heading, the bold words, else the words before a `,`, `(` or `:`) sets the
  role of every repo after it: `reference...` reference, `other...` other, `active`, `owned` or
  `current` owned. Before any role line, a repo is owned. A role line that set a role is dropped
  and listed in `dropped` with its line; every other line stays where it was, and the table
  takes the place of the first repo or role line.
- `Vault home` is kept from an older table's home column. Otherwise it is the first folder the
  repo's text links to or names in backticks, preferring `projects/` and `areas/` to
  `resources/ideas/`, and that to `archive/projects/` or `archive/ideas/`; a file's folder for a
  file, and only a folder that exists in the vault.
- `to_fill` lists, per repo, what the conversion could not know: `home` when it found none, and
  `site_hint`, the bare domains its text names (outside a URL), for the operator to confirm as
  its `Site` and to name the vault it serves.

Exit codes: 0 answered; 2 a bad argument (the vault is not a folder).
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
    first_link, is_separator_row, read_text, registry, split_lines, table_cells, utf8_stdout,
)

RULE_FILE = Path(".claude") / "rules" / "code-repos.md"
COLUMNS = ("Repo", "Role", "What it is", "Vault home", "Site", "Serves vault")
ROLES = ("owned", "reference", "other")

# Older tables: a header cell, lowercased with its marks dropped, and the field it fills.
HEADER_FIELDS = {
    "repo": "repo", "repository": "repo", "role": "role",
    "what it is": "what", "what": "what", "description": "what", "purpose": "what",
    "vault home": "home", "home": "home", "where": "home",
    "site": "site", "website": "site", "serves vault": "serves", "serves": "serves",
}
ROLE_LEADS = (("reference", "reference"), ("other", "other"), ("active", "owned"),
              ("owned", "owned"), ("current", "owned"))
DASH = "[-\u2013\u2014]"  # a hyphen, an en or an em dash between a name and its text
SEPARATOR = r"(?:\s+" + DASH + r"\s+|\s*:\s+|\s*$)"
ITEM_RES = (
    re.compile(r"^\s*[-*]\s+`([^`]+)`" + SEPARATOR + r"(.*)$"),
    re.compile(r"^\s*[-*]\s+\*\*([^*]+)\*\*" + SEPARATOR + r"(.*)$"),
    re.compile(r"^\s*[-*]\s+\[([^\]]+)\]\([^)]*\)" + SEPARATOR + r"(.*)$"),
    re.compile(r"^\s*[-*]\s+([A-Za-z0-9][\w.-]*)\s+" + DASH + r"\s+(.*)$"),
)
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
BOLD_LEAD_RE = re.compile(r"^\*\*([^*]+)\*\*")
TICKED_RE = re.compile(r"`([^`]+)`")
LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
HOME_RANK = ((re.compile(r"^(?:projects|areas)/"), 0), (re.compile(r"^resources/ideas/[^/]+/"), 1),
             (re.compile(r"^archive/(?:projects|ideas)/[^/]+/"), 2))
DOMAIN_RE = re.compile(r"(?<![\w./:@-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+([a-z]{2,24}))(?![\w/@-])")
SITE_TLDS = {"com", "net", "org", "io", "dev", "app", "tech", "ai", "co", "eu", "be", "nl", "fr",
             "de", "uk", "ch", "lu", "es", "it", "at", "site", "studio", "shop", "store",
             "online", "info", "biz", "us", "ca", "au", "pt", "ie", "dk", "se", "no", "fi"}


# --- reading --------------------------------------------------------------------------------

def rule_file(vault):
    return Path(vault) / RULE_FILE


def _plain(cell):
    """A header cell or a role lead, lowercased, its marks and stray punctuation dropped."""
    return re.sub(r"\s+", " ", re.sub(r"[`*_]", "", cell)).strip().strip(":").strip().lower()


def _repo_name(cell):
    """The repo's name from a Repo cell: inside backticks, a link label, or the cell itself."""
    cell = cell.strip()
    m = re.match(r"^\[([^\]]+)\]\(", cell)
    if m:
        cell = m.group(1)
    return re.sub(r"[`*]", "", cell).strip()


def role_of(line):
    """The role a role line sets, or None where the line is not one or sets nothing."""
    s = line.strip()
    if not s or LIST_RE.match(s) or s.startswith("|"):
        return None
    heading = HEADING_RE.match(s)
    bold = BOLD_LEAD_RE.match(s)
    if heading:
        lead = heading.group(1)
    elif bold:
        lead = bold.group(1)
    elif s.endswith(":"):
        lead = re.split(r"[,(:]", s, maxsplit=1)[0]
    else:
        return None
    lead = re.sub(r"[^a-z ]", " ", _plain(lead)).strip()
    for prefix, role in ROLE_LEADS:
        if lead.startswith(prefix):
            return role
    return None


def _frontmatter_end(lines):
    """The index of the first line after a leading `---` frontmatter block, 0 where none."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return i + 1
    return 0


def _vault_path(target):
    """A link target or a backticked path as a path from the vault root, or None."""
    t = target.strip().split("#", 1)[0].strip().replace("\\", "/")
    while t.startswith("../") or t.startswith("./"):
        t = t[3:] if t.startswith("../") else t[2:]
    if not t or any(ch in t for ch in "{}*<> ") or "://" in t:
        return None
    return t


def _folder(path):
    """The entity folder a vault path points into: a file's folder, without a `sources/` tail."""
    parts = [p for p in path.split("/") if p]
    if parts and "." in parts[-1]:
        parts = parts[:-1]
    if "sources" in parts:
        parts = parts[:parts.index("sources")]
    return "/".join(parts) + "/" if parts else None


def home_candidates(text):
    """Every vault folder a repo's text links to or names in backticks, in text order."""
    found = []
    spans = [(m.start(), first_link(m.group(0))) for m in LINK_RE.finditer(text)]
    spans += [(m.start(), m.group(1)) for m in TICKED_RE.finditer(text)]
    for _, target in sorted(spans, key=lambda s: s[0]):
        path = _vault_path(target or "")
        folder = _folder(path) if path else None
        if folder and folder not in found:
            found.append(folder)
    return found


def pick_home(text, vault):
    """The folder `convert` writes as a repo's home: the best-ranked candidate that exists."""
    best = None
    for folder in home_candidates(text):
        rank = next((r for rx, r in HOME_RANK if rx.match(folder)), None)
        if rank is None or not (Path(vault) / folder).is_dir():
            continue
        if best is None or rank < best[0]:
            best = (rank, folder)
    return best[1] if best else None


def site_hints(text):
    """Bare domains a repo's text names outside a URL, lowercase as written."""
    out = []
    for m in DOMAIN_RE.finditer(text):
        domain, tld = m.group(1), m.group(2)
        if tld in SITE_TLDS and domain not in out:
            out.append(domain)
    return out


def _home_path(cell):
    """The folder a Vault home cell links to, from the vault root, or None."""
    target = first_link(cell)
    if not target:
        ticked = TICKED_RE.search(cell)
        target = ticked.group(1) if ticked else None
    path = _vault_path(target) if target else None
    return _folder(path) if path else None


def _repo(name, role, what, home, line, site="", serves=""):
    return {"repo": name, "role": role, "what": what, "home": home, "home_path": _home_path(home),
            "site": site, "serves": serves, "line": line}


def parse(text):
    """Every repo in a code-repos file, and how the file holds them.

    Returns `(repos, shape, layout)`: `layout` is one `(kind, payload)` per source line, kind
    `keep` (a line `convert` keeps), `repo` (a line that holds a repo or a table's header or
    separator), `role` (a role line that set a role) or `cont` (a list item's continuation).
    """
    lines = split_lines(text)
    start = _frontmatter_end(lines)
    layout = [("keep", ln) for ln in lines[:start]]
    repos, role, header, in_table, is_target, saw_legacy = [], "owned", None, False, False, False
    last_item = None
    for i in range(start, len(lines)):
        ln, no = lines[i], i + 1
        s = ln.strip()
        if s.startswith("|"):
            cells = table_cells(s)
            if not in_table:
                fields = [HEADER_FIELDS.get(_plain(c)) for c in cells]
                in_table = True
                if "repo" in fields:
                    header = fields
                    is_target = tuple(c.strip() for c in cells) == COLUMNS
                    saw_legacy = saw_legacy or not is_target
                    layout.append(("repo", ln))
                else:
                    header = None
                    layout.append(("keep", ln))
                last_item = None
                continue
            if header is None:
                layout.append(("keep", ln))
                continue
            if is_separator_row(cells):
                layout.append(("repo", ln))
                continue
            row = dict.fromkeys(("repo", "role", "what", "home", "site", "serves"), "")
            extra = []
            for idx, cell in enumerate(cells):
                field = header[idx] if idx < len(header) else None
                if field is None:
                    if cell:
                        extra.append(cell)
                elif not row[field]:
                    row[field] = cell
            name = _repo_name(row["repo"])
            if not name:
                layout.append(("keep", ln))
                continue
            what = "; ".join([w for w in [row["what"]] + extra if w])
            row_role = _plain(row["role"]) if is_target else (_plain(row["role"]) or role)
            repos.append(_repo(name, row_role, what, row["home"], no, row["site"], row["serves"]))
            layout.append(("repo", ln))
            continue
        in_table, header = False, None
        item = next((m for rx in ITEM_RES for m in [rx.match(ln)] if m), None)
        if item:
            saw_legacy = True
            repos.append(_repo(_repo_name(item.group(1)), role, item.group(2).strip(), "", no))
            last_item = repos[-1]
            layout.append(("repo", ln))
            continue
        if last_item is not None and s and ln[:1] in (" ", "\t") and not LIST_RE.match(ln):
            last_item["what"] = (last_item["what"] + " " + s).strip()
            layout.append(("cont", ln))
            continue
        last_item = None
        new_role = role_of(ln)
        if new_role:
            role = new_role
            saw_legacy = True
            layout.append(("role", ln))
            continue
        layout.append(("keep", ln))
    return repos, ("legacy" if saw_legacy else "table"), layout


def problems_of(repos, vault_names=None):
    out, seen = [], {}
    for r in repos:
        key = r["repo"].lower()
        if key in seen:
            out.append({"line": r["line"], "repo": r["repo"],
                        "problem": f"listed twice, first on line {seen[key]}"})
        else:
            seen[key] = r["line"]
        if r["role"] not in ROLES:
            out.append({"line": r["line"], "repo": r["repo"],
                        "problem": f"role {r['role']!r} is not owned, reference or other"})
        if bool(r["site"]) != bool(r["serves"]):
            missing = "Serves vault" if r["site"] else "Site"
            out.append({"line": r["line"], "repo": r["repo"], "problem": f"{missing} is empty"})
        if r["serves"] and vault_names is not None and r["serves"] not in vault_names:
            out.append({"line": r["line"], "repo": r["repo"],
                        "problem": f"serves {r['serves']!r}, which the vault registry does not name"})
    return out


def list_repos(vault, paraos_home=None):
    path = rule_file(vault)
    if not path.is_file():
        return {"file": str(path), "shape": "absent", "repos": [], "problems": []}
    repos, shape, _ = parse(read_text(path))
    if shape == "legacy":
        for r in repos:
            if not r["home"]:
                found = pick_home(r["what"], vault)
                r["home_path"] = found
    names = [e.get("name") for e in registry(paraos_home) if isinstance(e, dict)]
    return {"file": str(path), "shape": shape, "repos": repos,
            "problems": problems_of(repos, names or None)}


# --- converting -----------------------------------------------------------------------------

def _cell(text):
    return re.sub(r"(?<!\\)\|", r"\\|", str(text or "")).strip()


def table(repos):
    rows = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for r in repos:
        rows.append("| " + " | ".join(_cell(c) for c in (
            f"`{r['repo']}`", r["role"], r["what"], r["home"], r["site"], r["serves"])) + " |")
    return rows


def convert(vault):
    path = rule_file(vault)
    out = {"file": str(path), "changed": False, "written": False, "text": None, "repos": [],
           "to_fill": [], "dropped": []}
    if not path.is_file():
        return out
    raw = read_text(path)
    repos, shape, layout = parse(raw)
    if shape == "table":
        out["repos"] = repos
        return out
    for r in repos:
        if not r["home"]:
            folder = pick_home(r["what"], vault)
            if folder:
                r["home"] = f"[{folder}](../../{folder})"
                r["home_path"] = folder
        if not r["role"]:
            r["role"] = "owned"
        fill = {}
        if not r["home"]:
            fill["home"] = True
        hints = [] if r["site"] else site_hints(r["what"])
        if hints:
            fill["site_hint"] = hints
        if fill:
            out["to_fill"].append({"repo": r["repo"], **fill})
    lines, placed = [], False
    for no, (kind, ln) in enumerate(layout, start=1):
        if kind in ("repo", "role", "cont"):
            if kind == "role":
                out["dropped"].append({"line": no, "text": ln.strip()})
            if not placed:
                if lines and lines[-1].strip():
                    lines.append("")
                lines.extend(table(repos))
                placed = True
            continue
        if not ln.strip() and lines and not lines[-1].strip():
            continue
        if placed and ln.strip() and lines and lines[-1].startswith("|"):
            lines.append("")
        lines.append(ln)
    while lines and not lines[-1].strip():
        lines.pop()
    text = "\n".join(lines) + "\n"
    out.update(changed=text != raw.replace("\r\n", "\n"), text=text, repos=repos)
    return out


def write(path, text):
    """Write `text` in the line endings the file already uses, atomically."""
    path = Path(path)
    data = path.read_bytes()
    if b"\r\n" in data:
        text = text.replace("\n", "\r\n")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".code-repos.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description="The code repos a vault steers, as one table.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="read the repos and report problems")
    ls.add_argument("--vault", required=True)
    ls.add_argument("--paraos-home", help="override for $PARAOS_HOME (default: ~/.paraos)")
    cv = sub.add_parser("convert", help="turn an older code-repos file into the table")
    cv.add_argument("--vault", required=True)
    cv.add_argument("--write", action="store_true", help="write the converted file")
    args = ap.parse_args(argv)
    utf8_stdout()
    if not Path(args.vault).is_dir():
        print(f"paraos_repos: --vault {args.vault!r} is not a folder", file=sys.stderr)
        return 2
    if args.cmd == "list":
        result = list_repos(args.vault, args.paraos_home)
    else:
        result = convert(args.vault)
        if args.write and result["changed"]:
            write(result["file"], result["text"])
            result["written"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
