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
    py -3 paraos_vault.py notice-date <renewal> "<n> months" [--term "1 year"] [--today D]
    py -3 paraos_vault.py weekday-after <day> <weekday>

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "para-shared" / "scripts"))
    from paraos_vault import live_lines, open_tasks, resolve_entity

What lives here is what two skills would otherwise each answer their own way about a vault:
whether a folder is a vault root, what the machine's registry says about it and its neighbours,
where a checkbox may live, what counts as one, what a task marker means, which folder a name
resolves to, which names a contact card answers to, when a file was really last touched, what
a link points at and what a move would have to rewrite, whether two files hold the same bytes,
what a vault declares it is built from and the locale it declares, the numbers a vault's own
rules state, the last day to give notice on a renewing agreement, and the date a promised
weekday points at. A second implementation of any of those is a vault getting two answers to
one question, which is the failure this repo exists to prevent. Two siblings hold what is not
about the vault itself: `paraos_clone.py` reads the para-os clone a vault is measured against,
and `paraos_mail.py` reads mail threads, the notes they become and the ledgers that track them.

What does NOT live here: anything a single skill decides. Bucketing against a date,
ranking, thresholds a skill invents for its own report, and every word an operator reads
stay with the skill that owns them.
"""

import argparse
import calendar
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

# --- what a vault's own rules state -------------------------------------------------------
# One home for numbers that several skills quote. A skill that disagrees with one of these
# tells an operator their file is fine while another says it needs grooming.

OPEN_ITEM_CAP = 8           # open items one action file holds: past it, close or demote first
HEADLINE_CAP = 120          # characters in an action's headline: its bold lead, else the line
FALSELY_OVERDUE_DAYS = 30   # overdue by more than this reads as a date that was never real
DORMANT_ENTITY_DAYS = 180   # untouched this long: a retirement candidate
BRIEF_LINE_CAP = 500        # a brief past this is over-grown
STALE_FILE_DAYS = 60        # an action file with open items, untouched this long
STALE_UNDATED_DAYS = 30     # an open, undated item untouched this long: offered for demotion
WAITING_FLAG_DAYS = 14      # a wait on someone else this old asks: chase or drop?
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
LEADING_MARKERS_RE = re.compile(r"^(?:\s*(?:[🔺🔼🔽⏬]|[📅🛫⏳✅]️?\s*\d\S*))+")
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


PERIOD_RE = re.compile(r"^\s*(\d+)\s*(day|week|month|year)s?\s*$", re.IGNORECASE)


def add_months(day, months):
    """`day` moved by whole calendar months, back where `months` is negative, clamped to the
    last day of a shorter month: `2027-05-31` less three months is `2027-02-28`."""
    year, month = divmod(day.year * 12 + day.month - 1 + months, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def shift(day, period, times=1):
    """`day` moved by `times` of a period written `<n> days|weeks|months|years`, back where
    `times` is negative. ValueError on any other wording."""
    m = PERIOD_RE.match(str(period))
    if not m:
        raise ValueError(f"not a period: {period!r}; write <n> days, weeks, months or years")
    count, unit = int(m.group(1)) * times, m.group(2).lower()
    if unit in ("day", "week"):
        return day + timedelta(days=count * (7 if unit == "week" else 1))
    return add_months(day, count * (12 if unit == "year" else 1))


WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def weekday_index(name):
    """0 for Monday to 6 for Sunday, from an English day name, its first three letters or
    more, or an ISO number 1 to 7. ValueError on anything else: a day written in another
    language is the caller's to translate, never guessed here."""
    text = str(name).strip().lower()
    if text.isdigit() and 1 <= int(text) <= 7:
        return int(text) - 1
    for index, day in enumerate(WEEKDAYS):
        if len(text) >= 3 and day.startswith(text):
            return index
    raise ValueError(f"not a weekday: {name!r}; write an English day name or 1 to 7")


