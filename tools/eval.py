#!/usr/bin/env python3
"""Run the repo's eval suite against para-os's skills, without shipping a plugin.

    py -3 tools/eval.py                       # every case, as the vendor defaults run them
    py -3 tools/eval.py --case daily-brief-*  # one case
    py -3 tools/eval.py -- --runs 1 --ablation none   # anything after -- goes to the vendor
    python3 tools/eval.py --summary "$GITHUB_STEP_SUMMARY"   # also append Markdown

`claude plugin eval` only loads skills that belong to a plugin, and para-os deliberately
ships no manifest: it is a template repo, not a marketplace entry, and `claude plugin
validate` already reads base/.claude/skills/ as a plain skills folder. So this wrapper
assembles a plugin in a temporary directory instead: base's skills, every add-on's and the
multi-vault layer's skills beside them as an operator installs them, a generated manifest,
and a copy of evals/ with the example vaults beside its fixtures. The repo keeps exactly
what it had, and the harness gets the shape it needs.

Results land in ${PARAOS_HOME:-~/.paraos}/data/eval-runs/<timestamp>/, where the repo
already keeps what a run produced rather than what it ships. Nothing is written inside
the repo, so a report full of a model's prose never reaches a shipped-text check.

Every case's fixture vault is built by its own setup.sh, so nothing here reads a real
vault. The scaffold flag is passed by default because the cases in this repo are ours.
"""

import argparse
import fnmatch
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "base" / ".claude" / "skills"
ADDON_SKILLS = ROOT / "addons"   # addons/<name>/.claude/skills/<skill>/
MULTI_VAULT = ROOT / "multi-vault"   # multi-vault/<skill>/
EVALS = ROOT / "evals"
EXAMPLES = ROOT / "examples"

MANIFEST = {
    "name": "para-os",
    "version": "0.0.0",
    "description": "para-os skills under test. Assembled by tools/eval.py, never shipped.",
}


# Tools the harness withholds from a run unless the operator grants them. A case lists what it
# needs in its prompt's allowed_tools; without the grant the model never gets the tool, so a
# case that needs a shell fails, and a "never writes" grader passes for the wrong reason.
GATED = ("Bash", "PowerShell", "Write", "Edit", "WebFetch")


def _listed(path, key):
    """The items of a one-line `key: [a, b]` list in a case file, or none."""
    if not path.is_file():
        return []
    m = re.search(rf"^{key}:\s*\[(.*)\]\s*$", path.read_text(encoding="utf-8"), re.M)
    return [t.strip().strip("'\"") for t in m.group(1).split(",") if t.strip()] if m else []


def selected_cases(case_glob, tags):
    """{name: (tags, allowed tools)} for the cases the harness will run, selected the way it
    selects them: by name glob, then by any of the given tags."""
    cases = {}
    for d in sorted(p for p in EVALS.iterdir() if (p / "case.yaml").is_file()):
        if case_glob and not fnmatch.fnmatch(d.name, case_glob):
            continue
        case_tags = _listed(d / "case.yaml", "tags")
        if tags and not set(tags) & set(case_tags):
            continue
        cases[d.name] = (case_tags, _listed(d / "prompt.md", "allowed_tools"))
    return cases


def split_cost(cmd, parts):
    """`cmd` with any `--max-cost-usd` ceiling divided across `parts` harness invocations,
    so the whole run still stops at the ceiling the caller set."""
    out, i = list(cmd), 0
    while i < len(out):
        if out[i] == "--max-cost-usd" and i + 1 < len(out):
            out[i + 1] = f"{float(out[i + 1]) / parts:g}"
        elif out[i].startswith("--max-cost-usd="):
            out[i] = f"--max-cost-usd={float(out[i].split('=', 1)[1]) / parts:g}"
        i += 1
    return out


def grant_groups(cases):
    """[(grant, [case names])] with one entry per distinct grant: the gated tools that
    case's own prompt lists. A case is graded in a session built for it, never one granted
    another case's shell."""
    groups = {}
    for name, (_, tools) in cases.items():
        groups.setdefault(tuple(t for t in GATED if t in tools), []).append(name)
    return list(groups.items())


def tag_values(rest):
    """Every value given to --tag in the options passed through to the harness."""
    out = []
    for i, a in enumerate(rest):
        if a == "--tag" and i + 1 < len(rest):
            out.append(rest[i + 1])
        elif a.startswith("--tag="):
            out.append(a.split("=", 1)[1])
    return out


def shell_blocker():
    """Why this machine cannot run a granted shell, or None. The harness refuses to run one
    unconfined, and says so only after the run has started."""
    if sys.platform == "win32":
        return ("a granted shell is refused on native Windows: run the shell cases under "
                "WSL2 or on Linux or macOS, or select only cases that need no shell")
    if sys.platform.startswith("linux"):
        missing = [t for t in ("bwrap", "socat") if not shutil.which(t)]
        if missing:
            return (f"the harness sandboxes a granted shell with bubblewrap and socat, and "
                    f"this machine lacks {', '.join(missing)}: install them "
                    f"(`sudo apt install bubblewrap socat`), or select only cases that need "
                    f"no shell")
    return None


