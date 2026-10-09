#!/usr/bin/env python3
"""Contract checks for the para-os repo. No dependencies; run it before shipping a revision.

    python3 tools/check.py            # report and exit non-zero on any failure
    python3 tools/check.py -v         # also list every check that passed
    python3 tools/check.py --no-vendor  # skip `claude plugin validate` (CI, or no CLI installed)

What it enforces, and why each one is machinery rather than prose:

  Integration markers   Every shipped integration script carries `para-os-integration: <name>
                        <revision>`, and the revision matches its row in integrations/README.md.
                        /para-upgrade finds an installed copy's master by that marker, so one that
                        disagrees with the table misleads every vault, silently. Config files are
                        named `<folder>.config.json`, never the machine-global secret's name.

  Template revisions    base/ and each example vault stamp a `<!-- para-os-template: -->`
                        marker that must equal the newest CHANGELOG entry, whose headings run
                        newest first: a stale template makes /para-upgrade report "nothing to do"
                        on a vault that needs migrating.

  Release notes         RELEASES.md lists the same revisions as CHANGELOG.md, in the same order.

  Changelog fragments   A fragment in `changelog.d/` the fold cannot parse fails in the pull
                        request that wrote it, not at the release; so does a CHANGELOG.md entry
                        line that is not a Reaction or `Retired:` line.

  Word caps             A starting template, a finished vault CLAUDE.md and a SKILL.md spine each
                        have a word cap: all three load every session, and a line cap passes a
                        short file that holds a long one.

  Dashes                CLAUDE.md makes em and en dashes a hard rule for shipped prose.

  Dates                 No ISO date, month or quarter with its year in a document's prose or a
                        script's comments and docstrings. A rule states what is true, not when
                        someone learned it. examples/ is set at a frozen date and is not scanned.

  Never-ship terms      Every file git would ship is scanned for the terms in
                        `$PARAOS_HOME/never-ship.txt` (default `~/.paraos/`): one per line, matched
                        case-insensitively as a whole word. The list lives outside the repo because
                        the terms are the private data it guards. No list skips the check and says
                        so on every run.

  Example skill copies  An example vault runs base's skills from an untracked copy that nothing
                        else notices falling behind. No copy is fine; one that differs fails.

  Skill contract        Every skill master (base, each add-on, multi-vault) keeps its frontmatter
                        (name matching its folder, description, allowed-tools naming a pattern per
                        shell command and never a bare `Bash` or `PowerShell`, argument-hint
                        offering `--test`), a link to para-shared/test-run.md, a `## Strict rules`
                        block, and references that resolve both ways.

  Installed links       Every relative link in a shipped skill's markdown, outside code, resolves
                        where the skills are installed, all side by side in one folder.

  Script launchers      A `python3 ` command in a skill's markdown states `py -3` on its own line
                        or the line above: on Windows `python3` is often a Store stub.

  Rules contract        Every `.claude/rules/*.md` carries a non-empty `paths:` frontmatter list,
                        and it and its CLAUDE.md point at each other, both ways.

  Vendor validator      `claude plugin validate` over the skills folders: whatever the tool
                        currently requires of a SKILL.md, which moves release to release.
                        `--no-vendor` skips it and says so.

  Test suites           Every skill script has its suite at `tools/tests/test_<script>.py`; an
                        integration's suite and an add-on pipeline's sit beside the script. All
                        run from here. A suite whose runtime is missing FAILS rather than skips.

Deliberately NOT checked: anything requiring judgement (privacy beyond a known term, bloat,
whether a rule earns its words). Those are review, not a script.
"""
import io
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tokenize
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # repo root; this file lives in tools/
REVISION = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
SCRIPT_SUFFIXES = {".py", ".js", ".mjs", ".ps1", ".sh"}

failures = []
passes = []
skips = []


def ok(msg):
    passes.append(msg)


def skip(msg):
    skips.append(msg)


def bad(msg):
    failures.append(msg)


def rel(p):
    return p.relative_to(ROOT).as_posix()


def listed(hits, limit=8):
    return ", ".join(hits[:limit]) + (f" (+{len(hits) - limit} more)" if len(hits) > limit else "")


def console_safe(s):
    """Drop what a Windows console cannot encode: the vendor validator reports with glyphs
    that kill the run on a cp1252 console, and the summary with it."""
    return s.encode("ascii", "replace").decode("ascii")


def run_captured(cmd, timeout):
    """Run a command from ROOT, stdout and stderr combined into one string."""
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, f"{r.stdout or ''}\n{r.stderr or ''}".strip()


def tail(text, n=15, transform=str):
    return "\n".join(f"        {transform(ln)}" for ln in text.splitlines()[-n:])


# The line each runner gives a failing test: node's TAP `not ok`, unittest's FAIL and ERROR.
FAILED_TEST = re.compile(r"^\s*not ok \d+|^(?:FAIL|ERROR): ")