def weekday_after(day, weekday):
    """The first `weekday` (0 for Monday) strictly after `day`: the date a promise naming a
    weekday points at, so a Wednesday promised on a Wednesday is the one a week on."""
    return day + timedelta(days=(weekday - day.weekday() - 1) % 7 + 1)


def working_days(since, until):
    """Working days after `since`, up to and including `until`, counting Monday to Friday.
    Public holidays are not known here and count as working days. 0 where `until` is not
    later than `since`."""
    if until <= since:
        return 0
    weeks, rest = divmod((until - since).days, 7)
    return weeks * 5 + sum(1 for i in range(1, rest + 1)
                           if (since + timedelta(days=i)).weekday() < 5)


def notice_date(renewal, notice, term=None, today=None):
    """The last day to give notice on an agreement renewing on `renewal`: the renewal less
    the notice period. With `term`, how often it renews, a renewal whose notice day is
    behind today rolls forward whole terms, counted from `renewal` so a clamped month never
    drifts, to the first whose notice day is still ahead."""
    today = today or date.today()
    if term and shift(renewal, term) <= renewal:
        raise ValueError(f"a term moves the renewal forward: {term!r}")
    current, rolled = renewal, 0
    deadline = shift(current, notice, -1)
    while term and deadline < today:
        rolled += 1
        current = shift(renewal, term, rolled)
        deadline = shift(current, notice, -1)
    return {"renewal": iso(current), "notice": notice, "term": term,
            "notice_date": iso(deadline), "passed": deadline < today}


