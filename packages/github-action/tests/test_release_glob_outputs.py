"""Protect possible config inputs before Git selection and bootstrap setup."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ACTION = Path(__file__).resolve().parents[1] / "traincost_action.py"


class GlobOutputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.outer = Path(self.temp.name).resolve()
        self.repo = self.outer / "consumer"
        self.repo.mkdir()
        self.env = {**os.environ, "GITHUB_OUTPUT": str(self.outer / "output"),
                    "GITHUB_STEP_SUMMARY": str(self.outer / "summary"), "GITHUB_EVENT_PATH": ""}

    def invoke(self, *args):
        return subprocess.run([sys.executable, "-I", str(ACTION), "--repo-root", str(self.repo),
                               "--event-name", "push", *args], cwd=self.repo,
                              env=self.env, capture_output=True, text=True, timeout=30)

    def test_existing_glob_matched_report_is_preserved(self):
        report = self.repo / "report.md"
        machine = self.repo / "report.json"
        report.write_text("existing markdown")
        machine.write_text('{"epochs": 3}')
        run = self.invoke("--config-path", "**/*.{yaml,json}")
        self.assertEqual(run.returncode, 2)
        self.assertEqual(report.read_text(), "existing markdown")
        self.assertEqual(machine.read_text(), '{"epochs": 3}')

    def test_existing_report_outside_config_glob_can_be_regenerated(self):
        for _ in range(2):
            run = self.invoke("--config-path", "configs/*.json")
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads((self.repo / "report.json").read_text())["analysis_status"], "skipped")

    def test_explicit_external_report_is_not_matched_by_repo_glob(self):
        machine = self.outer / "report.json"
        machine.write_text("previous external output")
        run = self.invoke("--config-path", "*.json", "--report-json-path", str(machine))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(machine.read_text())["analysis_status"], "skipped")


if __name__ == "__main__":
    unittest.main()
