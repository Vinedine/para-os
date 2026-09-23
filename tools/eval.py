#!/usr/bin/env python3
"""Run the repo's eval suite against para-os's skills, without shipping a plugin.

    py -3 tools/eval.py                       # every case, as the vendor defaults run them
    py -3 tools/eval.py --case daily-brief-*  # one case
    py -3 tools/eval.py -- --runs 1 --ablation none   # anything after -- goes to the vendor

`claude plugin eval` only loads skills that belong to a plugin, and para-os deliberately
ships no manifest: it is a template repo, not a marketplace entry, and `claude plugin
validate` already reads base/.claude/skills/ as a plain skills folder. So this wrapper
assembles a plugin in a temporary directory instead: base's skills, a generated manifest,
and a copy of evals/. The repo keeps exactly what it had, and the harness gets the shape
it needs.

Results land in ${PARAOS_HOME:-~/.paraos}/data/eval-runs/<timestamp>/, where the repo
already keeps what a run produced rather than what it ships. Nothing is written inside
the repo, so a report full of a model's prose never reaches a shipped-text check.

Every case's fixture vault is built by its own setup.sh, so nothing here reads a real
vault. The scaffold flag is passed by default because the cases in this repo are ours.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "base" / ".claude" / "skills"
EVALS = ROOT / "evals"

MANIFEST = {
    "name": "para-os",
    "version": "0.0.0",
    "description": "para-os skills under test. Assembled by tools/eval.py, never shipped.",
}


def build_plugin(workdir):
    """Assemble the plugin the harness wants: skills, a manifest, and the cases."""
    plugin = workdir / "para-os"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(MANIFEST, indent=2) + "\n", encoding="utf-8")
    shutil.copytree(SKILLS, plugin / "skills")
    shutil.copytree(EVALS, plugin / "evals",
                    ignore=shutil.ignore_patterns("results"))
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
    ap.add_argument("rest", nargs="*",
                    help="further options for claude plugin eval, after --")
    args = ap.parse_args(argv)

    if not SKILLS.is_dir():
        ap.error(f"no skills at {SKILLS}")
    if not EVALS.is_dir():
        ap.error(f"no eval cases at {EVALS}; write one before running this")

    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    home = Path(os.environ.get("PARAOS_HOME") or (Path.home() / ".paraos"))
    out_dir = home / "data" / "eval-runs" / stamp
    workdir = Path(tempfile.mkdtemp(prefix="para-os-eval-"))
    try:
        plugin = build_plugin(workdir)
        # On Windows the command is a .CMD shim, which CreateProcess will not find by
        # its bare name, so resolve it the way the shell would.
        claude = shutil.which("claude")
        if not claude:
            ap.error("claude is not on PATH")
        cmd = [claude, "plugin", "eval", str(plugin),
               "--trust-plugin", "--scaffold", "--no-publish",
               "--output-dir", str(out_dir)]
        if args.case:
            cmd += ["--case", args.case]
        elif not args.shell and "--tag" not in args.rest:
            # A case needing a shell is not free to skip late: without the grant the run
            # still happens, the model just never gets the tool, and the bill arrives with
            # a failure that says nothing. Select the ones that can pass here instead.
            cmd += ["--tag", "native"]
        cmd += args.rest

        print(f"plugin assembled at {plugin}")
        print(" ".join(cmd))
        if args.dry_run:
            return 0
        done = subprocess.run(cmd, cwd=str(plugin))
        print(f"results: {out_dir}")
        return done.returncode
    finally:
        if args.keep:
            print(f"kept {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