def claim_run_dir(runs):
    """Create this run's results folder, named by the second it started so folders sort by
    time. A run starting in the same second as another (a before and an after launched
    together) takes the next free suffix, rather than sharing a folder whose report the
    later run would overwrite."""
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    runs.mkdir(parents=True, exist_ok=True)
    for n in itertools.count(1):
        out_dir = runs / (stamp if n == 1 else f"{stamp}-{n}")
        try:
            out_dir.mkdir()
            return out_dir
        except FileExistsError:
            pass


def summary_markdown(out_dir):
    """The run as Markdown, one row per case in case order, so one run reads against the
    last. Scores are counted against 1.0 rather than the run's threshold, which CI sets to 0
    so that a score never fails the job. A run that hit a usage limit is still graded and
    scores 0 without the suite being partial, so each case shows its errors beside its score."""
    try:
        result = json.loads((out_dir / "aggregate-result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "## Evals\n\nNo result: the harness wrote no aggregate-result.json.\n"

    def cell(text, width=120):
        text = " ".join(str(text).split()).replace("|", "/")
        return text if len(text) <= width else text[:width - 3] + "..."

    suite, cases = result.get("suite", {}), result.get("cases", [])
    scores = [c.get("aggregates", {}).get("score", 0) for c in cases]
    lines = ["## Evals", ""]
    if result.get("partial"):
        lines += [f"**Partial run** ({result.get('partialReason', 'no reason given')}): "
                  f"leave it out of any trend.", ""]
    lines += [f"{sum(s >= 1 for s in scores)} of {len(cases)} cases scored 1.00. "
              f"Claude Code {result.get('claudeVersion', '?')}, judge "
              f"{suite.get('judgeModel', '?')}, ablation {suite.get('ablation', '?')}, "
              f"{result.get('costUsd', 0):.2f} USD at list price, "
              f"{round(result.get('durationSeconds', 0) / 60)} min.", "",
              "| Case | Score | Delta | Runs | Errors |", "|---|---:|---:|---:|---|"]
    for case, score in zip(cases, scores):
        runs = case.get("arms", {}).get("with", [])
        errors = [r["error"] for r in runs if r.get("error")]
        delta = case.get("aggregates", {}).get("delta")
        delta = "" if delta is None else f"{delta:+.2f}"
        errors = cell(f"{len(errors)}: {errors[0]}") if errors else ""
        lines.append(f"| {case.get('name', '?')} | {score:.2f} | {delta} | {len(runs)} | "
                     f"{errors} |")
    return "\n".join(lines) + "\n"


def no_skill_copy(directory, names):
    """What copying an example vault leaves out: the untracked `.claude/skills/` copy it may
    hold, so a case loads the skills under test rather than a stale copy of them, and the
    caches a test run leaves behind."""
    skip = {"__pycache__", ".pytest_cache"} & set(names)
    return skip | ({"skills"} if Path(directory).name == ".claude" else set())


def merge_results(out_dir, parts):
    """Write the one aggregate-result.json of a run the harness was invoked for in several
    folders, so the report and the summary read it as a single run. The cases keep name
    order; cost and time add up."""
    results = []
    for part in parts:
        try:
            results.append(json.loads((part / "aggregate-result.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    if not results:
        return
    merged = dict(results[0])
    merged["cases"] = sorted((c for r in results for c in r.get("cases", [])),
                             key=lambda c: c.get("name", ""))
    for key in ("costUsd", "durationSeconds"):
        merged[key] = sum(r.get(key, 0) for r in results)
    reasons = [r.get("partialReason", "no reason given") for r in results if r.get("partial")]
    merged["partial"] = bool(reasons)
    if reasons:
        merged["partialReason"] = "; ".join(reasons)
    (out_dir / "aggregate-result.json").write_text(json.dumps(merged, indent=2) + "\n",
                                                   encoding="utf-8")


def build_plugin(workdir, only=None):
    """Assemble the plugin the harness wants: skills, a manifest, and the cases (only the
    named ones, where `only` is given)."""
    plugin = workdir / "para-os"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(MANIFEST, indent=2) + "\n", encoding="utf-8")
    shutil.copytree(SKILLS, plugin / "skills")
    for skill in sorted([*ADDON_SKILLS.glob("*/.claude/skills/*/SKILL.md"),
                         *MULTI_VAULT.glob("*/SKILL.md")]):
        target = plugin / "skills" / skill.parent.name
        if target.exists():
            raise SystemExit(f"{skill.parent} has the name of a skill already loaded")
        shutil.copytree(skill.parent, target)
    def skip_cases(directory, names):
        out = {"results"} & set(names)
        if only is not None and Path(directory) == EVALS:
            out |= {n for n in names if (EVALS / n / "case.yaml").is_file() and n not in only}
        return out

    shutil.copytree(EVALS, plugin / "evals", ignore=skip_cases)
    shutil.copytree(EXAMPLES, plugin / "evals" / "_fixture" / "examples", ignore=no_skill_copy)
    return plugin


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--case", help="case name glob, passed through to the harness")
    ap.add_argument("--shell", action="store_true",
                    help="also run cases that need a shell grant, which are refused on a "
                         "machine with no sandbox backend after paying for the run")
    ap.add_argument("--keep", action="store_true",
                    help="keep the assembled plugin directory and print its path")
    ap.add_argument("--dry-run", action="store_true",
                    help="assemble and print the command, run nothing")
    ap.add_argument("--summary", metavar="FILE",
                    help="append each case's score as Markdown to FILE "
                         "(CI: $GITHUB_STEP_SUMMARY)")
    ap.add_argument("rest", nargs="*",
                    help="further options for claude plugin eval, after --")
    args = ap.parse_args(argv)

    if not SKILLS.is_dir():
        ap.error(f"no skills at {SKILLS}")
    if not EVALS.is_dir():
        ap.error(f"no eval cases at {EVALS}; write one before running this")

    home = Path(os.environ.get("PARAOS_HOME") or (Path.home() / ".paraos"))
    out_dir = claim_run_dir(home / "data" / "eval-runs")
    workdir = Path(tempfile.mkdtemp(prefix="para-os-eval-"))
    try:
        # On Windows the command is a .CMD shim, which CreateProcess will not find by
        # its bare name, so resolve it the way the shell would.
        claude = shutil.which("claude")
        if not claude:
            ap.error("claude is not on PATH")
        cmd = ["--trust-plugin", "--scaffold", "--no-publish"]
        tags = tag_values(args.rest)
        if args.case:
            cmd += ["--case", args.case]
        matched = selected_cases(args.case, tags)
        needs_shell = [n for n, (_, tools) in matched.items() if {"Bash", "PowerShell"} & set(tools)]
        if not args.shell and not tags and (not args.case or needs_shell):
            # A case needing a shell is not free to skip late: without the grant the run
            # still happens, the model just never gets the tool, and the bill arrives with
            # a failure that says nothing. Select the ones that can pass here instead. The
            # harness intersects --case with --tag, so a glob catching no shell case (the
            # install cases carry no native tag) is passed through as given.
            cmd += ["--tag", "native"]
            tags = ["native"]
            if args.case:
                left_out = sorted(set(matched) - set(selected_cases(args.case, tags)))
                if len(left_out) == len(matched):
                    ap.error(f"--case {args.case} matches only cases that need a shell; "
                             f"pass --shell to run them")
                print(f"selecting --tag native, which leaves out {' '.join(left_out)}; "
                      f"--shell runs them")

        cmd += args.rest
        # The harness's own default judge answers in one word with no thinking, and fails
        # right answers that a rubric has to read closely; evals/README.md has the evidence.
        if not any(a == "--judge-model" or a.startswith("--judge-model=") for a in args.rest):
            cmd += ["--judge-model", "sonnet"]
        # Grant each case what its own prompt lists, in one harness run per distinct grant,
        # unless the operator granted tools themselves, which then apply to every case.
        cases = selected_cases(args.case, tags)
        if any(a == "--allow-tools" or a.startswith("--allow-tools=") for a in args.rest):
            groups = [((), None)]
        else:
            groups = grant_groups(cases) if cases else [((), None)]
            if {"Bash", "PowerShell"} & {t for grant, _ in groups for t in grant}:
                blocker = shell_blocker()
                if blocker and not args.dry_run:
                    ap.error(blocker)
        if len(groups) == 1:
            groups = [(groups[0][0], None)]

        code, part_dirs = 0, []
        for i, (grant, names) in enumerate(groups):
            part = out_dir / f"group-{i}" if len(groups) > 1 else out_dir
            part_dirs.append(part)
            plugin = build_plugin(workdir / str(i), names)
            run = [claude, "plugin", "eval", str(plugin), *split_cost(cmd, len(groups)),
                   "--output-dir", str(part)]
            if grant:
                run += ["--allow-tools", *grant]
                print(f"granting {' '.join(grant)}: listed by "
                      f"{'the selected cases' if names is None else ' '.join(names)}")
            print(f"plugin assembled at {plugin}")
            print(" ".join(run))
            if not args.dry_run:
                code = max(code, subprocess.run(run, cwd=str(plugin)).returncode)
        if args.dry_run:
            return 0
        if len(groups) > 1:
            merge_results(out_dir, part_dirs)
        print(f"results: {out_dir}")
        if args.summary:
            with open(args.summary, "a", encoding="utf-8") as f:
                f.write(summary_markdown(out_dir))
        return code
    finally:
        if args.keep:
            print(f"kept {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)
        # A dry run, or one stopped before the harness wrote anything, leaves no empty folder.
        try:
            out_dir.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
