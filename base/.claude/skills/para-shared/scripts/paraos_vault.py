#!/usr/bin/env python3
"""Reading a PARA vault, for any skill that needs to.

Imported, and run from the command line for a few one-off questions: a skill ships its own
entry point in `<skill>/scripts/` and calls into this. The first caller is
`para-daily-brief/scripts/brief_scan.py`.

    py -3 paraos_vault.py resolve <name> [--vault .]
    py -3 paraos_vault.py lifecycles [--vault .]
    py -3 paraos_vault.py links dangling [--root archive] [--vault .]
    py -3 paraos_vault.py links inbound <name> [--vault .]
    py -3 paraos_vault.py move-plan <src> <dst> [--vault .]
    py -3 paraos_vault.py hashes [--vault .]
    py -3 paraos_vault.py registry [<name>] [--vault .]
    py -3 paraos_vault.py changed <file>
    py -3 paraos_vault.py sources [--vault .]
    py -3 paraos_vault.py ingest-logs [--paraos-home DIR]

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "para-shared" / "scripts"))
    from paraos_vault import live_lines, open_tasks, resolve_entity

What lives here is what two skills would otherwise each answer their own way: whether a
folder is a vault root, what the machine's registry says about it and its neighbours, where
a checkbox may live, what counts as one, what a task marker means, which folder a name
resolves to, when a file was really last touched, what a link points at and what a move
would have to rewrite, whether two files hold the same bytes (and whether two copies of one
file differ in more than line endings), what a vault declares it is built from and which
template in a para-os clone that names, and the numbers a vault's own rules state. A second implementation of any of those is a vault getting two answers to one
question, which is the failure this repo exists to prevent.

What does NOT live here: anything a single skill decides. Bucketing against a date,
ranking, thresholds a skill invents for its own report, and every word an operator reads
stay with the skill that owns them.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

# --- what a vault's own rules state -------------------------------------------------------
# One home for numbers that several skills quote. A skill that disagrees with one of these
# tells an operator their file is fine while another says it needs grooming.

WIP_THRESHOLD = 12          # open items in one action file, at or above which it needs grooming
FALSELY_OVERDUE_DAYS = 30   # overdue by more than this reads as a date that was never real
DORMANT_ENTITY_DAYS = 180   # untouched this long: a retirement candidate
BRIEF_LINE_CAP = 500        # a brief past this is over-grown
STALE_FILE_DAYS = 60        # an action file with open items, untouched this long
CLUSTER_SECONDS = 60        # mtimes this close mean a bulk write, not an edit

# --- what a task looks like ---------------------------------------------------------------

TASK_RE = re.compile(r"^- \[ \] (.*)$")
CLOSED_TASK_RE = re.compile(r"^- \[[xX]\] (.*)$")
H1_RE = re.compile(r"^# (.*)$")
H2_RE = re.compile(r"^## (.*)$")
FENCE_TOKEN_RE = re.compile(r"^\s*(`{3,}|~{3,})")

DUE_RE = re.compile(r"📅️?\s*(\d{4}-\d{2}-\d{2})")
START_RE = re.compile(r"🛫️?\s*(\d{4}-\d{2}-\d{2})")
SCHEDULED_RE = re.compile(r"⏳️?\s*(\d{4}-\d{2}-\d{2})")
RECUR_RE = re.compile(r"🔁️?\s*(every [^📅🛫⏳🔺🔼🔽⏬✅➕❌\n]+)")
PRIORITY_RE = re.compile(r"[🔺🔼🔽⏬]")
ANY_DATE_RE = re.compile(r"[📅🛫⏳]️?\s*(\S+)")
MARKERS_RE = re.compile(r"\s*[📅🛫⏳🔁🔺🔼🔽⏬✅][^|]*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
LINK_TITLE_RE = re.compile(r"""\s+(?:"[^"]*"|'[^']*')$""")
DONE_RE = re.compile(r"✅️?\s*(\d{4}-\d{2}-\d{2})")