def failure_report(text, transform=str):
    """A failed suite's output: the line naming each failing test, with the location and error
    TAP gives it, then the tail. The tail alone is counts and coverage, and names no test."""
    named, block = [], None  # block: the indent of the TAP key whose value is being copied
    for ln in text.splitlines():
        indent, s = len(ln) - len(ln.lstrip()), ln.strip()
        if block is not None and indent > block:
            named.append(f"  {ln[block:].rstrip()}")
            continue
        block = None
        if FAILED_TEST.match(ln):
            named.append(s)
        elif named and s.startswith(("location:", "error:")):
            named.append(f"  {s}")
            block = indent
    return "\n".join([f"        {transform(ln)}" for ln in named] + [tail(text, transform=transform)])


def is_test_file(p):
    return p.name.startswith("test_") or ".test." in p.name


# --- integrations ----------------------------------------------------------------------

def integration_dirs():
    return sorted(d for d in (ROOT / "integrations").iterdir() if d.is_dir())


def available_table():
    """{folder name: version} from the Available table in integrations/README.md."""
    text = (ROOT / "integrations" / "README.md").read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*\[`([^`/]+)/`\]\([^)]+\)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def check_config_naming(d, scripts):
    """One name for a vault config, across every integration: `<folder>.config.json`.

    `<folder>` because /para-upgrade resolves an installed copy by the integration name in its
    marker; `.config.json` because the bare `<name>.json` is the machine-global secret, and two
    files sharing one name across opposite trust zones is how a credential ends up in a folder
    that syncs (base/resources/scripts/README.md).
    """
    want = f"{d.name}.config.json"
    referenced = {m for p in scripts
                  for m in re.findall(r"[A-Za-z0-9_.-]+\.config\.json",
                                      p.read_text(encoding="utf-8", errors="ignore"))}
    for wrong in sorted(referenced - {want}):
        bad(f"integrations/{d.name}/ reads a vault config named `{wrong}`; the convention is "
            f"`{want}` (named for the integration, never for the script or the secret)")
    for tmpl in d.glob("*.config.json.template"):
        if tmpl.name != f"{want}.template":
            bad(f"{rel(tmpl)}: template should be `{want}.template`")


def check_integrations():
    table = available_table()
    if not table:
        bad("integrations/README.md: could not parse any row from the Available table")
        return
    folders = integration_dirs()

    for extra in sorted(set(table) - {d.name for d in folders}):
        bad(f"integrations/README.md lists `{extra}/` but no such folder exists")
    for missing in sorted({d.name for d in folders} - set(table)):
        bad(f"integrations/{missing}/ has no row in the Available table")

    for d in folders:
        scripts = [p for p in sorted(d.iterdir())
                   if p.suffix in SCRIPT_SUFFIXES and not is_test_file(p)]
        if not (d / "README.md").exists():
            bad(f"integrations/{d.name}/ has no README.md")
        if not scripts:
            bad(f"integrations/{d.name}/ ships no script")
            continue
        check_config_naming(d, scripts)

        revisions = {}
        for p in scripts:
            head = "\n".join(p.read_text(encoding="utf-8", errors="ignore").splitlines()[:10])
            m = re.search(r"para-os-integration:\s*(\S+)\s+(\S+)", head)
            if not m:
                bad(f"{rel(p)}: no `para-os-integration:` marker in the first 10 lines")
                continue
            name, revision = m.group(1), m.group(2)
            if name != d.name:
                bad(f"{rel(p)}: marker says integration `{name}`, folder is `{d.name}`")
            if not REVISION.match(revision):
                bad(f"{rel(p)}: revision `{revision}` is not YYYY.MM.NN")
            revisions[p] = revision

        distinct = set(revisions.values())
        if len(distinct) > 1:
            listing = ", ".join(f"{p.name}={v}" for p, v in sorted(revisions.items()))
            bad(f"integrations/{d.name}/: scripts disagree on the revision ({listing}). "
                f"The version is per integration, not per file.")
        elif distinct:
            got = distinct.pop()
            want = table.get(d.name)
            if want and got != want:
                bad(f"integrations/{d.name}/: scripts say {got}, Available table says {want}")
            else:
                ok(f"integrations/{d.name}/ at {got}, {len(revisions)} script(s) stamped")


# --- revisions and changelog -----------------------------------------------------------

def revision_headings(name):
    text = (ROOT / name).read_text(encoding="utf-8")
    return re.findall(r"^##\s+(\d{4}\.\d{2}\.\d{2})\s*$", text, re.M)


def template_files():
    files = [ROOT / "base" / "CLAUDE.md.template"]
    files += sorted(p / "CLAUDE.md" for p in (ROOT / "examples").iterdir()
                    if (p / "CLAUDE.md").exists())
    return files


def check_template_revisions():
    revisions = revision_headings("CHANGELOG.md")
    if not revisions:
        bad("CHANGELOG.md: no `## YYYY.MM.NN` revision headings found")
        return
    if revisions != sorted(set(revisions), reverse=True):
        bad(f"CHANGELOG.md: revisions are not unique and newest-first ({', '.join(revisions)})")

    for f in template_files():
        m = re.search(r"<!--\s*para-os-template:\s*(\S+)\s*-->",
                      f.read_text(encoding="utf-8", errors="ignore"))
        if not m:
            bad(f"{rel(f)}: no `<!-- para-os-template: -->` marker")
        elif m.group(1) != revisions[0]:
            bad(f"{rel(f)}: stamped {m.group(1)}, newest changelog revision is {revisions[0]}")
        else:
            ok(f"{rel(f)} at {revisions[0]}")