def parse_markers(body):
    """Every task marker on one task line, plus the text without them.

    A date-shaped marker still has to be a real date: `2026-13-45` matches the shape and
    names no day, so it comes back as no date with `malformed_date` set, never silently.
    Every date marker on the line is checked, so `⏳ tomorrow` is flagged even where a
    valid `📅` sits beside it. The text drops the markers trailing it and any written
    before it, so `🔺 Call Jan` reads as `Call Jan`.
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
        "text": MARKERS_RE.sub("", LEADING_MARKERS_RE.sub("", body)).strip(),
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

    def folded(path):
        return "/".join(norm(part) for part in str(path).strip().strip("/").split("/"))

    exact = [c for c in candidates if folded(c["path"]) == folded(query)] or \
        [c for c in candidates if c["key"] == key]
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

    A checkout or a sync writes many files in the same second, which leaves
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


ALIASES_RE = re.compile(r"^\*\*Aliases:\*\*\s*(.+)$", re.IGNORECASE)
ALSO_RE = re.compile(r"^Also:\s*(.+)$", re.IGNORECASE)


def contact_names(card):
    """A contact card's names: its H1, plus every alias a `**Aliases:**` or `Also:` line
    lists, split on commas and semicolons. One reading for every skill that looks a person
    up, so a card answers to the same names wherever it is asked."""
    lines = [t for _, t in live_lines(read_lines(card))]
    names = []
    for t in lines:
        m = H1_RE.match(t.strip())
        if m:
            names.append(m.group(1).strip())
            break
    for t in lines:
        m = ALIASES_RE.match(t.strip()) or ALSO_RE.match(t.strip())
        if m:
            names += [a.strip() for a in re.split(r"[,;]", m.group(1)) if a.strip()]
    return names


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

def _declared(value):
    """One declaration line's value as a name: markdown marks dropped, whitespace
    collapsed, None where nothing is left."""
    text = re.sub(r"\s+", " ", CELL_MARKS_RE.sub("", value or "")).strip()
    return text or None


def declarations(vault):
    """What a vault says it is built from, read from the lines under its `CLAUDE.md` title
    (`header_fields`): {type, flavor, modules}. `modules` is the `**Modules:**` line split
    on its commas in the order written, `[]` where the vault declares none.

    One reading for every skill, because the declaration picks the addons a vault is
    measured against: two skills reading it two ways give one vault two verdicts.
    """
    fields = header_fields(Path(vault) / "CLAUDE.md")
    modules = [m.strip() for m in (_declared(field_ci(fields, "Modules")) or "").split(",")]
    return {"type": _declared(field_ci(fields, "Type")),
            "flavor": _declared(field_ci(fields, "Flavor")),
            "modules": [m for m in modules if m]}


LOCALE_LINE_RE = re.compile(r"^\*\*Locale:?\*\*:?\s*(.*)$", re.IGNORECASE)
LOCALE_FIELD_RE = re.compile(
    r"^(country|currency|financial year ends|numbers|dates|time zone)\b\s*:?\s*(.*)$",
    re.IGNORECASE)
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december")


def locale(vault):
    """The `**Locale:**` line a vault's `CLAUDE.md` declares (the template puts it under
    `## Language`): {country, currency, year_end, numbers, dates, time_zone}, each the text
    written after its label, `·`-separated. A field the line leaves out, or that still holds
    a `{{placeholder}}`, is None; a vault with no such line answers {}. The prose after the
    line's last field is not part of it.

    Text only: `year_end_of` reads the year end, and the rest is read by the model.
    """
    keys = {"country": "country", "currency": "currency", "financial year ends": "year_end",
            "numbers": "numbers", "dates": "dates", "time zone": "time_zone"}
    for _, text in live_lines(read_lines(Path(vault) / "CLAUDE.md")):
        m = LOCALE_LINE_RE.match(text.strip())
        if not m:
            continue
        out = dict.fromkeys(keys.values())
        for segment in m.group(1).split("·"):
            f = LOCALE_FIELD_RE.match(segment.strip())
            if not f:
                continue
            value = re.split(r"\.\s", f.group(2), maxsplit=1)[0].strip().rstrip(".").strip()
            if value and "{{" not in value:
                out[keys[f.group(1).lower()]] = value
        return out
    return {}


def _month(word):
    word = word.lower().rstrip(".")
    hits = [n for n, name in enumerate(MONTHS, 1) if len(word) >= 3 and name.startswith(word)]
    return hits[0] if len(hits) == 1 else None


def year_end_of(text):
    """A financial year's last day as (month, day), from `30 June`, `June 30`, `30th of Jun`
    or `06-30` (`--06-30`), month names in English as structural files are. None where the
    text is none of those or names no day of any year; 29 February is accepted."""
    t = " ".join((text or "").split()).rstrip(".")
    numeric = re.fullmatch(r"-{0,2}(\d{1,2})-(\d{1,2})", t)
    day_first = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([A-Za-z]+\.?)", t)
    month_first = re.fullmatch(r"([A-Za-z]+\.?)\s+(\d{1,2})(?:st|nd|rd|th)?", t)
    if numeric:
        month, day = int(numeric.group(1)), int(numeric.group(2))
    elif day_first:
        month, day = _month(day_first.group(2)), int(day_first.group(1))
    elif month_first:
        month, day = _month(month_first.group(1)), int(month_first.group(2))
    else:
        return None
    if not month or not 1 <= month <= 12 or not 1 <= day <= calendar.monthrange(2000, month)[1]:
        return None
    return month, day


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
CADENCE_HINT_RE = re.compile(r"🔁️?\s*(every(?:\s+\d+)?\s+[A-Za-z]+)")
SENT_HINT_RE = re.compile(r"📤️?\s*sent\b", re.IGNORECASE)


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
        after = type_text.split(":", 1)[1] if ":" in type_text else ""
        after = SENT_HINT_RE.sub("", CADENCE_HINT_RE.sub("", after)).strip()
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
    cadence = next((m.group(1) for m in map(CADENCE_HINT_RE.search, cells) if m), None)
    return {
        "line": lineno, "source": cell("source").strip(), "type": type_text, "kind": kind,
        "connector": connector, "endpoint": endpoint_text, "path": path,
        "mailbox": _first_email(endpoint_text),
        "drive_id": _triage_drive_id(endpoint_raw) if kind == "drive" else None,
        "relevant_when": cell("relevant").strip(), "cadence": cadence,
        "sent": bool(SENT_HINT_RE.search(type_text)),
    }


def triage_sources(vault):
    """The `## Triage sources` block of a vault's CLAUDE.md, machine-read: one row per
    mailbox, script or drive lookup the vault declares, so `/para-triage` and `/para-ingest`
    answer the same question about it from one reading rather than two. `declared` says
    whether the section exists at all, so a vault with none is not reported the same as a
    vault whose table merely holds no rows. A table inside a fenced block is a sample, not a
    declaration, and is skipped the way `live_lines` skips it everywhere else. `cadence` is
    a row's `🔁 every <period>` hint, in any cell: how often the source should deliver.
    `sent` is whether its Type cell carries `📤 sent`, asking for the sent-mail pass of
    connectors.md; neither hint changes the row's `kind` or `connector`.
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