# --- what a table and a header line look like ---------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
CELL_MARKS_RE = re.compile(r"[`*]")
SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
STAGE_RE = re.compile(r"^[*_]{0,2}stage[*_]{0,2}\s*:\s*(.+)$", re.IGNORECASE)
HEADER_FIELD_RE = re.compile(r"^\*\*\s*([^*]+?)\s*:?\s*\*\*\s*:?\s*(.*)$")
COMMENT_LINE_RE = re.compile(r"^<!--.*-->$")
SINCE_RE = re.compile(r"since\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

PRIORITY_RANK = {"🔺": 2, "🔼": 1, "": 0, "🔽": -1, "⏬": -2}

CADENCE_DAYS = {
    "day": 1, "daily": 1, "week": 7, "weekly": 7, "fortnight": 14,
    "month": 30, "monthly": 30, "quarter": 91, "quarterly": 91,
    "year": 365, "yearly": 365, "annum": 365,
}


class CollectedVault(Exception):
    """A vault resting in collected state, where every markdown file lives under
    resources/mds/ with its path encoded in the filename. Reading it needs the path map,
    which these helpers do not implement, and a vault-shaped read finds no action file at
    all: it would report a thriving vault as an empty one. Refusing is the only honest
    answer, and the skill falls back to scanning by hand."""


def is_collected(vault):
    """Whether a vault rests in collected state: `resources/mds/` holds any `__`-encoded
    `.md`, the rule operating-discipline.md states for the read-only iPad delivery.

    Asked on its own by a reader that does not need the PARA folders: `flip.ps1 collect`
    never moves `CLAUDE.md` or anything under `.claude/`, so a vault's declarations and its
    installed copies still read in place, and such a reader answers with the state named
    rather than refusing. A reader that does need the folders refuses, through
    `refuse_if_collected`.
    """
    mds = Path(vault) / "resources" / "mds"
    return mds.is_dir() and any(mds.glob("*__*.md"))


def refuse_if_collected(vault):
    """Raise `CollectedVault` where `is_collected` says the vault is collected."""
    if is_collected(vault):
        raise CollectedVault(
            "this vault is collected (resources/mds/ holds its markdown); "
            "scan it by hand with the skill's own reference procedure")


# --- names --------------------------------------------------------------------------------

def norm(name):
    """Fold a name to its folder form: lowercase, and every separator a hyphen.

    Spaces, dots and underscores all separate, so "Para OS 2026.09.04",
    "para os 2026 09 04" and "para-os-2026-09-04" are one name.
    """
    folded = re.sub(r"[\s._]+", "-", str(name).strip().lower())
    return re.sub(r"-{2,}", "-", folded).strip("-")


# --- the vault itself, and the machine's registry of vaults ------------------------------

def vault_root(path):
    """Whether a folder is a PARA vault root, by the rule every skill states in its own Step
    1: `projects/` plus at least one of `areas/` or `archive/`, and a `CLAUDE.md`. Returns
    what was actually checked, so a caller can say why a folder failed rather than just that
    it did.
    """
    path = Path(path)
    missing = []
    if not (path / "projects").is_dir():
        missing.append("projects/")
    if not ((path / "areas").is_dir() or (path / "archive").is_dir()):
        missing.append("areas/ or archive/")
    if not (path / "CLAUDE.md").is_file():
        missing.append("CLAUDE.md")
    return {"root": not missing, "missing": missing}


def paraos_home_dir(paraos_home=None):
    """`paraos_home` where given, else `$PARAOS_HOME`, else `~/.paraos`."""
    return Path(paraos_home or os.environ.get("PARAOS_HOME") or (Path.home() / ".paraos"))


def find_clone(explicit=None, paraos_home=None):
    """The para-os clone a scan reads masters from, by para-shared/scripts.md's rule: an
    explicit `--clone` as given, else `<paraos home>/para-os` where that folder exists.
    `(path, "explicit" | "default")`, or `(None, None)`: no clone found, which a caller
    reports as its own state, never as a master it could not read.
    """
    if explicit:
        return Path(explicit), "explicit"
    default = paraos_home_dir(paraos_home) / "para-os"
    return (default, "default") if default.is_dir() else (None, None)


def registry(paraos_home=None):
    """The machine's vault registry, `<paraos_home>/vaults.json`: every vault this machine
    knows about, as written (`name`, `path`, `kind`, `purpose`, `active`). `paraos_home`
    defaults to `$PARAOS_HOME`, else `~/.paraos`. `[]` where the file is missing or
    unparseable, never an exception: a registry read is background context for a stop line,
    not something a run needs to fail on.
    """
    home = paraos_home_dir(paraos_home)
    try:
        data = json.loads((home / "vaults.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def registered_vault(entries, path):
    """The registry entry whose path is `path` itself or a parent folder of it, else None.
    Compared as `same_place`, since one folder can be spelled differently between a registry
    entry and a session's own `pwd`: either slash or case on Windows, a short `RUNNER~1`
    name, or a symlink the caller has already resolved (macOS's `/var` is one). For the "not
    a vault root, but the registry lists it at ..." stop line.
    """
    target = same_place(path)
    for entry in entries:
        entry_path = entry.get("path")
        if not entry_path:
            continue
        root = same_place(entry_path)
        # A drive or filesystem root already ends in its separator: "/" + os.sep is "//".
        if target == root or target.startswith(root if root.endswith(os.sep) else root + os.sep):
            return entry
    return None


def registry_holding(entries, name, exclude=None):
    """Every registered vault holding an entity folder named `name` (folded the way
    `resolve_entity` folds one), under `projects/`, `resources/ideas/`, `areas/` or anywhere
    under `archive/`. `exclude` is a vault root to skip, the current one, so a caller does
    not report its own vault back to itself.

    A registered path that does not exist or cannot be listed comes back as
    `{"vault": ..., "root": ..., "unreadable": True}` rather than being silently dropped: a
    scan that passed over a vault in silence would report it as clean when it was never
    read at all. Directory names only - nothing inside another vault's files is opened.
    """
    key = norm(name)
    exclude_place = same_place(exclude) if exclude else None
    out = []
    for entry in entries:
        entry_path = entry.get("path")
        if not entry_path:
            continue
        root = abspath(entry_path)
        if exclude_place and same_place(root) == exclude_place:
            continue
        try:
            hits = _entity_folders(root, key)
        except OSError:
            out.append({"vault": entry.get("name"), "root": str(root), "unreadable": True})
            continue
        for rel, kind in hits:
            out.append({"vault": entry.get("name"), "root": str(root), "path": rel,
                        "kind": kind})
    return out


def _entity_folders(root, key):
    """(vault-relative posix path, kind) for every folder under `root` whose name folds to
    `key`, in projects/, resources/ideas/, areas/ and anywhere under archive/. Raises
    OSError where `root` itself is not a readable directory, for `registry_holding` to catch
    and report as unreadable rather than silently empty."""
    if not root.is_dir():
        raise OSError(f"not a directory: {root}")
    found = []
    for bucket, kind in (("projects", "project"), ("resources/ideas", "idea"),
                        ("areas", "area")):
        base = root / bucket
        if base.is_dir():
            for d in sorted(base.iterdir()):
                if d.is_dir() and norm(d.name) == key:
                    found.append((rel_posix(root, d), kind))
    archive = root / "archive"
    if archive.is_dir():
        for d in sorted(archive.rglob("*")):
            if d.is_dir() and norm(d.name) == key:
                found.append((rel_posix(root, d), "archived"))
    return found


# --- reading ------------------------------------------------------------------------------

def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def split_lines(text):
    """A text's lines, broken on `\n` alone with a trailing `\r` dropped - the lines git and
    an editor number. `str.splitlines()` also breaks on `\x0c`, `\x85`, `\u2028` and the
    like, so a note quoting one would report every later line number off by one."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line.rstrip("\r") for line in lines]


def read_lines(path):
    return split_lines(read_text(path))


def fence_step(fence, line):
    """The fence state after one line, and whether the line itself is a fence marker
    (an opening or a closing line).

    Shared by every fenced-block reader, so the rule is stated once: a fence closes only
    on a run of the character that opened it, at least as long as that opening run, with
    nothing but whitespace after it. A four-backtick block keeps a three-backtick line
    inside it, never closed by the shorter run, and a ```` ```python ```` line inside a
    block opens nothing and closes nothing - the same rule strip_code() needs to keep an
    inner sample's syntax from leaking.
    """
    m = FENCE_TOKEN_RE.match(line)
    token = m.group(1) if m else None
    if token and token[0] == "`" and "`" in line[m.end():]:
        token = None  # a backtick run closed on its own line is inline code, not a fence
    if fence is None:
        return (token, True) if token else (None, False)
    if (token and token[0] == fence[0] and len(token) >= len(fence)
            and not line[m.end():].strip()):
        return None, True
    return fence, False


def live_lines(lines):
    """(line number, text) for each line outside a fenced block, 1-indexed.

    A checkbox quoted as a sample inside a fence is documentation, not work, and a plain
    grep counts it. Every reader here goes through this.
    """
    fence = None
    for i, raw in enumerate(lines, start=1):
        fence, marker = fence_step(fence, raw)
        if marker:
            continue
        if fence is None:
            yield i, raw


def blank_spans(line):
    """One line with its inline code spans blanked to spaces, a span closing on a backtick
    run of its own length. Backticks nothing closes are prose and stay."""
    out, i = list(line), 0
    while i < len(line):
        if line[i] != "`":
            i += 1
            continue
        opened = i
        while i < len(line) and line[i] == "`":
            i += 1
        run, j = i - opened, i
        while j < len(line):
            if line[j] != "`":
                j += 1
                continue
            closed = j
            while j < len(line) and line[j] == "`":
                j += 1
            if j - closed == run:
                out[opened:j] = " " * (j - opened)
                i = j
                break
    return "".join(out)


def strip_code(text):
    """The text with every fenced block and inline code span blanked to spaces.

    Same length and same line breaks, so a line number or an offset taken from the result
    still points at the original. A fence closes only on a run of its own character at least
    as long as the one that opened it, so a four-backtick block keeps the shorter fences
    inside it. Every link and reference reader below reads this rather than the raw text,
    because a quoted syntax is not a used syntax.
    """
    out, fence = [], None
    parts = text.split("\n")
    for i, part in enumerate(parts):
        body = part.rstrip("\r")
        end = part[len(body):] + ("\n" if i < len(parts) - 1 else "")
        before = fence
        fence, _ = fence_step(fence, body)
        if before is None and fence is None:
            out.append(blank_spans(body) + end)
        else:
            out.append(" " * len(body) + end)
    return "".join(out)


def parse_date(text):
    try:
        return datetime.strptime(str(text), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def iso(day):
    return day.isoformat() if day else None


def cadence_days(cadence):
    """Days in "every week", "every 2 weeks", "every 10 days". None when unreadable."""
    if not cadence:
        return None
    body = cadence[len("every"):].strip().lower() if cadence.lower().startswith("every") else cadence
    m = re.match(r"(\d+)\s+(\w+)", body)
    count, word = (int(m.group(1)), m.group(2)) if m else (1, body.split()[0] if body.split() else "")
    word = word.rstrip("s")
    return CADENCE_DAYS[word] * count if word in CADENCE_DAYS else None


def parse_markers(body):
    """Every task marker on one task line, plus the text without them.

    A date-shaped marker still has to be a real date: `2026-13-45` matches the shape and
    names no day, so it comes back as no date with `malformed_date` set, never silently.
    Every date marker on the line is checked, so `⏳ tomorrow` is flagged even where a
    valid `📅` sits beside it.
    """
    dates = {}
    for field, pattern in (("due", DUE_RE), ("scheduled", SCHEDULED_RE), ("start", START_RE)):
        found = pattern.search(body)
        dates[field] = found.group(1) if found and parse_date(found.group(1)) else None
    malformed = any(not DATE_RE.match(token) or not parse_date(token[:10])
                    for token in ANY_DATE_RE.findall(body))
    recur = RECUR_RE.search(body)
    prio = PRIORITY_RE.search(body)
    return {
        "text": MARKERS_RE.sub("", body).strip(),
        "due": dates["due"],
        "scheduled": dates["scheduled"],
        "start": dates["start"],
        "recurring": recur.group(1).strip() if recur else None,
        "priority": prio.group(0) if prio else "",
        "malformed_date": malformed,
    }


def first_link(text):
    """The target of the first `[label](target)` in a string, or None. Read through
    `link_spans`, so a target carrying parentheses is kept whole."""
    text = str(text)
    for start, end, bracket in link_spans(text):
        target = text[start:end].strip()
        if bracket is not None and target:
            return target
    return None


def table_cells(text):
    """The cells of one table row, outer pipes dropped. An escaped `\\|` is part of its cell,
    as in Obsidian's `[[note\\|alias]]`, and is kept as written."""
    row = re.sub(r"(?<!\\)\|+$", "", text.strip().lstrip("|"))
    return [c.strip() for c in re.split(r"(?<!\\)\|", row)]


def is_separator_row(cells):
    return bool(cells) and all(SEPARATOR_CELL_RE.match(c.replace(" ", "")) for c in cells)


def _tasks(path, pattern, extra=None):
    """Every checkbox `pattern` matches in one file, with the heading it sits under and its
    markers. Shared by `open_tasks` and `closed_tasks`, so what counts as a checkbox and
    which heading owns it is one rule stated once rather than kept in step by hand.

    The section is the nearest `##`, except under `## Next actions`, where the document's
    `#` says more than the heading does. `extra`, given the raw text after the checkbox
    marker, returns fields to add beyond what every checkbox already carries.
    """
    h1 = h2 = None
    out = []
    for lineno, text in live_lines(read_lines(path)):
        m = H1_RE.match(text)
        if m:
            h1, h2 = m.group(1).strip(), None
            continue
        m = H2_RE.match(text)
        if m:
            h2 = m.group(1).strip()
            continue
        m = pattern.match(text)
        if not m:
            continue
        task = {"line": lineno,
                "section": h1 if (h2 or "").lower() == "next actions" else (h2 or h1)}
        task.update(parse_markers(m.group(1)))
        task["first_link"] = first_link(m.group(1))
        if extra:
            task.update(extra(m.group(1)))
        out.append(task)
    return out


def open_tasks(path):
    """Every open checkbox in one file, with the heading it sits under and its markers.

    The section is the nearest `##`, except under `## Next actions`, where the document's
    `#` says more than the heading does.
    """
    return _tasks(path, TASK_RE)


def closed_tasks(path):
    """Every closed checkbox (`- [x]` or `- [X]`) in one file, the same shape `open_tasks`
    returns, plus `done`: the completion date from a `✅ YYYY-MM-DD` marker on the line,
    None where it carries none. What counts as a checkbox is this library's rule, so this
    reads `open_tasks`'s own section and marker logic rather than a second copy of it.
    """
    def done_date(raw):
        found = DONE_RE.search(raw)
        return {"done": found.group(1) if found and parse_date(found.group(1)) else None}
    return _tasks(path, CLOSED_TASK_RE, extra=done_date)


# --- where things live --------------------------------------------------------------------

def is_live(rel):
    """A path a checkbox may live in: not archive/, not resources/."""
    posix = Path(rel).as_posix()
    return not (posix.startswith("archive/") or posix.startswith("resources/"))


def action_files(vault):
    """Every file a checkbox may live in, per the vault's own rule: action files and
    contact files, never archive/ and never resources/."""
    vault = Path(vault)
    found = list(sorted(vault.rglob("actions.md")))
    for pattern in ("areas/network/*.md", "contacts/*.md", "people/*.md"):
        found += [p for p in sorted(vault.glob(pattern)) if p.name != "actions.md"]
    return [p for p in found if is_live(p.relative_to(vault))]


def scope_of(vault, path):
    """(bucket letter, entity label) for a file. Contact files aggregate to network,
    because one row per person floods any report."""
    parts = Path(path).relative_to(vault).parts
    if parts[0] == "projects":
        return "P", "/".join(parts[1:-1]) or parts[0]
    if parts[0] == "areas":
        if len(parts) >= 3 and parts[1] == "network":
            return "A", "network"
        return "A", "/".join(parts[1:-1]) or parts[0]
    if parts[0] in ("contacts", "people"):
        return "A", "network"
    return "?", "/".join(parts[:-1]) or parts[0]


BUCKET_LETTERS = {"projects": "P", "areas": "A", "resources/ideas": "I"}


def entity_candidates(vault, buckets=("projects", "areas")):
    """Every folder that could be `resolve_entity`'s answer, one per project, area or idea.
    `buckets` picks which of `projects/`, `areas/` and `resources/ideas/` (see
    `BUCKET_LETTERS`) to scan; the default is today's two, so an existing caller sees no
    change."""
    out = []
    for bucket in buckets:
        letter = BUCKET_LETTERS[bucket]
        base = Path(vault) / bucket
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if d.is_dir():
                out.append({"bucket": letter, "label": d.name,
                            "path": f"{bucket}/{d.name}", "key": norm(d.name)})
    return out


def resolve_entity(vault, query, buckets=("projects", "areas")):
    """Exactly one project, area (or idea, once `buckets` includes `resources/ideas`), or an
    answer about where the thing actually is.

    Exact match first, so `acme-website` still reaches its own folder in a vault that also
    holds `acme-website-v2`. Two partial matches are never chosen between, and a name that
    matches nothing is looked for in resources/ideas/ and archive/ before it is called
    missing: where the thing lives is a better answer than that it does not exist. Where
    `resources/ideas` is already one of `buckets`, an idea is resolved as a candidate like
    any other and is not reported a second time under `elsewhere`.
    """
    vault = Path(vault)
    key = norm(query)
    candidates = entity_candidates(vault, buckets)
    exact = [c for c in candidates if c["key"] == key]
    if len(exact) == 1:
        return {"query": query, "status": "resolved", "match": exact[0]}
    partial = [c for c in candidates if key and key in c["key"]]
    if len(partial) == 1:
        return {"query": query, "status": "resolved", "match": partial[0]}
    if len(partial) > 1:
        return {"query": query, "status": "ambiguous", "match": None,
                "candidates": [c["path"] for c in partial]}

    elsewhere = []
    if "resources/ideas" not in buckets:
        ideas = vault / "resources" / "ideas"
        if ideas.is_dir():
            elsewhere += [{"kind": "idea", "path": f"resources/ideas/{d.name}"}
                          for d in sorted(ideas.iterdir())
                          if d.is_dir() and norm(d.name) == key]
    archive = vault / "archive"
    if archive.is_dir():
        elsewhere += [{"kind": "archived", "path": d.relative_to(vault).as_posix()}
                      for d in sorted(archive.rglob("*")) if d.is_dir() and norm(d.name) == key]
    near = sorted(c["path"] for c in candidates
                  if key and (key[:6] in c["key"] or c["key"][:6] in key))[:3]
    return {"query": query, "status": "elsewhere" if elsewhere else "unresolved",
            "match": None, "elsewhere": elsewhere, "nearest": near}


# --- when a file was really last touched --------------------------------------------------

def git_bytes(directory, args, input=None):
    """git's own stdout as the bytes it wrote, run in `directory`. None where git cannot
    answer: a non-zero exit (not a repository, a ref or a path that names nothing), no git
    on PATH, or a run past 30 seconds.

    For a file's content taken from a commit, which is compared byte for byte against a
    copy on disk and need not be text at all: decoding it first would turn every byte
    outside UTF-8 into the same replacement character, and two different files into one.
    `git()` is this decoded.

    `input` is written to git's stdin, for the plumbing that reads its requests there:
    `cat-file --batch` answers every blob a history walk names in one process, where a
    `show` per blob would start git hundreds of times.
    """
    try:
        done = subprocess.run(["git", "-C", str(directory)] + list(args), input=input,
                              capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout


def git(vault, args):
    """git's own stdout, decoded as UTF-8 regardless of the console's codepage.

    Not `subprocess.run(..., text=True)`: with no explicit encoding that decodes with the
    console's own locale codec, and on a Windows console outside UTF-8, git output naming
    anything non-ASCII (a vault's own prose, in a commit message or a diff) raises inside
    the reader thread. The call then comes back as None, which a caller cannot tell apart
    from "git said no" - the raise never reaches here to be caught. So git's raw bytes are
    taken from `git_bytes` and decoded here, the one place that decides how.
    """
    out = git_bytes(vault, args)
    return None if out is None else out.decode("utf-8", errors="replace")


# git quotes a path holding anything outside ASCII as an octal-escaped C string unless told
# not to, and a vault names its files in the operator's own language.
UNQUOTED_STATUS = ["-c", "core.quotePath=false", "status", "--porcelain"]


def git_status_lines(vault, args=()):
    """`git status --porcelain` for the vault alone, each path made vault-relative.

    Porcelain output names paths from the repo root whatever `-C` says, so a vault sitting
    below its repo's root (a vault inside a larger repo) would otherwise read every path
    with the prefix doubled, and see changes outside the vault as its own. None where git
    cannot answer. Each item is (status code, vault-relative posix path).
    """
    prefix = git(vault, ["rev-parse", "--show-prefix"])
    if prefix is None:
        return None
    prefix = prefix.strip()
    out = git(vault, UNQUOTED_STATUS + list(args or ["--", "."]))
    if out is None:
        return None
    lines = []
    for line in out.splitlines():
        name = line[3:].strip().strip('"')
        if " -> " in name:
            name = name.split(" -> ")[-1].strip('"')
        if not name.startswith(prefix):
            continue
        lines.append((line[:2], name[len(prefix):]))
    return lines


def git_modified(vault):
    lines = git_status_lines(vault)
    return {(Path(vault) / name).resolve() for _, name in lines or ()}


def git_untracked(vault, under):
    """The files `git status` reports untracked (`??`) under `under`, a folder or path
    relative to `vault`, as vault-relative posix paths. None, not `[]`, where git cannot
    answer at all (no repo, no git on PATH), so a caller can tell "nothing untracked" from
    "could not check": a report that reads the first as the second tells an operator a move
    was clean when it was never verified.
    """
    lines = git_status_lines(vault, ["--untracked-files=all", "--", Path(under).as_posix()])
    if lines is None:
        return None
    return [Path(name).as_posix() for code, name in lines if code == "??"]


def git_last_commit_date(vault, path):
    try:
        rel = Path(path).resolve().relative_to(Path(vault).resolve()).as_posix()
    except ValueError:
        return None
    out = git(vault, ["log", "-1", "--format=%as", "--", rel])
    return out.strip() if out and out.strip() else None


ALL_ZERO_HASH = "0" * 40


def git_blame_line_date(vault, path, line):
    """The date one line was really last touched, from `git blame` against the working
    tree, not `git log -L` against the file's current line numbers.

    `git log -L <n>,<n>:<file>` asks for the history of whatever sits on line `n` today,
    which a later, unrelated edit elsewhere in the file can shift without the line's own
    content ever changing - the query then walks the wrong history. `git blame -L <n>,<n>
    --porcelain -w` follows the line's content through history instead, the same way it
    tracks any line for `git blame`'s normal output, and it reads the working tree, so an
    edit not yet committed shows up rather than being silently skipped.

    Returns the ISO date of the commit that introduced the line, the literal string
    "uncommitted" where `git blame`'s all-zero commit hash says the working tree holds an
    edit git has not committed yet, or None where git could not answer at all (no git, no
    history, an unreadable path).
    """
    try:
        rel = Path(path).resolve().relative_to(Path(vault).resolve()).as_posix()
    except ValueError:
        return None
    out = git(vault, ["blame", "-L", f"{line},{line}", "--porcelain", "-w", "--", rel])
    if not out:
        return None
    first = out.splitlines()[0].split()
    if not first:
        return None
    commit_hash = first[0]
    if commit_hash == ALL_ZERO_HASH:
        return "uncommitted"
    log_out = git(vault, ["log", "-1", "--format=%as", commit_hash])
    return log_out.strip() if log_out and log_out.strip() else None


def file_dates(vault, paths):
    """{path: YYYY-MM-DD} for each file, by mtime, with one correction.

    A checkout, a sync or a collect writes many files in the same second, which leaves
    every mtime saying today and hides what is actually stale. Where three or more files
    share a moment, git's own last-commit date is the honest answer for the ones git says
    are unmodified.
    """
    paths = [Path(p) for p in paths]
    stamps = {}
    for p in paths:
        try:
            stamps[p] = p.stat().st_mtime
        except OSError:
            stamps[p] = None

    clustered = set()
    run = []
    for t, p in sorted((t, p) for p, t in stamps.items() if t is not None):
        if run and t - run[0][0] <= CLUSTER_SECONDS:
            run.append((t, p))
        else:
            if len(run) >= 3:
                clustered.update(p for _, p in run)
            run = [(t, p)]
    if len(run) >= 3:
        clustered.update(p for _, p in run)

    modified = git_modified(vault) if clustered else set()
    out = {}
    for p, t in stamps.items():
        stamp = date.fromtimestamp(t).isoformat() if t else None
        # git_modified names each path resolved, so a relative or symlinked one is compared
        # in that form too, or an uncommitted edit would read as its last commit's date.
        if p in clustered and p.resolve() not in modified:
            stamp = git_last_commit_date(vault, p) or stamp
        out[p] = stamp
    return out


# --- entity state -------------------------------------------------------------------------

def stage_line(path):
    """An entity's stage, by three rules in order: a line opening on a stage label; the
    Stage row of a `## Status` table, never its header row; else the first prose line."""
    lines = [text for _, text in live_lines(read_lines(path))]
    for text in lines:
        stripped = text.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^[*_]{0,2}(stage|status)[*_]{0,2}\s*:\s*(.+)$", stripped, re.IGNORECASE)
        if m:
            return re.sub(r"[*_]", "", m.group(2)).strip()
    in_status = False
    for text in lines:
        if re.match(r"^##\s+status\b", text.strip(), re.IGNORECASE):
            in_status = True
            continue
        if in_status:
            if not text.strip():
                continue
            if text.strip().startswith("|"):
                cells = table_cells(text)
                if cells and cells[0].lower() == "stage" and len(cells) > 1:
                    return cells[1]
                continue
            if text.strip().startswith("#"):
                break
            return text.strip()
    for text in lines:
        if text.strip() and not text.strip().startswith("#"):
            return text.strip()[:200]
    return None


def stage_of(path):
    """An entity's Stage line in its parts: the declared name, the qualifier behind it, the
    `since` date and every other dated clause. None where the document carries no such line."""
    for _, text in live_lines(read_lines(path)):
        stripped = text.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = STAGE_RE.match(stripped)
        if m:
            return stage_parts(re.sub(r"[*_]", "", m.group(1)).strip(), stripped)
    return None


def stage_parts(body, raw):
    name = re.split(r"\s+-\s+", body.split("(", 1)[0])[0].strip()
    rest = body[len(name):].strip().lstrip("-").strip()
    name = name.rstrip(".,;:!?").strip()
    if rest.startswith("(") and rest.endswith(")"):
        rest = rest[1:-1].strip()
    since = SINCE_RE.search(rest)
    since = since.group(1) if since and parse_date(since.group(1)) else None
    facts = []
    for clause in rest.split(";"):
        found = DATE_RE.search(clause)
        if not found or not parse_date(found.group(0)):
            continue
        if since and found.group(0) == since and SINCE_RE.search(clause):
            continue
        facts.append((clause.strip(), found.group(0)))
    return {"name": name, "qualifier": rest, "since": since,
            "dated_facts": facts, "raw": raw}


def header_fields(path):
    """The bold-led lines under an entity's title, field name to text, in the order written.
    A link is left as written, so `first_link` can take its target out of one.

    A one-line HTML comment (`<!-- ... -->`) is skipped rather than treated as the end of
    the block: every real vault CLAUDE.md carries `<!-- para-os-template: ... -->` between
    its title and its first bold field.
    """
    fields, titled = {}, False
    for _, text in live_lines(read_lines(path)):
        stripped = text.strip()
        if not titled:
            titled = stripped.startswith("#")
            continue
        if COMMENT_LINE_RE.match(stripped):
            continue
        if not stripped:
            if fields:
                break
            continue
        m = HEADER_FIELD_RE.match(stripped)
        if not m:
            break
        fields[m.group(1).strip()] = m.group(2).strip()
    return fields


def field_ci(fields, name):
    """A header field or register column by name, ignoring case: a lifecycle's rule file
    names its fields in prose, and a vault's own table header may not match it letter for
    letter."""
    name = name.strip().lower()
    for k, v in fields.items():
        if k.strip().lower() == name:
            return v
    return None


def register_rows(path):
    """Every row of every table in a register, one dict per row: each header cell as a key,
    the first column again as `name`, plus the `##` section it sits under, its line, and
    `cells`, the number of cells its own line actually held before padding to the header's
    width."""
    section, header, rows = None, None, []
    for lineno, text in live_lines(read_lines(path)):
        m = H2_RE.match(text)
        if m:
            section, header = m.group(1).strip(), None
            continue
        stripped = text.strip()
        if not stripped.startswith("|"):
            header = None
            continue
        cells = table_cells(stripped)
        if header is None:
            header = [CELL_MARKS_RE.sub("", c).strip() for c in cells]
            continue
        if is_separator_row(cells):
            continue
        row = dict(zip(header, cells + [""] * (len(header) - len(cells))))
        row.update({"name": cells[0] if cells else "", "section": section, "line": lineno,
                    "cells": len(cells)})
        rows.append(row)
    return rows


# --- what the vault declares ---------------------------------------------------------------

DELIVERY_SCRIPT = "flip.ps1"         # at a vault root with no **Delivery:** line: the delivery below
DETECTED_DELIVERY = "readonly-ipad"


def _declared(value):
    """One declaration line's value as a name: markdown marks dropped, whitespace
    collapsed, None where nothing is left."""
    text = re.sub(r"\s+", " ", CELL_MARKS_RE.sub("", value or "")).strip()
    return text or None


def declarations(vault):
    """What a vault says it is built from, read from the lines under its `CLAUDE.md` title
    (`header_fields`): {type, delivery, delivery_source, flavor, modules, collected}.

    `delivery_source` is "declared" where a `**Delivery:**` line names one; "detected"
    where there is no such line and `flip.ps1` sits at the vault root, which puts the vault
    on `readonly-ipad` whether it says so or not (operating-discipline.md, "The read-only
    iPad delivery"); else None. `modules` is the `**Modules:**` line split on its commas in
    the order written, `[]` where the vault declares none. `collected` is `is_collected`:
    the declarations still read in a collected vault, since `flip.ps1` never moves
    `CLAUDE.md`, but most of what a caller goes on to read has moved.

    One reading for every skill, because the declaration picks the master a vault is
    measured against: two skills reading it two ways compare one vault against two
    templates and give it two verdicts.
    """
    vault = Path(vault)
    fields = header_fields(vault / "CLAUDE.md")
    delivery = _declared(field_ci(fields, "Delivery"))
    source = "declared" if delivery else None
    if not delivery and (vault / DELIVERY_SCRIPT).is_file():
        delivery, source = DETECTED_DELIVERY, "detected"
    modules = [m.strip() for m in (_declared(field_ci(fields, "Modules")) or "").split(",")]
    return {"type": _declared(field_ci(fields, "Type")), "delivery": delivery,
            "delivery_source": source, "flavor": _declared(field_ci(fields, "Flavor")),
            "modules": [m for m in modules if m], "collected": is_collected(vault)}


def lifecycles(vault):
    """Every lifecycle a vault's CLAUDE.md declares: the heading, the entity noun, and the
    stages in table order with the PARA home each one lives in."""
    lines = list(live_lines(read_lines(Path(vault) / "CLAUDE.md")))
    out = []
    for i, (_, text) in enumerate(lines):
        m = HEADING_RE.match(text)
        if not m or not m.group(2).lower().endswith("lifecycle"):
            continue
        stages = lifecycle_stages(lines[i + 1:], len(m.group(1)))
        if stages:
            out.append({"heading": m.group(2), "noun": lifecycle_noun(m.group(2)),
                        "stages": stages})
    return out


def lifecycle_noun(heading):
    """The heading's first word, where it has one before the word lifecycle."""
    words = heading.split()
    return words[0].lower() if len(words) > 1 else None


def lifecycle_stages(rest, level):
    """The stages of the first table under a lifecycle heading that declares a Stage column
    and a PARA home column. Another table above it is somebody else's."""
    header, stages = None, []
    for _, text in rest:
        m = HEADING_RE.match(text)
        if m and len(m.group(1)) <= level:
            break
        stripped = text.strip()
        if not stripped.startswith("|"):
            if header:
                break
            continue
        cells = table_cells(stripped)
        if header is None:
            keys = [CELL_MARKS_RE.sub("", c).strip() for c in cells]
            if keys[0].lower() == "stage" and any(k.lower() == "para home" for k in keys):
                header = keys
            continue
        if not is_separator_row(cells):
            stages += stage_entries(header, cells)
    return stages


def stage_entries(header, cells):
    """One entry per name a Stage cell declares, all of them sharing the row's home."""
    row = dict(zip(header, cells + [""] * (len(header) - len(cells))))
    home_key = next(k for k in header if k.lower() == "para home")
    home, is_row = parse_home(row[home_key])
    columns = {k: v for k, v in row.items() if k.lower() not in ("stage", "para home")}
    names = re.sub(r"[*_]", "", row[header[0]]).split(":", 1)[0]
    return [{"name": name.strip(), "home": home, "terminal": home.startswith("archive/"),
             "row": is_row, "columns": dict(columns)}
            for name in names.split(",") if name.strip()]


def parse_home(cell):
    """A PARA home cell as (path, is a row home). The `(row)` suffix is the declaration."""
    text = CELL_MARKS_RE.sub("", cell).strip()
    is_row = text.lower().endswith("(row)")
    return (text[:-len("(row)")].strip() if is_row else text), is_row


# --- what a vault pulls from --------------------------------------------------------------

TRIAGE_HEADING_RE = re.compile(r"triage sources", re.IGNORECASE)
SCRIPT_SUFFIXES = (".py", ".js", ".mjs", ".ps1", ".sh")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BACKTICK_SPAN_RE = re.compile(r"`([^`]+)`")


def _md_cell(text):
    """A table cell with its backticks and `**` stripped and whitespace collapsed: the
    plain text a caller reads a field as, not what a rewriter would have to find on disk."""
    return re.sub(r"\s+", " ", CELL_MARKS_RE.sub("", text)).strip()


def _first_email(text):
    m = EMAIL_RE.search(text)
    return m.group(0) if m else None


def _triage_columns(header):
    """Source/type/endpoint/relevant column index in a Triage sources header row, by name
    where the row names a column (case-insensitive substring), else by the position the
    convention itself declares. A vault that translates only one column heading (a
    "Pertinent quand" in place of "Relevant when") still gets the other three by name."""
    hints = ("source", "type", "endpoint", "relevant")
    found = {}
    for hint in hints:
        for i, cell in enumerate(header):
            if hint in cell.lower():
                found[hint] = i
                break
    for i, hint in enumerate(hints):
        found.setdefault(hint, i)
    return found


def _normalize_connector(text):
    """A connector name folded to the one spelling every dispatcher reads: two vaults spell
    the Gmail connector two different ways, and a literal dispatch on the raw text misses
    one of them."""
    text = text.strip()
    lowered = text.lower()
    if "gmail" in lowered and "claude" in lowered:
        return "claude_ai_Gmail"
    if "google-workspace" in lowered:
        return "google-workspace"
    return text


def _triage_kind(type_text):
    """(kind, connector name) from a Triage sources Type cell, already markdown-stripped."""
    lowered = type_text.lower()
    for kind in ("sync-script", "fetch-script", "drive"):
        if lowered.startswith(kind):
            return kind, None
    if lowered.startswith("connector"):
        after = type_text.split(":", 1)[1].strip() if ":" in type_text else ""
        return "connector", _normalize_connector(after)
    return "unknown", None


def _triage_path(endpoint_raw):
    """A sync/fetch-script row's script path: the first backticked span whose first
    whitespace-separated token names a script file, taking that token only, else the first
    bare token in the cell that does. None where nothing qualifies."""
    for span in BACKTICK_SPAN_RE.findall(endpoint_raw):
        token = span.split()[0] if span.split() else ""
        if token.lower().endswith(SCRIPT_SUFFIXES):
            return token
    bare = BACKTICK_SPAN_RE.sub(" ", endpoint_raw).replace("*", " ")
    for token in bare.split():
        if token.lower().endswith(SCRIPT_SUFFIXES):
            return token
    return None


def _triage_drive_id(endpoint_raw):
    """A drive row's id: the first backticked span in the endpoint, else its first word."""
    m = BACKTICK_SPAN_RE.search(endpoint_raw)
    if m:
        return m.group(1).strip()
    words = _md_cell(endpoint_raw).split()
    return words[0] if words else None


def _triage_row(header, cells, lineno):
    cols = _triage_columns(header)

    def cell(name):
        idx = cols.get(name)
        return cells[idx] if idx is not None and idx < len(cells) else ""

    type_raw, endpoint_raw = cell("type"), cell("endpoint")
    type_text, endpoint_text = _md_cell(type_raw), _md_cell(endpoint_raw)
    kind, connector = _triage_kind(type_text)
    path = _triage_path(endpoint_raw) if kind in ("sync-script", "fetch-script") else None
    return {
        "line": lineno, "source": cell("source").strip(), "type": type_text, "kind": kind,
        "connector": connector, "endpoint": endpoint_text, "path": path,
        "mailbox": _first_email(endpoint_text),
        "drive_id": _triage_drive_id(endpoint_raw) if kind == "drive" else None,
        "relevant_when": cell("relevant").strip(),
    }


def triage_sources(vault):
    """The `## Triage sources` block of a vault's CLAUDE.md, machine-read: one row per
    mailbox, script or drive lookup the vault declares, so `/para-triage` and `/para-ingest`
    answer the same question about it from one reading rather than two. `declared` says
    whether the section exists at all, so a vault with none is not reported the same as a
    vault whose table merely holds no rows. A table inside a fenced block is a sample, not a
    declaration, and is skipped the way `live_lines` skips it everywhere else.
    """
    path = Path(vault) / "CLAUDE.md"
    if not path.is_file():
        return {"declared": False, "rows": []}
    lines = list(live_lines(read_lines(path)))
    start = None
    for i, (_, text) in enumerate(lines):
        m = HEADING_RE.match(text)
        if m and len(m.group(1)) == 2 and TRIAGE_HEADING_RE.fullmatch(m.group(2)):
            start = i + 1
            break
    if start is None:
        return {"declared": False, "rows": []}
    header, rows = None, []
    for lineno, text in lines[start:]:
        m = HEADING_RE.match(text)
        if m and len(m.group(1)) == 2:
            break
        stripped = text.strip()
        if not stripped.startswith("|"):
            header = None
            continue
        cells = table_cells(stripped)
        if header is None:
            header = [CELL_MARKS_RE.sub("", c).strip() for c in cells]
            continue
        if is_separator_row(cells):
            continue
        rows.append(_triage_row(header, cells, lineno))
    return {"declared": True, "rows": rows}


# --- vault hygiene ------------------------------------------------------------------------

FROZEN_MARKER_RE = re.compile(r"frozen record|third-party verbatim|kept as generated", re.IGNORECASE)


def misplaced_checkboxes(vault):
    """Open checkboxes where the vault forbids them, per bucket, worst file first.

    A file is a frozen record - and left alone - by either of two independent triggers in
    its first fifteen live lines before the first checkbox: a blockquote (unchanged from
    before), or plain prose naming itself one of "frozen record", "third-party verbatim" or
    "kept as generated", case-insensitively, with no blockquote required. Either is enough
    on its own; a file with an unrelated blockquote and no marker text is still exempt, and
    a file with the marker text and no blockquote is exempt too.
    """
    vault = Path(vault)
    out = {}
    for parent in ("archive", "resources"):
        base = vault / parent
        rows = []
        if base.is_dir():
            for path in sorted(base.rglob("*.md")):
                lines = read_lines(path)
                open_lines = [n for n, text in live_lines(lines) if TASK_RE.match(text)]
                if not open_lines:
                    continue
                first = open_lines[0]
                header = [text for n, text in live_lines(lines[:15]) if n < first]
                frozen = any(text.lstrip().startswith(">") for text in header) or \
                    any(FROZEN_MARKER_RE.search(text) for text in header)
                if frozen:
                    continue
                rows.append({"file": path.relative_to(vault).as_posix(),
                             "open": len(open_lines)})
        out[parent] = sorted(rows, key=lambda r: -r["open"])
    return out


def over_grown_briefs(vault, cap=BRIEF_LINE_CAP, limit=3):
    """Briefs past the line cap, longest first."""
    vault = Path(vault)
    rows = []
    for pattern in ("projects/*/brief.md", "areas/*/brief.md",
                    "projects/*/README.md", "areas/*/README.md"):
        for path in sorted(vault.glob(pattern)):
            count = len(read_lines(path))
            if count > cap:
                rows.append({"file": path.relative_to(vault).as_posix(), "lines": count})
    return sorted(rows, key=lambda r: -r["lines"])[:limit]


def triage_items(vault):
    """The direct file children of triage/. A `.gitkeep` is not an item, and a PDF and its
    extracted markdown twin are one."""
    base = Path(vault) / "triage"
    if not base.is_dir():
        return []
    files = [p for p in sorted(base.iterdir()) if p.is_file() and p.name != ".gitkeep"]
    pdfs = {p.stem for p in files if p.suffix.lower() == ".pdf"}
    return [p.name for p in files if not (p.suffix.lower() == ".md" and p.stem in pdfs)]


# --- links ---------------------------------------------------------------------------------

LINK_OPEN_RE = re.compile(r"\]\(")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
LINK_ROOTS = ("projects", "areas", "resources", "triage")
NOT_VAULT_CONTENT = (".git", ".claude/skills")


def abspath(path):
    """One absolute, normalised form for a path, without asking the filesystem. Two names
    for one file compare equal only once both are written this way."""
    return Path(os.path.normpath(Path(path).absolute()))


def same_place(path):
    """A form two spellings of one folder share, for comparing places: absolute, with
    symlinks and Windows short names resolved as far as the path exists, then case-folded
    where the platform ignores case. It asks the filesystem, unlike `abspath`, so it is for
    matching only; what gets reported stays the path as written."""
    return os.path.normcase(os.path.realpath(abspath(path)))


def rel_posix(vault, path):
    """A path as the vault names it: relative to the root, forward slashes. A path outside
    the vault keeps its absolute form, since no vault-relative name would be honest."""
    try:
        return abspath(path).relative_to(abspath(vault)).as_posix()
    except ValueError:
        return abspath(path).as_posix()


def is_under(path, base):
    """Whether a path is the folder itself or something inside it."""
    path, base = abspath(path), abspath(base)
    return path == base or base in path.parents


def link_spans(text):
    """(target start, target end, opening bracket) for each `[label](target)`.

    The target ends at the `)` balancing its opening `(`, never at the first one, so a
    filename carrying parentheses survives.
    """
    out = []
    for m in LINK_OPEN_RE.finditer(text):
        start = m.end()
        depth, j = 1, start
        while j < len(text) and depth:
            depth += (text[j] == "(") - (text[j] == ")")
            j += 1
        if not depth:
            out.append((start, j - 1, opening_bracket(text, m.start())))
    return out


def opening_bracket(text, close_at):
    """The `[` opening the label that closes at `close_at`, or None where there is none."""
    depth = 0
    for i in range(close_at, -1, -1):
        if text[i] == "]":
            depth += 1
        elif text[i] == "[":
            depth -= 1
            if not depth:
                return i
    return None


def extract_links(text):
    """(line number, target, target as written) for every link into the vault.

    The `#fragment` is dropped and the rest percent-decoded, so a target linked with `%20`
    resolves. What is not a path into the vault never comes back: a target carrying a scheme
    (`http:`, `mailto:`, `file:`, a drive letter) and one holding a `<placeholder>`, which is
    a template quoted in prose. The target as written comes back too, because it is what a
    rewriter has to find in the file and what says how the path was encoded: a `<...>`
    target keeps its brackets there, and a trailing `"title"` is not part of it.
    """
    out = []
    for start, end, _ in link_spans(text):
        raw = LINK_TITLE_RE.sub("", text[start:end].strip())
        target = raw
        if raw.startswith("<") and raw.endswith(">") and ("/" in raw or "." in raw):
            target = raw[1:-1]
        href = unquote(target.split("#", 1)[0]).strip()
        if not href or SCHEME_RE.match(href) or "<" in href:
            continue
        out.append((text.count("\n", 0, start) + 1, href, raw))
    return out


def resolve_link(from_file, href):
    """The absolute path a relative href names, read from the linking file's own folder.

    Never from the vault root: `../brief.md` names a different file in every folder it could
    sit in, which is what a link rewritten by depth difference gets wrong.
    """
    return abspath(Path(from_file).parent / href)


def link_files(vault, roots):
    """Every markdown file a link scan covers: the named roots, plus the root-level files,
    which sit in no bucket and link out as much as any of them."""
    vault = Path(vault)
    found = sorted(vault.glob("*.md"))
    for root in roots:
        base = vault / root
        if base.is_dir():
            found += sorted(base.rglob("*.md"))
    return found


def dangling_links(vault, roots=LINK_ROOTS):
    """Every link in the vault's live buckets whose target does not exist.

    archive/ is out of the default scan: a historical mention inside a closed record points
    at what was true then, and a caller that wants it passes its own roots.
    """
    vault = Path(vault)
    out = []
    for path in link_files(vault, roots):
        for line, href, _ in extract_links(strip_code(read_text(path))):
            target = resolve_link(path, href)
            if not target.exists():
                out.append({"file": rel_posix(vault, path), "line": line, "href": href,
                            "resolved": rel_posix(vault, target)})
    return out


def reference_shape(text, start, end):
    """Which of the four ways a path can be written this mention is: the target of a link,
    the display text of one, a path quoted in backticks, or plain prose."""
    for open_at, close_at, label_at in link_spans(text):
        if open_at <= start and end <= close_at:
            return "link_target"
        if label_at is not None and label_at < start and end <= open_at - 2:
            return "link_text"
    if blank_spans(text)[start:end] != text[start:end]:
        return "backtick"
    return "prose"


def first_mention(text, name, parent=None):
    """Where the first mention of `name` starts in `text`, or -1. Any substring without
    `parent`; with it, only the whole name, sitting under `parent` where written as a path."""
    if parent is None:
        return text.find(name)

    def continues(c, also=""):
        return bool(c) and (c.isalnum() or c in "-_" + also)

    at = text.find(name)
    while at >= 0:
        before = text[at - 1] if at else ""
        whole = not continues(before, ".") and not continues(text[at + len(name):][:1])
        if whole and before in ("/", "\\"):
            folder = re.split(r"[/\\]", text[:at - 1])[-1]
            whole = folder.endswith(parent) and \
                not continues(folder[:len(folder) - len(parent)][-1:], ".")
        if whole:
            return at
        at = text.find(name, at + 1)
    return -1


def inbound_references(vault, name, exclude=NOT_VAULT_CONTENT, parent=None):
    """Every live line in the vault naming `name`, with the shape it is written in.

    A reference is anywhere the path is written, not only a `](...)` target: a link's display
    text and a path quoted in backticks assert it too, and only the target fails on a click,
    so the rest go on naming a path that no longer exists. The line is percent-decoded before
    the match, so `%20` does not hide a name with a space in it, and the shape is the shape of
    its first mention. `in_sources` marks a file under a sources/ folder, where a third-party
    document is quoted verbatim.

    Given `parent`, the folder `name` sits directly in, a mention is the whole name, never the
    tail of a longer one (`notes.md` is not named by `meeting-notes.md`), and one written as a
    path must sit under that folder, so `triage/README.md` is not named by
    `projects/p/README.md`. Without it any substring counts, for a caller that sorts the
    loose hits itself.
    """
    vault = Path(vault)
    out = []
    for path in sorted(vault.rglob("*.md")):
        rel = rel_posix(vault, path)
        if any(rel == e or rel.startswith(e + "/") for e in exclude):
            continue
        in_sources = "sources" in Path(rel).parts[:-1]
        for lineno, text in live_lines(read_lines(path)):
            decoded = unquote(text)
            at = first_mention(decoded, name, parent)
            if at < 0:
                continue
            out.append({"file": rel, "line": lineno, "text": text,
                        "shape": reference_shape(decoded, at, at + len(name)),
                        "in_sources": in_sources})
    return out


# --- moving a folder -------------------------------------------------------------------------

def match_encoding(raw, new):
    """The new href written the way the old one was: its `#fragment` kept, and its spaces
    percent-encoded where the original encoded them, or where the original had no space to
    say and a bare space would end the target (never inside `<...>`, where one is legal)."""
    bracketed = raw.startswith("<") and raw.endswith(">")
    if bracketed:
        raw = raw[1:-1]
    _, sep, frag = raw.partition("#")
    encode = "%20" in raw or (not bracketed and " " not in raw)
    out = (new.replace(" ", "%20") if encode else new) + sep + frag
    return f"<{out}>" if bracketed else out


def link_rewrite(vault, path, line, href, raw, target, moved_target, from_dir):
    """One link's row in a move plan: where it is written, what it resolves to today, and the
    href naming the file it must then name, from `from_dir`, the folder it will be read in.

    Both halves move in a move plan, never together: the linking file travels and its target
    stands, or the target travels and the linking file stands.
    """
    new = Path(os.path.relpath(moved_target, from_dir)).as_posix()
    return {"file": rel_posix(vault, path), "line": line, "href": href, "raw": raw,
            "resolved": rel_posix(vault, target), "new_href": match_encoding(raw, new)}


def move_plan(vault, src, dst):
    """What moving a folder has to rewrite, in two lists, before anything moves.

    `inside`: a link in the moved folder whose target lies outside it, resolved from the old
    location and rewritten relative to the new one, never shifted by the difference in depth.
    A link to something that travels with the folder keeps its href and is not listed.
    `inbound`: a link from the rest of the vault into the folder, with the href it must
    become. A mention that is not a link has no href to rewrite and stays with
    `inbound_references`. Nothing here is applied.
    """
    vault = Path(vault)
    src_dir, dst_dir = vault_path(vault, src), vault_path(vault, dst)
    inside = []
    for path in sorted(src_dir.rglob("*.md")):
        moved = dst_dir / path.relative_to(src_dir)
        for line, href, raw in extract_links(strip_code(read_text(path))):
            target = resolve_link(path, href)
            if not is_under(target, src_dir):
                inside.append(link_rewrite(vault, path, line, href, raw, target, target,
                                           moved.parent))
    inbound = []
    for hit in inbound_references(vault, src_dir.name):
        path = vault / hit["file"]
        if is_under(path, src_dir):
            continue
        for _, href, raw in extract_links(strip_code(hit["text"])):
            target = resolve_link(path, href)
            if is_under(target, src_dir):
                inbound.append(link_rewrite(vault, path, hit["line"], href, raw, target,
                                            dst_dir / target.relative_to(src_dir), path.parent))
    return {"inside": inside, "inbound": inbound}


def vault_path(vault, path):
    """A folder named either way: absolute, or relative to the vault root."""
    path = Path(path)
    return abspath(path if path.is_absolute() else Path(vault) / path)


# --- file contents ---------------------------------------------------------------------------

MIN_HASH_BYTES = 200        # below this, a stub matches every other stub and says nothing
SKIP_HASH_FOLDERS = ("photos", "plans", "styles", "public")  # media, and a build's own assets


def hashes(vault, min_bytes=MIN_HASH_BYTES, skip=SKIP_HASH_FOLDERS, sizes=None, within=None):
    """Every file in the vault at or above `min_bytes` by content digest, as {path: md5},
    with what a skipped folder holds named under `skipped` rather than dropped: a scan that
    passed over a folder in silence reports a vault it never read as clean. `.git` is not
    vault content and is never walked.

    `sizes` (a set of byte counts) and `within` (a tuple of folder names) each narrow which
    files are even opened, for a vault synced by a streaming cloud client where reading a
    file's bytes downloads it: a file `stat` alone rules out is not listed at all, not even
    under `skipped`. Both default to `None`, which keeps today's answer exactly.
    """
    vault = Path(vault)
    lowered = {s.lower() for s in skip}
    digests, skipped = {}, []
    for path in sorted(vault.rglob("*")):
        if not path.is_file():
            continue
        rel = rel_posix(vault, path)
        parts = Path(rel).parts
        if ".git" in parts:
            continue
        if within is not None and not any(p in within for p in parts[:-1]):
            continue
        try:
            size = path.stat().st_size
            if size < min_bytes:
                continue
            if sizes is not None and size not in sizes:
                continue
            if any(p.lower() in lowered for p in parts[:-1]):
                skipped.append(rel)
                continue
            digests[rel] = hashlib.md5(path.read_bytes()).hexdigest()
        except OSError:
            continue
    return {"files": digests, "skipped": skipped}


def duplicates(digests):
    """Every group of two or more paths holding the same bytes, each group sorted. Content,
    never a matching name or size, which are not evidence of anything."""
    digests = digests["files"] if isinstance(digests.get("files"), dict) else digests
    groups = {}
    for path, digest in digests.items():
        groups.setdefault(digest, []).append(path)
    return sorted((sorted(g) for g in groups.values() if len(g) > 1), key=lambda g: g[0])


UTF8_BOM = b"\xef\xbb\xbf"
TRAILING_BLANKS_RE = re.compile(rb"[ \t]+$", re.MULTILINE)


def normalised(data, trailing_ws=False):
    """A file's bytes in the form two copies of it are compared by: a leading UTF-8
    byte-order mark dropped, and CRLF and a lone CR each read as LF. A `str` is taken as
    its UTF-8 bytes.

    A copy that passed through a Windows editor or a sync client comes back with CRLF or a
    BOM and nothing else changed, and a raw compare reports that as drift from its master:
    every "is this copy identical to its master" question is asked of this form, never of
    the bytes on disk.

    `trailing_ws` also drops the spaces and tabs ending each line, and the blank lines
    ending the file, a missing final newline included: two copies equal under it differ in
    whitespace alone. That is evidence a copy is equivalent to a version, never that it is
    identical to one, so it is off unless asked for. `snapshot()` stays on the raw bytes,
    since a write-time check has to see every byte a writer changed.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    elif not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"normalised() takes bytes or str, not {type(data).__name__}")
    data = bytes(data)
    if data.startswith(UTF8_BOM):
        data = data[len(UTF8_BOM):]
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if trailing_ws:
        data = TRAILING_BLANKS_RE.sub(b"", data).rstrip(b"\n")
        data = data + b"\n" if data else b""
    return data


def snapshot(paths):
    """{path: digest} for each path as it stands, None where there is no file. A caller takes
    one before proposing an edit and checks it before writing, so a file that changed while
    the operator was reading the proposal is caught rather than overwritten."""
    out = {}
    for p in paths:
        try:
            out[str(Path(p))] = hashlib.sha1(Path(p).read_bytes()).hexdigest()
        except OSError:
            out[str(Path(p))] = None
    return out


def changed(before):
    """The paths of a snapshot whose contents no longer match it, one since deleted included."""
    now = snapshot(before)
    return sorted(p for p, digest in before.items() if now.get(p) != digest)


def arrived(before, folders):
    """The files directly in each folder that the snapshot does not hold: arrivals since it
    was taken, which no approval covered. A `.gitkeep` is not a file here, as in triage/."""
    known = set(before)
    out = []
    for folder in folders:
        try:
            children = sorted(Path(folder).iterdir())
        except OSError:
            continue
        out += [str(abspath(c)) for c in children
                if c.is_file() and c.name != ".gitkeep" and str(abspath(c)) not in known]
    return out


def scan_snapshot(data):
    """The snapshot a scan's output carries: its top-level `snapshot`, or the snapshots under
    its phase keys merged (`clean_scan.py` nests one per phase), or the document itself where
    it is a bare {path: digest} map. None where there is none, so a document without one is
    never read as a snapshot and reported as all changed."""
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("snapshot"), dict):
        return data["snapshot"]
    nested = [v["snapshot"] for v in data.values()
              if isinstance(v, dict) and isinstance(v.get("snapshot"), dict)]
    if nested:
        return {p: d for snap in nested for p, d in snap.items()}
    if data and all(isinstance(v, (str, type(None))) for v in data.values()):
        return data
    return None


def scan_snapshot_folders(data):
    """The folders a scan's snapshot holds every file of, from its `snapshot_folders`
    (top-level or under a phase key); empty where it names none."""
    if not isinstance(data, dict):
        return []
    found = [data] + [v for v in data.values() if isinstance(v, dict)]
    return [f for d in found if isinstance(d.get("snapshot_folders"), list)
            for f in d["snapshot_folders"]]


# --- what a vault was built from -------------------------------------------------------------

REVISION_PATTERN = r"\d{4}\.\d{2}(?:\.\d{2})?"
TEMPLATE_MARKER_RE = re.compile(r"<!--\s*para-os-template:\s*(" + REVISION_PATTERN + r")\s*-->")
INTEGRATION_MARKER_RE = re.compile(r"para-os-integration:\s*([A-Za-z0-9._-]+)\s+("
                                   + REVISION_PATTERN + r")")
CHANGELOG_HEADING_RE = re.compile(r"^##\s+(\d{4}\.\d{2}\.\d{2})\s*$")
RULE_RE = re.compile(r"^-{3,}$")
LEGACY_REVISIONS = {"2026.08": "2026.08.01"}
MARKED_SUFFIXES = (".py", ".js", ".mjs", ".ps1", ".sh")
MARKER_HEADER_LINES = 80


def template_marker(text, raw=False):
    """The template revision a document is stamped with, from its first marker comment.

    The one label that shipped before revisions carried a sequence reads as the revision it
    was renumbered to, so a vault carrying it is not migrated onto itself. `raw` returns the
    label as the comment writes it instead (`2026.08`, not `2026.08.01`): what a search of
    a template's history has to look for, since the renumbered form was never written into
    any file that carried the old one.
    """
    m = TEMPLATE_MARKER_RE.search(text)
    if not m:
        return None
    return m.group(1) if raw else LEGACY_REVISIONS.get(m.group(1), m.group(1))


def integration_markers(vault, exclude=NOT_VAULT_CONTENT):
    """Every installed integration script in the vault, as {file, name, revision}.

    The whole vault, never one folder: a delivery installs its pipeline where it needs it,
    and a folder-scoped scan reports those copies as absent rather than as stale.
    """
    vault = Path(vault)
    out = []
    for path in sorted(vault.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in MARKED_SUFFIXES:
            continue
        rel = rel_posix(vault, path)
        if any(rel == e or rel.startswith(e + "/") for e in exclude):
            continue
        header = "\n".join(read_lines(path)[:MARKER_HEADER_LINES])
        m = INTEGRATION_MARKER_RE.search(header)
        if m:
            out.append({"file": rel, "name": m.group(1), "revision": m.group(2)})
    return out


def changelog_entries(text):
    """Each `## <revision>` entry of a changelog in the order written, as {revision, line,
    body}. The body is the entry itself, which is the procedure a migration runs; `line` is
    the 1-based line of its heading in `text`, so a report can point at the entry rather
    than quote it. A heading inside a fenced block is a sample, not an entry."""
    out, body = [], None
    for lineno, line in live_lines(split_lines(text)):
        m = CHANGELOG_HEADING_RE.match(line.strip())
        if m:
            body = []
            out.append({"revision": m.group(1), "line": lineno, "body": body})
        elif body is None:
            continue
        elif H2_RE.match(line):
            body = None
        else:
            body.append(line)
    for entry in out:
        lines = entry["body"]
        while lines and (not lines[-1].strip() or RULE_RE.match(lines[-1].strip())):
            lines.pop()
        entry["body"] = "\n".join(lines).strip()
    return out


def entries_between(entries, after, upto=None):
    """The entries a vault stamped `after` has not had yet, up to and including `upto`.
    Revisions compare as plain strings, which is what their padding is for."""
    return [e for e in entries
            if (after is None or e["revision"] > after)
            and (upto is None or e["revision"] <= upto)]


# --- a para-os clone, which a vault is measured against ------------------------------------
# Every reader here reads the commit a ref names, never the clone's checkout: a revision in
# flight lives in the working tree uncommitted, and a vault measured against it reads as
# behind a revision that never shipped. `worktree=True` is the one exception, asked for by
# name when a master about to be committed is the point: the files on disk in the clone,
# never its index. `ref` is then not read at all, since the caller has already settled that
# it names the checked-out branch.

BASE_TEMPLATE = "base/CLAUDE.md.template"
SKELETON_TEMPLATE = "skeleton/CLAUDE.md.template"   # under an addon's own folder
ADDONS_DIR = "addons"
OLDER_ADDON_DIRS = ("delivery", "flavors")          # where an addon lived before addons/


def _clone_rel(path):
    """A clone-relative path the way git names it: forward slashes, no `./`, no leading or
    trailing slash. `""` for the clone root."""
    text = str(path).replace("\\", "/").strip("/")
    text = str(PurePosixPath(text)) if text else ""
    return "" if text == "." else text


def _usable_ref(ref):
    """A ref git will read as a ref: a value opening on `-` would be read as an option."""
    return bool(ref) and not str(ref).startswith("-")


def _z_paths(out):
    """The paths of a `-z` listing, NUL-separated and never quoted, decoded as UTF-8."""
    return [p.decode("utf-8", errors="replace") for p in out.split(b"\0") if p]


def clone_ref(clone, ref):
    """The commit a ref names in a clone, as {ref, commit}: `ref` as given, `commit` its
    full hash. None where it names no commit (a typo, a branch never fetched) or `clone` is
    not a git repository. Peeled with `^{commit}`, so an annotated tag answers with the
    commit it tags, never the tag object's own hash.
    """
    if not _usable_ref(ref):
        return None
    out = git(clone, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
    commit = out.strip() if out else ""
    return {"ref": ref, "commit": commit} if commit else None


def clone_read(clone, ref, path, worktree=False):
    """One file's bytes as a clone holds it at a ref, or None where the ref holds no file
    at that path: absent, or a folder.

    Read with `git cat-file blob <ref>:<path>`, the same bytes `git show` prints for a file,
    but an error for a folder where `git show` prints a listing that would read back as the
    file's content. With `worktree`, the file on disk in the clone, unstaged edits included
    and never the index.
    """
    rel = _clone_rel(path)
    if not rel:
        return None
    if worktree:
        target = Path(clone) / rel
        try:
            return target.read_bytes() if target.is_file() else None
        except OSError:
            return None
    if not _usable_ref(ref):
        return None
    return git_bytes(clone, ["cat-file", "blob", f"{ref}:{rel}"])


def clone_files(clone, ref, prefix, worktree=False):
    """Every file a clone holds under `prefix` at a ref, as sorted clone-relative posix
    paths (`git ls-tree -r --name-only <ref> -- <prefix>`). A prefix naming one file answers
    with that file, and `""` with the whole tree. A prefix is a path, never a pattern, and
    matches whole segments: `addons/sales` never lists `addons/sales-extra/`.

    `[]` where nothing is there, None where git cannot answer at all (not a repository, a
    ref that names no commit), so a caller can tell an empty folder from a question never
    answered.

    With `worktree`, what the working tree holds: every tracked file still on disk, plus
    every untracked file the clone's own ignore rules do not exclude (`git ls-files
    --cached --others --exclude-standard`). An ignored file (a `__pycache__`, a live
    config) is part of no master, and a tracked file deleted on disk is not in the working
    tree whatever the index says.
    """
    rel = _clone_rel(prefix)
    spec = ["--", rel] if rel else []
    if worktree:
        out = git_bytes(clone, ["--literal-pathspecs", "ls-files", "-z", "--cached",
                                "--others", "--exclude-standard"] + spec)
    elif _usable_ref(ref):
        out = git_bytes(clone, ["--literal-pathspecs", "ls-tree", "-r", "--name-only", "-z",
                                ref] + spec)
    else:
        out = None
    if out is None:
        return None
    found = set()
    for path in _z_paths(out):
        if rel and path != rel and not path.startswith(rel + "/"):
            continue
        if worktree and not os.path.lexists(Path(clone) / path):
            continue
        found.add(path)
    return sorted(found)


def _clone_holds_folder(clone, ref, path, worktree):
    """Whether a folder exists in a clone at a ref: it holds a file there, since git tracks
    no empty folder. With `worktree`, `clone_files` lists something under it, so a folder
    left on disk holding only ignored files does not count."""
    if worktree:
        return bool(clone_files(clone, ref, path, worktree=True))
    if not _usable_ref(ref):
        return False
    out = git(clone, ["cat-file", "-t", f"{ref}:{path}"])
    return bool(out) and out.strip() == "tree"


def addon_root(clone, ref, name, worktree=False):
    """The clone-relative folder an addon (a delivery, a flavor or a module) lives in at a
    ref, or None where that ref holds none by that name.

    Three layouts have shipped, and a vault pinned to an older ref is measured against the
    layout that ref carried. Today every addon lives under `addons/<name>/`. Before that, a
    delivery lived under `delivery/<name>/` and a flavor under `flavors/<name>/`; and
    before that the read-only iPad delivery was itself a flavor, under
    `flavors/readonly-ipad/`. So a ref holding `addons/` answers from there alone, never
    from a folder that ref no longer carries, and a ref without it answers with the first
    of `delivery/<name>`, `flavors/<name>` that exists at it.
    """
    if not name or any(c in name for c in "/\\") or name in (".", ".."):
        return None
    if _clone_holds_folder(clone, ref, ADDONS_DIR, worktree):
        candidates = [f"{ADDONS_DIR}/{name}"]
    else:
        candidates = [f"{parent}/{name}" for parent in OLDER_ADDON_DIRS]
    return next((c for c in candidates if _clone_holds_folder(clone, ref, c, worktree)), None)


def _template_row(path, data, source, fallback):
    text = data.decode("utf-8", errors="replace") if data is not None else ""
    return {"path": path, "marker": template_marker(text),
            "raw_marker": template_marker(text, raw=True), "source": source,
            "fallback": fallback}


def master_template(clone, ref, decl, worktree=False):
    """The `CLAUDE.md` template a vault is measured against at a ref, as {path, marker,
    raw_marker, source, fallback}. `decl` is the vault's `declarations()`.

    A vault on a delivery, declared or detected, is measured against the delivery's
    `<addon_root>/skeleton/CLAUDE.md.template`, whichever layout the ref carries; every
    other vault against `base/CLAUDE.md.template`. A delivery with no skeleton template at
    the ref falls back to base, and `fallback` says so in one sentence an operator can read
    (None otherwise). `source` names which was read, "delivery" or "base", and is None
    where the ref holds neither. `marker` is the revision as `template_marker` reads it and
    `raw_marker` the label the comment writes, so a legacy label is told apart from the
    revision it became.

    A detected delivery counts here exactly as a declared one: a vault with `flip.ps1` at
    its root measured against base reads as behind, or ahead of, a template it was never
    built from.
    """
    delivery = (decl or {}).get("delivery")
    fallback = None
    if delivery:
        root = addon_root(clone, ref, delivery, worktree)
        if root:
            path = f"{root}/{SKELETON_TEMPLATE}"
            data = clone_read(clone, ref, path, worktree)
            if data is not None:
                return _template_row(path, data, "delivery", None)
        where = "in the clone's working tree" if worktree else f"at {ref}"
        fallback = (f"'{delivery}' names no skeleton {where}; "
                    f"compared against {BASE_TEMPLATE} instead")
    data = clone_read(clone, ref, BASE_TEMPLATE, worktree)
    return _template_row(BASE_TEMPLATE, data, "base" if data is not None else None, fallback)


# --- para-ingest's own run logs, staged-note names, and the seen-ledger watermark ---------
# What `/para-triage`'s per-vault seen-ledger and `/para-ingest`'s central one both need:
# reading the run logs a model writes (and so names its fields inconsistently between runs),
# recomputing a staged note's name from the thread id that produced it, and deciding whether
# a ledger entry still covers a thread's newest message. Two callers, one answer each.

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

    These logs are written by a model, not by code, so their field names drift between
    runs - this reads every spelling seen on this machine rather than one. A file that
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


# --- from the command line ------------------------------------------------------------------

def answer_for(args, root):
    if args.command == "resolve":
        return resolve_entity(root, args.name)
    if args.command == "lifecycles":
        return lifecycles(root)
    if args.command == "move-plan":
        return move_plan(root, args.src, args.dst)
    if args.command == "hashes":
        return hashes(root)
    if args.command == "registry":
        if args.name:
            return registry_holding(registry(), args.name, exclude=root)
        return registry()
    if args.command == "sources":
        return triage_sources(root)
    if args.kind == "inbound":
        return inbound_references(root, args.name)
    return dangling_links(root, tuple(args.roots)) if args.roots else dangling_links(root)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Answer one question about a vault, as JSON.")
    sub = ap.add_subparsers(dest="command", required=True)
    resolve = sub.add_parser("resolve", help="where one project or area lives")
    resolve.add_argument("name", help="the project or area to look for")
    declared = sub.add_parser("lifecycles", help="the lifecycles the vault declares")
    links = sub.add_parser("links", help="what points at what")
    kinds = links.add_subparsers(dest="kind", required=True)
    dangling = kinds.add_parser("dangling", help="links whose target does not exist")
    dangling.add_argument("--root", action="append", dest="roots", metavar="R",
                          help="a bucket to scan, repeatable (default: the live buckets)")
    inbound = kinds.add_parser("inbound", help="every line naming an entity or a file")
    inbound.add_argument("name", help="the folder or filename to look for")
    plan = sub.add_parser("move-plan", help="the links a folder move has to rewrite")
    plan.add_argument("src", help="the folder as it stands")
    plan.add_argument("dst", help="where it is going")
    digests = sub.add_parser("hashes", help="content digests, for finding duplicates")
    reg = sub.add_parser("registry", help="the machine's vault registry, or who else holds a name")
    reg.add_argument("name", nargs="?", help="an entity name to look for in every other vault")
    changed_cmd = sub.add_parser(
        "changed", help="which paths in a snapshot no longer match it, and which files "
                        "arrived in its snapshot_folders since (exit 1 if any)")
    changed_cmd.add_argument(
        "file", help="a JSON snapshot ({path: digest}), or scan output carrying a "
                     "'snapshot' key, top-level or under a phase key")
    sources = sub.add_parser("sources", help="the Triage sources block the vault declares")
    ingest_logs_cmd = sub.add_parser("ingest-logs", help="every /para-ingest run log, newest first")
    ingest_logs_cmd.add_argument("--paraos-home", dest="paraos_home", default=None,
                                 help="ingest cache root (default: $PARAOS_HOME or ~/.paraos)")
    for parser in (resolve, declared, dangling, inbound, plan, digests, reg, sources):
        parser.add_argument("--vault", default=".", help="vault root (default: .)")
    args = ap.parse_args(argv)

    # A Windows console defaults to a codepage that cannot encode what a vault writes.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if args.command == "changed":
        try:
            data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            ap.error(f"cannot read {args.file}: {err}")
        snap = scan_snapshot(data)
        if snap is None:
            ap.error(f"{args.file} holds no snapshot")
        diffs = {"changed": changed(snap), "arrived": arrived(snap, scan_snapshot_folders(data))}
        json.dump(diffs, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 1 if diffs["changed"] or diffs["arrived"] else 0

    if args.command == "ingest-logs":
        json.dump(ingest_logs(args.paraos_home), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    root = Path(args.vault)
    if not root.is_dir():
        ap.error(f"no such vault: {root}")
    json.dump(answer_for(args, root), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
