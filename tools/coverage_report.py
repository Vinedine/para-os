#!/usr/bin/env python3
"""Measure what the test suites actually exercise. CI's coverage job runs this.

    python3 tools/coverage_report.py                            # report only
    python3 tools/coverage_report.py --fail-under 90 --fail-under-js 60
    python3 tools/coverage_report.py --summary "$GITHUB_STEP_SUMMARY"   # also append Markdown

The suites are the ones tools/check.py runs, found the same way, so a suite added there is
measured here with no second list to keep. Python is measured with coverage.py, lines and
branches, including the scripts a test launches as a subprocess (the CLI tests run the real
script). JavaScript is measured with Node's built-in coverage, lines only.

check.py stays dependency-free, so this is a separate tool: it needs coverage.py 7.10 or
later (`python3 -m pip install "coverage>=7.10"`), and `requests` for outlook's suite, as
check.py does. Everything it writes goes to a temporary folder; the repo is left untouched.

The floors guard against a drop, not for a number: a suite that stops reaching a script
fails the job rather than quietly shrinking. Raise them when coverage rises.
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402  (the discovery lives there; importing it runs no check)

ROOT = check.ROOT

# Node's TAP prints one row per file: `name | line % | branch % | funcs % | uncovered lines`,
# indented under folder rows on newer versions. Only the rows naming a file are read.
NODE_ROW = re.compile(r"^#\s*(\S+\.m?js)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|")


def suites():
    """{suite folder: [test files]} for every folder check.py runs a suite in."""
    found = {}
    for d in check.integration_dirs() + [check.TESTS_DIR]:
        tests = sorted(p for p in d.iterdir() if check.is_test_file(p) and p.suffix in check.RUNNERS)
        if tests:
            found[d] = tests
    return found


def python_coverage(folders, tmp, fail_under):
    """Run every Python suite under coverage.py; return (ok, text report, Markdown report).
    What is measured is the scripts: the integrations and every skill's scripts/ folder."""
    rc = tmp / "coveragerc"
    sources = "\n    ".join(str(d) for d in check.integration_dirs() + check.skill_script_dirs())
    rc.write_text(
        "[run]\n"
        "branch = True\n"
        "parallel = True\n"
        "patch = subprocess\n"
        f"data_file = {tmp / '.coverage'}\n"
        f"source =\n    {sources}\n"
        "omit = */test_*.py\n"
        "[report]\n"
        "precision = 1\n"
        "sort = Cover\n",
        encoding="utf-8")
    cov = [sys.executable, "-m", "coverage"]
    ok = True
    for d, tests in folders.items():
        for t in tests:
            r = subprocess.run(cov + ["run", f"--rcfile={rc}", str(t)], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode != 0:
                ok = False
                print(f"FAIL  {check.rel(t)}: suite failed under coverage (exit {r.returncode})")
                print(check.failure_report(f"{r.stdout}\n{r.stderr}".strip()))
    subprocess.run(cov + ["combine", f"--rcfile={rc}", "-q"], cwd=ROOT, check=True)

    def report(*extra):
        r = subprocess.run(cov + ["report", f"--rcfile={rc}", *extra], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout

    floor = [f"--fail-under={fail_under}"] if fail_under is not None else []
    code, text = report(*floor)
    _, markdown = report("--format=markdown")
    if code != 0:
        ok = False
        print(f"FAIL  Python coverage is under the {fail_under}% floor")
    return ok, text, markdown


def js_coverage(folders, fail_under):
    """Run every Node suite with --experimental-test-coverage; return (ok, rows)."""
    ok = True
    rows = []
    for d, tests in folders.items():
        r = subprocess.run(["node", "--test", "--test-reporter=tap", "--experimental-test-coverage",
                            *[t.name for t in tests]],
                           cwd=d, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            ok = False
            print(f"FAIL  {check.rel(d)}: node suite failed under coverage (exit {r.returncode})")
            print(check.failure_report(f"{r.stdout}\n{r.stderr}".strip()))
        for line in r.stdout.splitlines():
            m = NODE_ROW.match(line)
            if m and ".test." not in m.group(1):
                rows.append((f"{check.rel(d)}/{m.group(1)}", float(m.group(2)), float(m.group(3))))
    for name, lines, _ in rows:
        if fail_under is not None and lines < fail_under:
            ok = False
            print(f"FAIL  {name}: {lines:.1f}% of lines covered, under the {fail_under}% floor")
    return ok, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fail-under", type=float, metavar="PCT",
                    help="fail when the Python total (lines and branches) is under PCT")
    ap.add_argument("--fail-under-js", type=float, metavar="PCT",
                    help="fail when any JavaScript script's line coverage is under PCT")
    ap.add_argument("--summary", metavar="FILE",
                    help="append the report as Markdown to FILE (CI: $GITHUB_STEP_SUMMARY)")
    args = ap.parse_args()

    try:
        import coverage
    except ImportError:
        print('coverage.py is not installed: python3 -m pip install "coverage>=7.10"')
        return 2
    if tuple(int(x) for x in coverage.__version__.split(".")[:2]) < (7, 10):
        print(f"coverage.py {coverage.__version__} is too old: 7.10 added the subprocess "
              f"measurement the CLI tests need")
        return 2

    found = suites()
    py = {d: [t for t in ts if t.suffix == ".py"] for d, ts in found.items()}
    js = {d: [t for t in ts if t.suffix in (".js", ".mjs")] for d, ts in found.items()}
    py = {d: ts for d, ts in py.items() if ts}
    js = {d: ts for d, ts in js.items() if ts}

    with tempfile.TemporaryDirectory() as tmp:
        py_ok, text, markdown = python_coverage(py, Path(tmp), args.fail_under)
    js_ok, js_rows = js_coverage(js, args.fail_under_js)

    print(text)
    if js_rows:
        width = max(len(n) for n, _, _ in js_rows)
        print(f"{'JavaScript':<{width}}  Lines  Branches")
        for name, lines, branches in js_rows:
            print(f"{name:<{width}}  {lines:5.1f}  {branches:8.1f}")

    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as f:
            f.write("## Test coverage\n\n### Python (lines and branches)\n\n")
            f.write(markdown.strip() + "\n\n")
            if js_rows:
                f.write("### JavaScript\n\n| Script | Lines | Branches |\n|---|---:|---:|\n")
                for name, lines, branches in js_rows:
                    f.write(f"| {name} | {lines:.1f}% | {branches:.1f}% |\n")
                f.write("\n")

    return 0 if py_ok and js_ok else 1


if __name__ == "__main__":
    sys.exit(main())