def checkbox_rows(text, raw=False):
    """{bucket: cells} from the `Where a checkbox may live` table, the bucket cell stripped of
    backticks and bold (`areas/network/`), the rest lowercased and stripped the same way.
    With `raw`, {bucket: the row as written}."""
    rows, inside = {}, False
    for _, line in live_lines(split_lines(text)):
        heading = HEADING_RE.match(line)
        if heading:
            inside = heading.group(2).strip().lower() == "where a checkbox may live"
            continue
        if not inside or not line.lstrip().startswith("|"):
            continue
        cells = [CELL_MARKS_RE.sub("", c).strip() for c in table_cells(line)]
        if len(cells) > 1 and not is_separator_row(cells) and cells[0].lower() != "bucket":
            rows[cells[0]] = line.strip() if raw else [c.lower() for c in cells[1:]]
    return rows


def contact_card_level(vault):
    """What a contact card may hold: `yes`, `relationship only` or `never`, from the
    `areas/network/` row of the vault's checkbox table. With no row, a `## Who writes this
    vault` roster implies `never` and anything else is `yes`."""
    text = read_text(Path(vault) / "CLAUDE.md") or ""
    rows = checkbox_rows(text)
    cells = rows.get("areas/network/") or rows.get("areas/network")
    if cells:
        return next((lv for lv in ("never", "relationship only") if cells[0].startswith(lv)), "yes")
    return "never" if re.search(r"^## Who writes this vault\s*$", text, re.MULTILINE) else "yes"


def _frozen(lines, first):
    header = [text for n, text in live_lines(lines[:15]) if n < first]
    return any(text.lstrip().startswith(">") for text in header) or \
        any(FROZEN_MARKER_RE.search(text) for text in header)


def misplaced_checkboxes(vault, with_closed=False):
    """Open checkboxes where the vault forbids them, per bucket, worst file first: `archive`,
    `resources`, `areas/network` where the vault's contact-card level is `never`, and any
    other folder its checkbox table declares at `never` (work tracked somewhere else).
    `with_closed` adds `closed`, the ticked checkboxes on those cards, which `never` forbids
    too.

    A file is a frozen record - and left alone - by either of two independent triggers in
    its first fifteen live lines before the first checkbox: a blockquote (unchanged from
    before), or plain prose naming itself one of "frozen record", "third-party verbatim" or
    "kept as generated", case-insensitively, with no blockquote required. Either is enough
    on its own; a file with an unrelated blockquote and no marker text is still exempt, and
    a file with the marker text and no blockquote is exempt too.
    """
    vault = Path(vault)
    out, closed = {}, {}
    cards = contact_card_level(vault) == "never"
    declared = [k.strip("/") for k, cells in
                checkbox_rows(read_text(vault / "CLAUDE.md") or "").items()
                if cells[0].startswith("never") and "," not in k and k.endswith("/")
                and k.strip("/") not in ("archive", "resources", "areas/network")]
    for parent in ("archive", "resources") + (("areas/network",) if cards else ()) + \
            tuple(declared):
        base = vault / parent
        rows, ticked = [], []
        if base.is_dir():
            paths = base.glob("*.md") if parent == "areas/network" else base.rglob("*.md")
            for path in sorted(paths):
                if parent == "areas/network" and path.name.lower() == "readme.md":
                    continue
                lines = read_lines(path)
                open_lines = [n for n, text in live_lines(lines) if TASK_RE.match(text)]
                done = [n for n, text in live_lines(lines) if CLOSED_TASK_RE.match(text)] \
                    if parent == "areas/network" else []
                if not (open_lines or done) or _frozen(lines, min(open_lines + done)):
                    continue
                rel = path.relative_to(vault).as_posix()
                if open_lines:
                    rows.append({"file": rel, "open": len(open_lines)})
                if done:
                    ticked.append({"file": rel, "closed": len(done)})
        out[parent] = sorted(rows, key=lambda r: -r["open"])
        if parent == "areas/network":
            closed[parent] = sorted(ticked, key=lambda r: -r["closed"])
    if with_closed:
        out["closed"] = closed
    return out


