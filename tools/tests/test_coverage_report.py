#!/usr/bin/env python3
"""Tests for coverage_report.py: it measures what check.py runs, with no second list."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check  # noqa: E402  (importing it runs no check)
import coverage_report  # noqa: E402

PIPELINE = check.ROOT / "addons" / "activity" / "pipeline"


class Discovery(unittest.TestCase):
    def test_an_addon_pipelines_suite_runs_with_the_others(self):
        found = coverage_report.suites()
        self.assertIn(PIPELINE / "test_activity.py", found.get(PIPELINE, []))
        self.assertIn(check.TESTS_DIR, found)

    def test_an_addon_pipelines_script_is_measured(self):
        done = mock.Mock(returncode=0, stdout="")
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(coverage_report.subprocess, "run", return_value=done):
            coverage_report.python_coverage({}, Path(tmp), None)
            rc = (Path(tmp) / "coveragerc").read_text(encoding="utf-8")
        self.assertIn(str(PIPELINE), rc)


if __name__ == "__main__":
    unittest.main()
