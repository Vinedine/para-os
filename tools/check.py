#!/usr/bin/env python3
"""Contract checks for the para-os repo. No dependencies; run it before shipping a revision.

    python3 tools/check.py            # report and exit non-zero on any failure
    python3 tools/check.py -v         # also list every check that passed

What it enforces, and why each one is machinery rather than prose:

  Integration markers   The versioning scheme in integrations/README.md only works if every
                        shipped script carries `para-os-integration: <name> <revision>` and
                        the folder's revision matches its row in the Available table.
                        /para-upgrade compares an installed copy against that marker, so a
                        marker that disagrees with the table sends the wrong answer to every
                        vault, silently.

  Template revisions    base/, each flavor skeleton, and each example vault all stamp a
                        `<!-- para-os-template: -->` marker. They must agree with the newest
                        CHANGELOG entry: a flavor left a revision behind means /para-upgrade
                        reads a stale master and reports "nothing to do" on a vault that
                        genuinely needs migrating.

  Dashes                CLAUDE.md makes this a hard rule for shipped prose, and it is the one
                        style rule a reader notices immediately.

  Colocated tests       Each integration's own suite, run in place: `test_*.py` and `*.test.js`
                        next to the script they cover. Shipping a revision is one command, not
                        three remembered ones. A suite whose runtime is missing FAILS rather
                        than skipping: an integration nobody could verify must not report as a
                        clean bill of health.

Deliberately NOT checked: anything requiring judgement (privacy, bloat, whether a rule earns
its words). Those are review, not a script.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # repo root; this file lives in tools/
REVISION = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
SCRIPT_SUFFIXES = {".py", ".js", ".ps1", ".sh"}

failures = []
passes = []


def ok(msg):
    passes.append(msg)


def bad(msg):
    failures.append(msg)


def rel(p):
    return p.relative_to(ROOT).as_posix()


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
            listed = ", ".join(f"{p.name}={v}" for p, v in sorted(revisions.items()))
            bad(f"integrations/{d.name}/: scripts disagree on the revision ({listed}). "
                f"The version is per integration, not per file.")
        elif distinct:
            got = distinct.pop()
            want = table.get(d.name)
            if want and got != want:
                bad(f"integrations/{d.name}/: scripts say {got}, "
                    f"Available table says {want}")
            else:
                ok(f"integrations/{d.name}/ at {got}, {len(revisions)} script(s) stamped")


# --- template revisions ----------------------------------------------------------------

def changelog_revisions():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return re.findall(r"^##\s+(\d{4}\.\d{2}\.\d{2})\s*$", text, re.M)


def template_files():
    files = [ROOT / "base" / "CLAUDE.md.template"]
    files += sorted((ROOT / "flavors").glob("*/skeleton/CLAUDE.md.template"))
    files += sorted(p / "CLAUDE.md" for p in (ROOT / "examples").iterdir()
                    if p.is_dir() and (p / "CLAUDE.md").exists())
    return [f for f in files if f.exists()]


def check_template_revisions():
    revisions = changelog_revisions()
    if not revisions:
        bad("CHANGELOG.md: no `## YYYY.MM.NN` revision headings found")
        return
    if revisions != sorted(revisions, reverse=True):
        bad(f"CHANGELOG.md: revisions are not newest-first ({', '.join(revisions)})")
    if len(set(revisions)) != len(revisions):
        bad("CHANGELOG.md: a revision heading appears twice")
    current = revisions[0]

    for f in template_files():
        m = re.search(r"<!--\s*para-os-template:\s*(\S+)\s*-->",
                      f.read_text(encoding="utf-8", errors="ignore"))
        if not m:
            bad(f"{rel(f)}: no `<!-- para-os-template: -->` marker")
        elif m.group(1) != current:
            bad(f"{rel(f)}: stamped {m.group(1)}, newest changelog revision is {current}")
        else:
            ok(f"{rel(f)} at {current}")


# --- style -----------------------------------------------------------------------------

DASHES = ("\u2014", "\u2013")  # em, en: escaped so this file passes its own check.
FENCE = re.compile(r"^\s*```")
CODE_SPAN = re.compile(r"`[^`]*`")


def check_dashes():
    """The rule is about *prose*, so code is out of scope: a regex that matches an en dash in
    someone's calendar entry, inside a regex character class, is parsing data,
    not writing prose."""
    hits = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or ".git" in p.parts or "node_modules" in p.parts:
            continue
        if p.suffix not in {".md", ".template", ".py", ".js", ".json", ".ps1"}:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        in_fence = False
        for n, line in enumerate(text.splitlines(), 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            prose = CODE_SPAN.sub("", line)
            if any(d in prose for d in DASHES):
                hits.append(f"{rel(p)}:{n}")
    if hits:
        shown = ", ".join(hits[:8]) + (f" (+{len(hits) - 8} more)" if len(hits) > 8 else "")
        bad(f"em/en dash in shipped text: {shown}")
    else:
        ok("no em/en dashes in shipped text")


# --- colocated test suites --------------------------------------------------------------

# sys.executable, not "python": the interpreter running this file is known to exist, which
# `python` on a Windows PATH is not. Node has no such trick, so a missing `node` is reported.
RUNNERS = {".py": lambda p: [sys.executable, str(p)],
           ".js": lambda p: ["node", "--test", str(p)]}

# unittest writes "Ran 39 tests" to stderr; node --test writes "pass 35" to stdout. The count
# is reported so a suite that quietly stopped covering anything is visible at a glance. It is
# not a guarantee: `node --test <file>` scores a file with no tests in it as one passing test,
# so only a runner that reports a real 0 (unittest does, and exits non-zero too) is caught.
COUNTS = (re.compile(r"^Ran (\d+) tests?", re.M), re.compile(r"^\D*pass (\d+)$", re.M))


def check_tests():
    suites = [p for d in integration_dirs() for p in sorted(d.iterdir())
              if p.suffix in RUNNERS and is_test_file(p)]
    for d in integration_dirs():
        if not any(p.parent == d for p in suites):
            bad(f"integrations/{d.name}/ ships no test suite")

    for p in suites:
        cmd = RUNNERS[p.suffix](p)
        try:
            # utf-8 explicitly: node --test emits box-drawing and ℹ, which a cp1252 console
            # default cannot decode, and a UnicodeDecodeError here would read as a test failure.
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=300)
        except FileNotFoundError:
            bad(f"{rel(p)}: cannot run, `{cmd[0]}` is not on PATH. A suite that could not "
                f"run has not passed.")
            continue
        except subprocess.TimeoutExpired:
            bad(f"{rel(p)}: timed out after 300s")
            continue

        combined = f"{r.stdout or ''}\n{r.stderr or ''}".strip()
        count = next((int(m.group(1)) for m in (c.search(combined) for c in COUNTS) if m), None)
        if r.returncode != 0:
            tail = "\n".join(f"        {ln}" for ln in combined.splitlines()[-15:])
            bad(f"{rel(p)}: suite failed (exit {r.returncode})\n{tail}")
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
    check_dashes()
    check_tests()

    if verbose:
        for line in passes:
            print(f"  ok    {line}")
    for line in failures:
        print(f"  FAIL  {line}")

    if failures:
        print(f"\n{len(failures)} failure(s), {len(passes)} check(s) passed.")
        return 1
    print(f"All {len(passes)} contract check(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