def check_release_notes():
    notes, revisions = revision_headings("RELEASES.md"), revision_headings("CHANGELOG.md")
    if notes == revisions:
        ok(f"RELEASES.md lists the {len(notes)} CHANGELOG revision(s), in order")
        return
    for missing in [r for r in revisions if r not in notes]:
        bad(f"RELEASES.md has no `## {missing}` note; CHANGELOG.md has that revision")
    for extra in [r for r in notes if r not in revisions]:
        bad(f"RELEASES.md has `## {extra}`, which CHANGELOG.md does not")
    if set(notes) == set(revisions):
        bad("RELEASES.md lists the CHANGELOG revisions in a different order; keep both newest first")


MAINTAINER_SKILLS = ROOT / ".claude" / "skills"   # for working on this repo; never shipped


def check_fragments():
    """The parser is the fold's own, so what passes here is what /release can fold, and
    CHANGELOG.md's entries are held to the same lines."""
    sys.path.insert(0, str(MAINTAINER_SKILLS / "release" / "scripts"))
    from fold_changelog import changelog_problems, fragment_paths, parse_fragment
    problems = changelog_problems((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    for problem in problems:
        bad(f"CHANGELOG.md: {problem}")
    if not problems:
        ok("CHANGELOG.md: every entry line is a Reaction or `Retired:` line")
    for p in sorted(fragment_paths(ROOT)):
        _, problems = parse_fragment(p.read_text(encoding="utf-8"))
        for problem in problems:
            bad(f"{rel(p)}: {problem}")
        if not problems:
            ok(f"{rel(p)} parses")


# --- word caps -------------------------------------------------------------------------

# Each a little above the largest real file of its kind, so the cap catches regrowth.
TEMPLATE_MAX_WORDS = 1650   # base's CLAUDE.md.template: a vault starts here and adds its own
FINISHED_MAX_WORDS = 2250   # a populated vault's own CLAUDE.md, which the example is
SPINE_MAX_WORDS = 2300      # a SKILL.md: its body loads on every invoke


def check_template_size():
    for f in template_files():
        cap = TEMPLATE_MAX_WORDS if f.suffix == ".template" else FINISHED_MAX_WORDS
        n = len(f.read_text(encoding="utf-8", errors="ignore").split())
        if n > cap:
            bad(f"{rel(f)}: {n} words, cap is {cap}. Cut procedure and rationale, not rules.")
        else:
            ok(f"{rel(f)} at {n} words (cap {cap})")


# --- style -----------------------------------------------------------------------------

DASHES = ("\u2014", "\u2013")  # em, en: escaped so this file passes its own check.
FENCE = re.compile(r"^\s*(?:```|~~~)")
CODE_SPAN = re.compile(r"`[^`]*`")
WALK_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache"}
PROSE_SUFFIXES = {".md", ".template", ".sections", ".py", ".js", ".mjs", ".json", ".ps1"}


def prose_files():
    """Every file this script may read, with the noise pruned at descent: `.git` alone holds
    roughly eight times as many files as the repo."""
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in WALK_SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix in PROSE_SUFFIXES:
                yield p


def check_dashes():
    """The rule is about *prose*, so code is out of scope: a regex that matches an en dash in
    someone's calendar entry is parsing data, not writing prose."""
    hits = []
    for p in prose_files():
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        in_fence = False
        for n, line in enumerate(text.splitlines(), 1):
            if FENCE.match(line):
                in_fence = not in_fence
            elif not in_fence and any(d in CODE_SPAN.sub("", line) for d in DASHES):
                hits.append(f"{rel(p)}:{n}")
    if hits:
        bad(f"em/en dash in shipped text: {listed(hits)}")
    else:
        ok("no em/en dashes in shipped text")


def shippable_names(check):
    """Every file git would ship (tracked, plus untracked and not ignored), or None once the
    failure is reported under `check`: a scan that could not list its files has not passed."""
    # -z and stdout alone: git quotes a non-ASCII path otherwise, and that file would drop
    # out of the scan without a word.
    try:
        r = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           cwd=ROOT, capture_output=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        bad(f"{check}: could not list shippable files with git ({e})")
        return None
    if r.returncode != 0:
        bad(f"{check}: git ls-files exited {r.returncode}")
        return None
    return list(filter(None, r.stdout.decode("utf-8").split("\0")))


# --- dates in prose ----------------------------------------------------------------------

# Case-insensitive, except a lowercase `may`, which is a verb far more often than a month.
_MONTH = (r"(?:May|MAY|(?i:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|june?|july?"
          r"|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?))")
_YEAR = r"(?:19|20)\d{2}"
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
# An ISO-style date or month (`2026-08`, `2026/08/14`), a month with its year (`Aug. 2026`,
# `14th August 2026`, `Aug 14th, 2026`), or a quarter or half (`Q3 2026`, `H1 2026`). A
# revision label (2026.09.03) is none of them. The examples sit in code spans so this file
# passes its own check.
DATE = re.compile(rf"(?<![\w./-]){_YEAR}([-/])(?:0[1-9]|1[0-2])(?:\1[0-3]\d)?(?![\w/])"
                  rf"|\b(?:{_DAY}\s+(?:of\s+)?)?{_MONTH}\.?\s+(?:{_DAY},?\s+)?{_YEAR}\b"
                  rf"|\b(?:Q[1-4]|H[12])\s+{_YEAR}\b")
DATE_DOC_SUFFIXES = {".md", ".template", ".sections"}
DATE_SCRIPT_SUFFIXES = {".py", ".js", ".mjs", ".ps1"}


def py_prose(text):
    """{line: text} of a Python file's comments and docstrings, from its tokens. A string
    standing alone as a statement is a docstring; any other string literal is data."""
    out, statement = {}, []
    skip = {tokenize.NL, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING}
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            out[tok.start[0]] = out.get(tok.start[0], "") + tok.string
        elif tok.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
            if statement and all(t.type == tokenize.STRING for t in statement):
                for t in statement:
                    for i, part in enumerate(t.string.splitlines(), t.start[0]):
                        out[i] = out.get(i, "") + part
            statement = []
        elif tok.type not in skip:
            statement.append(tok)
    return out


def script_comments(text, line, block, escapes):
    """{line: text} of the comments in a JS or PowerShell file, skipping string literals.
    `escapes` maps each quote character to its escape character; `'` and `"` end at a newline
    in JS, where only a template literal spans lines."""
    out, state, i, n = {}, None, 0, 1
    while i < len(text):
        c = text[i]
        if c == "\n":
            n += 1
            if state == "line" or (line == "//" and state in ("'", '"')):
                state = None
        elif state is None:
            if text.startswith(block[0], i) or text.startswith(line, i):
                state = "block" if text.startswith(block[0], i) else "line"
                i += len(block[0] if state == "block" else line)
                continue
            if c in escapes:
                state = c
        elif state == "block" and text.startswith(block[1], i):
            state, i = None, i + len(block[1])
            continue
        elif state in ("line", "block"):
            out[n] = out.get(n, "") + c
        elif c == escapes[state] and text[i + 1:i + 2] not in ("", "\n"):
            i += 1
        elif c == state:
            state = None
        i += 1
    return out


def prose_lines(suffix, text):
    """(line number, text) for each line of prose in a shipped file: in a document, outside
    fences and code spans; in a script, comments and docstrings only, since its string
    literals are test data."""
    if suffix == ".py":
        found = py_prose(text)
    elif suffix == ".ps1":
        found = script_comments(text, "#", ("<#", "#>"), {"'": None, '"': "`"})
    elif suffix in DATE_SCRIPT_SUFFIXES:
        found = script_comments(text, "//", ("/*", "*/"), {q: "\\" for q in "'\"`"})
    else:
        found, in_fence = {}, False
        for n, ln in enumerate(text.splitlines(), 1):
            if FENCE.match(ln):
                in_fence = not in_fence
            elif not in_fence:
                found[n] = ln
    for n in sorted(found):
        yield n, CODE_SPAN.sub("", found[n])


def check_dates():
    names = shippable_names("dates in prose")
    if names is None:
        return
    hits = []
    for name in names:
        suffix = Path(name).suffix
        if name.startswith("examples/") or suffix not in DATE_DOC_SUFFIXES | DATE_SCRIPT_SUFFIXES:
            continue
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue   # binary, or staged as deleted
        for n, prose in prose_lines(suffix, text):
            m = DATE.search(prose)
            if m:
                hits.append(f"{name}:{n} ({m.group(0)})")
    if hits:
        bad(f"date in shipped prose: {listed(hits)}. State what is true; git records when.")
    else:
        ok("no dates in shipped prose")


# --- never-ship terms -------------------------------------------------------------------

def never_ship_list():
    return Path(os.environ.get("PARAOS_HOME") or Path.home() / ".paraos") / "never-ship.txt"


def check_never_ship():
    path = never_ship_list()
    if not path.is_file():
        skip(f"never-ship terms: no list at {path}, nothing scanned")
        return
    terms = [t.strip() for t in path.read_text(encoding="utf-8").splitlines()]
    terms = [t for t in terms if t and not t.startswith("#")]
    if not terms:
        bad(f"never-ship terms: {path} lists no terms")
        return
    word = "|".join(re.escape(t) for t in terms)
    pattern = re.compile(rf"(?<![A-Za-z0-9])(?:{word})(?![A-Za-z0-9])", re.I)
    names = shippable_names("never-ship terms")
    if names is None:
        return
    hits = []
    for name in names:
        try:
            data = (ROOT / name).read_bytes()
        except OSError:
            continue   # staged as deleted
        if b"\0" in data:
            continue   # binary
        for n, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
            m = pattern.search(line)
            if m:
                hits.append(f"{name}:{n} ({m.group(0)})")
    if hits:
        bad(f"never-ship term in shipped text: {listed(hits)}")
    else:
        ok(f"no never-ship terms in shipped text ({len(terms)} terms)")


# --- skill masters ---------------------------------------------------------------------

SKILLS_DIR = ROOT / "base" / ".claude" / "skills"
EXTRA_SKILL_DIRS = (ROOT / "multi-vault",)   # optional layers that ship a skill of their own
SKILL_FRONTMATTER = ("name", "description", "allowed-tools", "argument-hint")
ALLOWED_TOOL = re.compile(r"[\w-]+(?:\([^)]*\))?")   # `Read`, `Bash(git log *)`, an MCP tool name
DESCRIPTION_MAX_CHARS = 600
TEST_RUN_DOC = "para-shared/test-run.md"   # what `--test` means, stated once for every skill


def addon_skill_dirs():
    """Each add-on's skills folder, under .claude/ like base's. An add-on need not ship one."""
    return sorted(d for d in (ROOT / "addons").glob("*/.claude/skills") if d.is_dir())


def skill_dirs(parent):
    """The skill folders directly under `parent` - a folder holding a SKILL.md is a skill."""
    return sorted(d for d in parent.iterdir() if (d / "SKILL.md").exists())


def whole_shell_grants(allowed_tools):
    """The entries of an `allowed-tools` value that pre-approve every command of a shell: `Bash`
    or `PowerShell` bare, or with a pattern that is nothing but a wildcard (`Bash(*)`)."""
    return [t for t in ALLOWED_TOOL.findall(allowed_tools)
            if t.split("(")[0] in ("Bash", "PowerShell")
            and not t.partition("(")[2].rstrip(")").strip(" *:")]


def skill_script_dirs():
    """Each skill's scripts/ folder, wherever skills ship from, and the maintainer's own."""
    roots = [SKILLS_DIR, *addon_skill_dirs(), *EXTRA_SKILL_DIRS, MAINTAINER_SKILLS]
    return sorted(d for root in roots for d in root.glob("*/scripts") if d.is_dir())


def check_skills():
    if not (SKILLS_DIR / TEST_RUN_DOC).is_file():
        bad(f"base/.claude/skills/{TEST_RUN_DOC} is missing, and every skill's `--test` points at it")

    masters = skill_dirs(SKILLS_DIR)
    for extra in [*addon_skill_dirs(), *EXTRA_SKILL_DIRS]:
        masters += skill_dirs(extra)

    for d in masters:
        sk = d / "SKILL.md"
        text = sk.read_text(encoding="utf-8")
        words = len(text.split())
        before = len(failures)

        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m:
            bad(f"{rel(sk)}: no YAML frontmatter")
            continue
        fields = {k: v.strip() for k, v in re.findall(r"^([\w-]+):\s*(.*)$", m.group(1), re.M)}

        for key in SKILL_FRONTMATTER:
            if key not in fields:
                bad(f"{rel(sk)}: frontmatter is missing `{key}:`")

        shells = whole_shell_grants(fields.get("allowed-tools", ""))
        if shells:
            bad(f"{rel(sk)}: allowed-tools pre-approves a whole shell ({', '.join(shells)}). List "
                f"a pattern per command the skill runs, such as `Bash(git mv *)`.")

        name = fields.get("name")
        if name and name != d.name:
            bad(f"{rel(sk)}: frontmatter name `{name}` does not match folder `{d.name}`. "
                f"The frontmatter name is what the skill is invoked as.")

        desc = fields.get("description")
        if desc and len(desc) > DESCRIPTION_MAX_CHARS:
            bad(f"{rel(sk)}: description is {len(desc)} chars "
                f"(cap {DESCRIPTION_MAX_CHARS}). It sits in context every turn.")

        if words > SPINE_MAX_WORDS:
            bad(f"{rel(sk)}: {words} words (cap {SPINE_MAX_WORDS}). A SKILL.md is a loader "
                f"spine; per-step procedure belongs in references/.")

        if "--test" not in fields.get("argument-hint", ""):
            bad(f"{rel(sk)}: argument-hint does not offer `[--test]`, the test-run argument every "
                f"skill takes")
        if TEST_RUN_DOC not in text:
            bad(f"{rel(sk)}: never links {TEST_RUN_DOC}, so `--test` has no definition "
                f"this skill loads")

        if not re.search(r"^##\s+Strict rules\s*$", text, re.M):
            bad(f"{rel(sk)}: no `## Strict rules` section. A skill has to say what it must "
                f"never do, not only what it does.")

        refs = d / "references"
        on_disk = {p.name for p in refs.glob("*.md")}
        linked = set(re.findall(r"references/([A-Za-z0-9_.-]+\.md)", text))
        for orphan in sorted(on_disk - linked):
            bad(f"{rel(refs / orphan)}: on disk but never linked from SKILL.md, so no step "
                f"ever loads it")
        for dangling in sorted(linked - on_disk):
            bad(f"{rel(sk)}: links references/{dangling}, which does not exist")

        if len(failures) == before:
            ok(f"{rel(d)}/ contract holds ({words} words, {len(on_disk)} reference(s))")


# --- example skill copies ---------------------------------------------------------------

def check_example_skill_copies():
    """An example vault runs base's skills from an untracked copy (examples/README.md) that
    nothing else notices fall behind. No copy is fine; a copy must match base file for file,
    line endings aside."""
    def tree(root):
        return {p.relative_to(root).as_posix(): p.read_bytes().replace(b"\r\n", b"\n")
                for p in root.rglob("*")
                if p.is_file() and not WALK_SKIP_DIRS.intersection(p.relative_to(root).parts)}

    want = tree(SKILLS_DIR)
    for copy in sorted((ROOT / "examples").glob("*/.claude/skills")):
        have = tree(copy)
        diffs = (("differs:", sorted(n for n in want.keys() & have.keys() if want[n] != have[n])),
                 ("missing:", sorted(want.keys() - have.keys())),
                 ("not in base:", sorted(have.keys() - want.keys())))
        parts = [f"{label} {listed(names, 4)}" for label, names in diffs if names]
        if parts:
            bad(f"{rel(copy)}/ is not a copy of base/.claude/skills/ ({'; '.join(parts)}). "
                f"Replace it with a fresh copy of base/.claude/skills/.")
        else:
            ok(f"{rel(copy)}/ matches base/.claude/skills/ ({len(have)} files)")


# --- installed links -------------------------------------------------------------------

MD_LINK = re.compile(r"\]\(\s*<?([^)>\s]+)>?(?:\s+\"[^\"]*\")?\)")
URL_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:")


def installed_skill_folders():
    """What an install puts side by side in one skills folder, by the name it goes in under:
    base's skills and para-shared/, each add-on's skills, and the multi-vault skills."""
    folders = [d for d in SKILLS_DIR.iterdir() if d.is_dir()]
    for extra_skills in addon_skill_dirs():
        folders += [d for d in extra_skills.iterdir() if d.is_dir()]
    for extra in EXTRA_SKILL_DIRS:
        folders += skill_dirs(extra)
    return {d.name: d for d in folders if d.name not in WALK_SKIP_DIRS}


def check_installed_links():
    """A relative link in a shipped skill has to resolve where the skill is installed. From the
    repo, `../../../base/.claude/skills/para-shared/x.md` and `../../para-shared/x.md` both reach
    a file, but only the second exists in a vault, where every skill sits in one folder. Links
    inside code are examples of a vault's own links, not the skill's, so they are left alone."""
    folders = installed_skill_folders()
    count, before = 0, len(failures)
    for name, d in sorted(folders.items()):
        for f in sorted(d.rglob("*.md")):
            if WALK_SKIP_DIRS & set(f.relative_to(d).parts):
                continue
            fenced = False
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if FENCE.match(line):
                    fenced = not fenced
                    continue
                if fenced:
                    continue
                for target in MD_LINK.findall(CODE_SPAN.sub("", line)):
                    if target.startswith(("#", "/")) or URL_SCHEME.match(target):
                        continue
                    count += 1
                    # The path from the skills folder: a `..` past its top leaves the folder
                    # an install creates.
                    path = posixpath.normpath(posixpath.join(
                        name, *f.relative_to(d).parent.parts, target.split("#")[0]))
                    top, _, rest = path.partition("/")
                    if path.startswith("..") or top == "." or top not in folders:
                        reason = "leaves the skills folder"
                    elif not (folders[top] / rest).exists():
                        reason = "names no file"
                    else:
                        continue
                    bad(f"{rel(f)}:{n}: `{target}` {reason} once installed, where every skill "
                        f"sits beside para-shared/ in one folder")
    if len(failures) == before:
        ok(f"{count} relative link(s) in shipped skills resolve where they are installed")


# --- script launchers ------------------------------------------------------------------

PY3_COMMAND = re.compile(r"`python3 ")


def check_launchers():
    hits = []
    for root in [SKILLS_DIR, *addon_skill_dirs(), *EXTRA_SKILL_DIRS]:
        for p in sorted(root.rglob("*.md")):
            prev, in_fence = "", False
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if FENCE.match(line):
                    in_fence = not in_fence
                elif (line.lstrip().startswith("python3 ") if in_fence else PY3_COMMAND.search(line)) \
                        and "py -3" not in line and "py -3" not in prev:
                    hits.append(f"{rel(p)}:{n}")
                prev = line
    if hits:
        bad(f"`python3` command with no Windows form (`py -3`) on its line or the line above: "
            f"{', '.join(hits)}")
    else:
        ok("every skill's `python3` command states its Windows form")


# --- .claude/rules/ contract -----------------------------------------------------------

RULES_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
RULES_PATHS_LIST = re.compile(r"^paths:[ \t]*\n((?:^[ \t]*-[ \t]*\S.*\n?)+)", re.M)
RULES_POINTER = re.compile(r"\.claude/rules/([A-Za-z0-9_.-]+\.md)")


def vault_roots_with_rules():
    """Every CLAUDE.md, template or add-on sections file, paired with the `.claude/rules/` it
    points into. Walked rather than listed, so a second example that grows a rules/ folder is
    picked up with no edit here."""
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in WALK_SKIP_DIRS]
        here = Path(dirpath)
        for name in ("CLAUDE.md", "CLAUDE.md.template", "CLAUDE.md.sections"):
            if name in filenames and (here / ".claude" / "rules").is_dir():
                yield here / name, here / ".claude" / "rules"


def check_rules_contract():
    """A rule file and its vault's CLAUDE.md must agree, both ways, and the file itself must
    carry the frontmatter that makes it load at all. An orphaned rule file is as invisible as
    an unlinked reference doc, and a dangling pointer sends a reader to a file that is gone."""
    for claude_md, rules_dir in sorted(vault_roots_with_rules()):
        before = len(failures)
        claude_text = claude_md.read_text(encoding="utf-8", errors="ignore")
        on_disk = {p.name for p in rules_dir.glob("*.md")}
        linked = set(RULES_POINTER.findall(claude_text))

        for orphan in sorted(on_disk - linked):
            bad(f"{rel(rules_dir / orphan)}: on disk but not pointed at from {rel(claude_md)}, "
                f"so a skill that reads CLAUDE.md alone will never find it")
        for dangling in sorted(linked - on_disk):
            bad(f"{rel(claude_md)}: points at .claude/rules/{dangling}, which does not exist")

        for name in sorted(on_disk):
            f = rules_dir / name
            m = RULES_FRONTMATTER.match(f.read_text(encoding="utf-8", errors="ignore"))
            if not m:
                bad(f"{rel(f)}: no YAML frontmatter")
            elif not RULES_PATHS_LIST.search(m.group(1)):
                bad(f"{rel(f)}: frontmatter has no non-empty `paths:` list, so this rule "
                    f"never auto-loads for any session")

        if len(failures) == before:
            ok(f"{rel(claude_md)}: .claude/rules/ contract holds ({len(on_disk)} file(s))")


# --- vendor validator ------------------------------------------------------------------

def check_skill_validator():
    """Run `claude plugin validate` over each skills directory: a linter, not a distribution
    step, and the part of the contract a hand-written check cannot keep up with.

    Two things the tool does are corrected for here. It picks its mode from the path, so the
    run is only meaningful once the output says it validated components. And it exits 0 on
    warnings, so the exit code alone would be a check that passes and measures nothing.
    """
    if "--no-vendor" in sys.argv:
        skip("vendor skill validator: --no-vendor given, `claude plugin validate` not run. "
             "Run without it before shipping a revision.")
        return
    claude = shutil.which("claude")
    if not claude:
        bad("`claude` is not on PATH, so the vendor's skill validator could not run. A check "
            "that could not run has not passed.")
        return
    for skills_dir in [SKILLS_DIR] + addon_skill_dirs():
        validate_skills_dir(claude, skills_dir)


def validate_skills_dir(claude, skills_dir):
    try:
        returncode, out = run_captured([claude, "plugin", "validate", str(skills_dir)],
                                        timeout=120)
    except subprocess.TimeoutExpired:
        bad("claude plugin validate: timed out after 120s")
        return

    out_tail = tail(out, transform=console_safe)

    if "early access" in out.lower():
        bad(f"claude plugin validate: refused, {console_safe(out.splitlines()[0])}")
        return
    if "Validating components in" not in out:
        bad(f"claude plugin validate: did not validate {rel(skills_dir)}/ as a skills folder. "
            f"It picks its mode from the path, so this reports on the wrong thing rather than "
            f"failing outright.\n{out_tail}")
        return

    found = re.findall(r"Found (\d+) (error|warning)", out)
    counts = ", ".join(f"{n} {kind}(s)" for n, kind in found)

    # Fail CLOSED on anything that isn't a recognized clean pass: a future wording change must
    # read as "could not confirm clean", never as "nothing to report".
    if returncode != 0 or "Validation failed" in out:
        bad(f"claude plugin validate: failed (exit {returncode})"
            f"{': ' + counts if counts else ''}\n{out_tail}")
    elif "Validation passed with warnings" in out or found:
        bad(f"claude plugin validate: {counts or 'passed with warnings'}. It exits 0 on "
            f"warnings, so these are caught here rather than by the exit code.\n{out_tail}")
    elif "Validation passed" in out:
        ok(f"claude plugin validate: {rel(skills_dir)}/ clean, no errors or warnings")
    else:
        bad(f"claude plugin validate: output did not match a recognized pass/fail shape "
            f"(exit {returncode}). Treating as failed rather than silently reporting "
            f"clean - the vendor CLI's wording may have changed.\n{out_tail}")


# --- test suites ------------------------------------------------------------------------

# sys.executable, not "python": the interpreter running this file is known to exist, which
# `python` on a Windows PATH is not. Node has no such trick, so a missing `node` is reported.
# TAP, which failure_report() reads: Node 23 and later default to spec even when piped.
RUNNERS = {".py": lambda p: [sys.executable, str(p)],
           ".js": lambda p: ["node", "--test", "--test-reporter=tap", str(p)],
           ".mjs": lambda p: ["node", "--test", "--test-reporter=tap", str(p)]}

# unittest writes "Ran 39 tests" to stderr; node --test writes "pass 35" to stdout. The count
# makes a suite that quietly stopped covering anything visible. `node --test <file>` scores a
# file with no tests as one passing test, so only unittest's real 0 is caught.
COUNTS = (re.compile(r"^Ran (\d+) tests?", re.M), re.compile(r"^\D*pass (\d+)$", re.M))

TESTS_DIR = ROOT / "tools" / "tests"   # one suite per skill script, test_<script>.py


def check_tests():
    suite_dirs = integration_dirs() + [TESTS_DIR]
    # An add-on's pipeline/ runs its suite where it ships one, but is not held to having one.
    pipelines = sorted(d for d in (ROOT / "addons").glob("*/pipeline") if d.is_dir())
    suites = [p for d in suite_dirs + pipelines for p in sorted(d.iterdir())
              if p.suffix in RUNNERS and is_test_file(p)]
    for d in suite_dirs:
        if not any(p.parent == d for p in suites):
            bad(f"{rel(d)}/ ships no test suite")
    for d in skill_script_dirs():
        for script in sorted(d.glob("*.py")):
            if not (TESTS_DIR / f"test_{script.stem}.py").is_file():
                bad(f"{rel(script)} has no suite at tools/tests/test_{script.stem}.py")

    def run_suite(p):
        try:
            return run_captured(RUNNERS[p.suffix](p), timeout=300)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return e

    # The suites share nothing but the machine, and the slow ones wait on the git processes
    # they start, so they run side by side. Results report in suite order.
    with ThreadPoolExecutor(max_workers=max(2, os.cpu_count() or 2)) as pool:
        results = list(pool.map(run_suite, suites))

    for p, result in zip(suites, results):
        if isinstance(result, FileNotFoundError):
            bad(f"{rel(p)}: cannot run, `{RUNNERS[p.suffix](p)[0]}` is not on PATH. A suite "
                f"that could not run has not passed.")
            continue
        if isinstance(result, subprocess.TimeoutExpired):
            bad(f"{rel(p)}: timed out after 300s")
            continue
        returncode, combined = result

        count = next((int(m.group(1)) for m in (c.search(combined) for c in COUNTS) if m), None)
        if returncode != 0:
            bad(f"{rel(p)}: suite failed (exit {returncode})\n{failure_report(combined, console_safe)}")
        elif count == 0:
            bad(f"{rel(p)}: ran 0 tests - discovery found nothing to run")
        elif count is None:
            ok(f"{rel(p)}: passed, test count not reported")
        else:
            ok(f"{rel(p)}: {count} test(s) passed")


def main():
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    check_integrations()
    check_template_revisions()
    check_release_notes()
    check_fragments()
    check_template_size()
    check_dashes()
    check_dates()
    check_never_ship()
    check_example_skill_copies()
    check_skills()
    check_installed_links()
    check_launchers()
    check_rules_contract()
    check_skill_validator()
    check_tests()

    if verbose:
        for line in passes:
            print(f"  ok    {line}")
    for line in skips:
        print(f"  skip  {line}")
    for line in failures:
        print(f"  FAIL  {line}")

    if failures:
        print(f"\n{len(failures)} failure(s), {len(passes)} check(s) passed.")
        return 1
    print(f"All {len(passes)} contract check(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
