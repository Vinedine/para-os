#!/usr/bin/env python3
"""Tests for tools/eval.py.

    python3 test_eval.py
    py -3 test_eval.py

The harness is a mock: no `claude` runs. Every fixture is a throwaway tree in a temporary
directory standing in for the repo's skills, evals and examples.
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import eval as eval_tool


def write_case(evals, name, tools, tags="[native]"):
    case = evals / name
    case.mkdir(parents=True)
    (case / "case.yaml").write_text(f"name: {name}\ntags: {tags}\n", encoding="utf-8")
    (case / "prompt.md").write_text(
        f"---\nallowed_tools: [{', '.join(tools)}]\n---\nGo.\n", encoding="utf-8")


class FakeHarness:
    """Stands in for subprocess.run: records, per invocation, the cases the plugin it was
    started in holds and the tools it was granted, and writes the result file a real run would."""

    def __init__(self):
        self.calls = []

    def __call__(self, cmd, cwd=None, **kwargs):
        evals = Path(cwd) / "evals"
        names = sorted(p.name for p in evals.iterdir() if (p / "case.yaml").is_file())
        grant = []
        if "--allow-tools" in cmd:
            for item in cmd[cmd.index("--allow-tools") + 1:]:
                if item.startswith("--"):
                    break
                grant.append(item)
        out_dir = Path(cmd[cmd.index("--output-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "aggregate-result.json").write_text(json.dumps({
            "suite": {}, "costUsd": 1.5, "durationSeconds": 60,
            "cases": [{"name": n, "aggregates": {"score": 1.0}, "arms": {"with": [{}]}}
                      for n in names]}), encoding="utf-8")
        cost = cmd[cmd.index("--max-cost-usd") + 1] if "--max-cost-usd" in cmd else None
        self.calls.append({"cases": names, "grant": grant, "out_dir": out_dir, "cost": cost})
        return mock.Mock(returncode=0)


class GrantPerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="test-eval-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        repo = self.tmp / "repo"
        (repo / "base" / ".claude" / "skills" / "para-x").mkdir(parents=True)
        (repo / "base" / ".claude" / "skills" / "para-x" / "SKILL.md").write_text("x\n")
        (repo / "addons").mkdir()
        (repo / "multi-vault").mkdir()
        (repo / "examples").mkdir()
        evals = repo / "evals"
        (evals / "_fixture").mkdir(parents=True)
        self.tools = {
            "reads-only": ["Read", "Glob", "Grep", "Skill"],
            "reads-too": ["Read", "Skill"],
            "needs-shell": ["Read", "Bash"],
            "needs-shell-and-write": ["Bash", "Write", "Skill"],
            "writes": ["Write", "Edit"],
        }
        for name, tools in self.tools.items():
            write_case(evals, name, tools, "[shell]" if "Bash" in tools else "[native]")
        self.patches = [
            mock.patch.object(eval_tool, "ROOT", repo),
            mock.patch.object(eval_tool, "SKILLS", repo / "base" / ".claude" / "skills"),
            mock.patch.object(eval_tool, "ADDON_SKILLS", repo / "addons"),
            mock.patch.object(eval_tool, "MULTI_VAULT", repo / "multi-vault"),
            mock.patch.object(eval_tool, "EVALS", evals),
            mock.patch.object(eval_tool, "EXAMPLES", repo / "examples"),
            mock.patch.object(eval_tool, "shell_blocker", lambda: None),
            mock.patch.object(eval_tool.shutil, "which", lambda name: "claude"),
            mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.tmp / "home")}),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def run_eval(self, *argv):
        harness = FakeHarness()
        out = io.StringIO()
        with mock.patch.object(eval_tool.subprocess, "run", harness), \
                contextlib.redirect_stdout(out):
            rc = eval_tool.main(list(argv))
        return rc, harness, out.getvalue()

    def test_a_mocked_server_is_declared_so_its_mock_stands_in(self):
        mocks = eval_tool.EVALS / "reads-only" / "mocks" / "mailserver"
        mocks.mkdir(parents=True)
        (mocks / "search_messages.md").write_text("[]\n", encoding="utf-8")
        plugin = eval_tool.build_plugin(self.tmp / "work")
        declared = json.loads((plugin / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(list(declared["mcpServers"]), ["mailserver"])

    def gated(self, name):
        return [t for t in eval_tool.GATED if t in self.tools[name]]

    def test_each_case_runs_once_with_exactly_its_own_grant(self):
        rc, harness, _ = self.run_eval("--shell")
        self.assertEqual(rc, 0)
        seen = {}
        for call in harness.calls:
            for name in call["cases"]:
                self.assertNotIn(name, seen, f"{name} ran twice")
                seen[name] = call["grant"]
        self.assertEqual(sorted(seen), sorted(self.tools))
        for name, grant in seen.items():
            self.assertEqual(grant, self.gated(name), name)

    def test_one_invocation_per_distinct_grant(self):
        _, harness, _ = self.run_eval("--shell")
        self.assertEqual(sorted(tuple(c["grant"]) for c in harness.calls),
                         sorted({tuple(self.gated(n)) for n in self.tools}))

    def test_results_merge_into_one_run_folder(self):
        _, harness, _ = self.run_eval("--shell")
        out_dir = harness.calls[0]["out_dir"].parent
        merged = json.loads((out_dir / "aggregate-result.json").read_text(encoding="utf-8"))
        self.assertEqual([c["name"] for c in merged["cases"]], sorted(self.tools))
        self.assertEqual(merged["costUsd"], 1.5 * len(harness.calls))
        self.assertEqual(merged["durationSeconds"], 60 * len(harness.calls))

    def test_each_invocation_gets_the_ceiling_share_of_its_cases(self):
        _, harness, _ = self.run_eval("--shell", "--", "--max-cost-usd", "50")
        self.assertEqual({tuple(c["cases"]): c["cost"] for c in harness.calls}, {
            ("reads-only", "reads-too"): "20", ("needs-shell",): "10",
            ("needs-shell-and-write",): "10", ("writes",): "10"})

    def test_one_grant_runs_once_in_the_run_folder_itself(self):
        rc, harness, _ = self.run_eval("--case", "reads-*")
        self.assertEqual(len(harness.calls), 1)
        self.assertEqual(harness.calls[0]["grant"], [])
        self.assertTrue((harness.calls[0]["out_dir"] / "aggregate-result.json").is_file())

    def test_an_operator_grant_applies_to_every_case(self):
        _, harness, _ = self.run_eval("--shell", "--", "--allow-tools", "Write")
        self.assertEqual(len(harness.calls), 1)
        self.assertEqual(sorted(harness.calls[0]["cases"]), sorted(self.tools))


class Summary(unittest.TestCase):
    def summary(self, runs, suite=None):
        out_dir = Path(tempfile.mkdtemp(prefix="test-eval-"))
        self.addCleanup(shutil.rmtree, out_dir, ignore_errors=True)
        (out_dir / "aggregate-result.json").write_text(json.dumps({
            "claudeVersion": "2.1.0", "suite": {"judgeModel": "sonnet", **(suite or {})},
            "cases": [{"name": "a", "aggregates": {"score": 1.0}, "arms": {"with": runs}}]}),
            encoding="utf-8")
        return eval_tool.summary_markdown(out_dir)

    def test_names_the_model_a_kept_trace_ran_on(self):
        trace = Path(tempfile.mkdtemp(prefix="test-eval-")) / "trace.jsonl"
        self.addCleanup(shutil.rmtree, trace.parent, ignore_errors=True)
        trace.write_text(json.dumps({"type": "system", "subtype": "hook_started"}) + "\n" +
                         json.dumps({"type": "system", "subtype": "init",
                                     "model": "claude-test-1"}) + "\n", encoding="utf-8")
        self.assertIn("Claude Code 2.1.0, model claude-test-1, judge sonnet",
                      self.summary([{"tracePath": str(trace)}]))

    def test_without_a_trace_names_the_override_or_nothing(self):
        gone = [{"tracePath": "/no/such/trace.jsonl"}]
        self.assertIn("model opus, judge", self.summary(gone, {"modelOverride": "opus"}))
        self.assertIn("model ?, judge", self.summary(gone))


class SplitCost(unittest.TestCase):
    def test_each_invocation_gets_its_share_of_the_ceiling(self):
        self.assertEqual(eval_tool.split_cost(["--runs", "1", "--max-cost-usd", "40"], 0.5),
                         ["--runs", "1", "--max-cost-usd", "20"])
        self.assertEqual(eval_tool.split_cost(["--max-cost-usd=30"], 1 / 3), ["--max-cost-usd=10"])

    def test_one_invocation_keeps_the_ceiling(self):
        self.assertEqual(eval_tool.split_cost(["--max-cost-usd", "40"], 1), ["--max-cost-usd", "40"])


if __name__ == "__main__":
    unittest.main()