def other_checkbox_paths(vault):
    """Every `.md` under `projects/` and `areas/` that is not an action file or a contact
    file (action_files() already covers both) and carries at least one open checkbox: the
    boxes no brief counts, in a log, a plan or a meeting note."""
    vault = Path(vault)
    action_set = set(action_files(vault))
    out = []
    for bucket in ("projects", "areas"):
        base = vault / bucket
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if path in action_set or path.name == "actions.md":
                continue
            if open_tasks(path):
                out.append(path)
    return out


def stray_checkboxes(vault):
    """`other_checkbox_paths()` less the frozen records, as `{file, open}`, worst first."""
    vault = Path(vault)
    rows = []
    for path in other_checkbox_paths(vault):
        lines = read_lines(path)
        opens = [n for n, text in live_lines(lines) if TASK_RE.match(text)]
        if opens and not _frozen(lines, opens[0]):
            rows.append({"file": path.relative_to(vault).as_posix(), "open": len(opens)})
    return sorted(rows, key=lambda r: -r["open"])


BOLD_LEAD_RE = re.compile(r"^\*\*(.+?)\*\*")


WAITING_ON_RE = re.compile(r"^\**\s*waiting on\b\**\s*(.+)$", re.IGNORECASE)


def waiting_on(text):
    """`{person, what, since}` for an item owed by someone else, written `Waiting on
    <person>: <what> (since YYYY-MM-DD)`, else None. The person is a link's label where the
    line links a card; `since` is None where the line names no date."""
    m = WAITING_ON_RE.match(text.strip())
    if not m:
        return None
    rest = m.group(1)
    who, _, what = rest.partition(":")
    label = re.match(r"^\s*\[([^\]]+)\]", who)
    since = SINCE_RE.search(rest)
    what = re.sub(r"\(\s*since\s+\d{4}-\d{2}-\d{2}\s*\)", "", what).strip(" .")
    return {"person": (label.group(1) if label else who).strip(" *"), "what": what or None,
            "since": since.group(1) if since else None}


def cap_count(tasks):
    """The open items a file's cap counts: every one but a wait on someone else."""
    return sum(1 for t in tasks if not waiting_on(t["text"]))


def headline(text):
    """An action's headline: its bold lead where it opens on one, else the whole text."""
    m = BOLD_LEAD_RE.match(text.strip())
    return m.group(1).strip() if m else text.strip()


def entity_of(vault, path):
    """The vault-relative entity a file belongs to: `projects/<x>`, `areas/<x>`, or the
    contact file itself under `areas/network/`. None for anything else."""
    parts = Path(path).resolve().relative_to(Path(vault).resolve()).parts
    if len(parts) >= 3 and parts[:2] == ("areas", "network"):
        return "/".join(parts[:3])
    if len(parts) >= 3 and parts[0] in ("projects", "areas"):
        return "/".join(parts[:2])
    return None


def backlog_bullets(path):
    """The top-level bullets under a `## Backlog` heading, `{line, text}` each."""
    out, inside = [], False
    for n, line in live_lines(read_lines(path)):
        heading = HEADING_RE.match(line)
        if heading:
            inside = heading.group(2).strip().lower() == "backlog"
            continue
        if inside and re.match(r"^[-*] (?!\[[ xX]\])", line):
            out.append({"line": n, "text": line[2:].strip()})
    return out


def open_items(vault, files):
    """What an end-of-work reconcile asks about: for each entity the `files` belong to, its
    open checkboxes and its `## Backlog` bullets, in its action file or its contact file."""
    vault = Path(vault)
    out = {}
    for f in files:
        try:
            entity = entity_of(vault, f)
        except ValueError:
            continue
        if not entity or entity in out:
            continue
        home = vault / entity
        doc = home if home.is_file() else home / "actions.md"
        if not doc.is_file():
            continue
        rel = doc.relative_to(vault).as_posix()
        out[entity] = {"file": rel,
                       "open": [{"line": t["line"], "text": t["text"], "due": t["due"],
                                 "recurring": t["recurring"]} for t in open_tasks(doc)],
                       "backlog": backlog_bullets(doc)}
    return [dict(entity=k, **v) for k, v in sorted(out.items())]


CADENCE_RE = re.compile(r"every\s+(?:(\d+)\s+)?(day|week|month|year)s?\b(.*)", re.IGNORECASE)


def next_occurrence(line, today):
    """A recurring task ticked today: `{closed, next}`, the line closed with `✅ <today>` and
    its successor reopened on the next due date. The next date is one cadence on from the
    line's `📅` (from today for `when done`, or a line with no `📅`). ValueError where the
    line carries no cadence this can count: every <n> days, weeks, months or years."""
    m = TASK_RE.match(line.strip()) or CLOSED_TASK_RE.match(line.strip())
    if not m:
        raise ValueError("not a task line")
    body = m.group(1)
    markers = parse_markers(body)
    found = CADENCE_RE.match(markers["recurring"] or "")
    if not found:
        raise ValueError(f"no countable cadence: {markers['recurring']!r}")
    period = f"{found.group(1) or 1} {found.group(2).lower()}s"
    due = parse_date(markers["due"])
    base = today if "when done" in found.group(3).lower() or not due else due
    following = shift(base, period)
    body = DONE_RE.sub("", body).rstrip()
    successor = DUE_RE.sub(f"📅 {iso(following)}", body) if due else f"{body} 📅 {iso(following)}"
    return {"closed": f"- [x] {body} ✅ {iso(today)}", "next": f"- [ ] {successor}",
            "due": iso(following)}


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

    The `?query` and `#fragment` are dropped and the rest percent-decoded, so a target linked
    with `%20` resolves and a query-only link (`?tab=t.0`) names no file. What is not a path
    into the vault never comes back: a target carrying a scheme (`http:`, `mailto:`, `file:`,
    a drive letter) and one holding a `<placeholder>`, which is a template quoted in prose.
    The target as written comes back too, because it is what a rewriter has to find in the
    file and what says how the path was encoded: a `<...>` target keeps its brackets there,
    and a trailing `"title"` is not part of it.
    """
    out = []
    for start, end, _ in link_spans(text):
        raw = LINK_TITLE_RE.sub("", text[start:end].strip())
        target = raw
        if raw.startswith("<") and raw.endswith(">") and ("/" in raw or "." in raw):
            target = raw[1:-1]
        href = unquote(re.split(r"[?#]", target, maxsplit=1)[0]).strip()
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


def link_target_exists(target):
    """Whether a link's target exists. A path the OS cannot even stat (an unreachable UNC
    share on Windows raises OSError) names nothing, so it reads as absent."""
    try:
        return Path(target).exists()
    except OSError:
        return False


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
            if not link_target_exists(target):
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
    """The new href written the way the old one was: its `?query#fragment` kept, and its spaces
    percent-encoded where the original encoded them, or where the original had no space to
    say and a bare space would end the target (never inside `<...>`, where one is legal)."""
    bracketed = raw.startswith("<") and raw.endswith(">")
    if bracketed:
        raw = raw[1:-1]
    suffix = raw[len(re.split(r"[?#]", raw, maxsplit=1)[0]):]
    encode = "%20" in raw or (not bracketed and " " not in raw)
    out = (new.replace(" ", "%20") if encode else new) + suffix
    return f"<{out}>" if bracketed else out


def link_rewrite(vault, path, line, href, raw, target, moved_target, from_dir):
    """One link's row in a move plan: where it is written, what it resolves to today, and the
    href naming the file it must then name, from `from_dir`, the folder it will be read in.

    Both halves move in a move plan, never together: the linking file travels and its target
    stands, or the target travels and the linking file stands.
    """
    new = Path(os.path.relpath(moved_target, from_dir)).as_posix()
    if href.endswith("/"):
        new += "/"  # a folder link stays one
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

    The whole vault, never one folder: a script installed outside `resources/scripts/`
    would otherwise read as absent rather than as stale.
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
    notice = sub.add_parser("notice-date", help="the last day to give notice on a renewing "
                                                "agreement")
    notice.add_argument("renewal", help="the renewal date, YYYY-MM-DD")
    notice.add_argument("notice", help="the notice period: <n> days, weeks, months or years")
    notice.add_argument("--term", help="how often it renews, written the same way: a renewal "
                                       "whose notice day has passed rolls forward to the next")
    notice.add_argument("--today", help="YYYY-MM-DD (default: the system clock)")
    items = sub.add_parser("open-items", help="the open items of the entities some files "
                                              "belong to, for an end-of-work reconcile")
    items.add_argument("files", nargs="*", help="vault-relative files (default: every file "
                                                "git reports changed)")
    recur = sub.add_parser("next-occurrence", help="a recurring task ticked: the closed line "
                                                   "and its successor")
    recur.add_argument("line", help="the task line as written")
    recur.add_argument("--today", help="YYYY-MM-DD (default: the system clock)")
    promised = sub.add_parser("weekday-after", help="the date a promise naming a weekday "
                                                    "points at: the first one after a day")
    promised.add_argument("day", help="the day the promise was made, YYYY-MM-DD")
    promised.add_argument("weekday", help="an English day name, or 1 (Monday) to 7")
    for parser in (resolve, declared, dangling, inbound, plan, digests, reg, sources, items):
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

    if args.command == "notice-date":
        renewal, today = parse_date(args.renewal), parse_date(args.today or iso(date.today()))
        if not renewal or not today:
            ap.error(f"dates are YYYY-MM-DD: {args.renewal!r}, {args.today!r}")
        try:
            answer = notice_date(renewal, args.notice, args.term, today)
        except ValueError as err:
            ap.error(str(err))
        json.dump(answer, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.command == "weekday-after":
        day = parse_date(args.day)
        if not day:
            ap.error(f"dates are YYYY-MM-DD: {args.day!r}")
        try:
            weekday = weekday_index(args.weekday)
        except ValueError as err:
            ap.error(str(err))
        answer = {"after": iso(day), "weekday": WEEKDAYS[weekday].capitalize(),
                  "date": iso(weekday_after(day, weekday))}
        json.dump(answer, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.command == "next-occurrence":
        today = parse_date(args.today or iso(date.today()))
        if not today:
            ap.error(f"dates are YYYY-MM-DD: {args.today!r}")
        try:
            answer = next_occurrence(args.line, today)
        except ValueError as err:
            ap.error(str(err))
        json.dump(answer, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    root = Path(args.vault)
    if not root.is_dir():
        ap.error(f"no such vault: {root}")
    if args.command == "open-items":
        files = [root / f for f in args.files] or sorted(git_modified(root))
        json.dump(open_items(root, files), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    json.dump(answer_for(args, root), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
