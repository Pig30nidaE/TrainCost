"""Output-path checks for Action success, error, and setup failure."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ACTION = Path(__file__).resolve().parents[1] / "traincost_action.py"
BOOTSTRAP = ACTION.with_name("bootstrap.py")


class ActionOutputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.outer = Path(self.temp.name).resolve()
        self.repo = self.outer / "consumer"
        self.repo.mkdir()
        self.sentinel = self.outer / "outside.json"
        self.sentinel.write_text("outside must remain intact", encoding="utf-8")
        self.original = self.sentinel.read_bytes()
        self.report = self.repo / "report.md"
        self.report.write_text("existing report", encoding="utf-8")
        self.report_before = self.report.read_bytes()
        self.output = self.repo / "report.json"

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Test",
                               "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false", *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def event_for_changed_pr(self):
        self.git("init", "-q")
        config = self.repo / "config.json"
        config.write_text(json.dumps({"epochs": 1, "gpu_type": "T4", "gpu_count": 1,
                                      "estimated_minutes_per_epoch": 6}), encoding="utf-8")
        self.git("add", "config.json")
        self.git("commit", "-qm", "base")
        base = self.git("rev-parse", "HEAD")
        config.write_text(json.dumps({"epochs": 3, "gpu_type": "T4", "gpu_count": 1,
                                      "estimated_minutes_per_epoch": 6}), encoding="utf-8")
        self.output.symlink_to(self.sentinel)
        self.git("add", "config.json", "report.json")
        self.git("commit", "-qm", "head")
        head = self.git("rev-parse", "HEAD")
        event = self.repo / "event.json"
        event.write_text(json.dumps({"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}))
        return event

    def assert_preserved(self):
        self.assertEqual(self.sentinel.read_bytes(), self.original)
        self.assertEqual(self.report.read_bytes(), self.report_before)

    def test_pr_controlled_json_symlink_cannot_overwrite_external_file(self):
        event = self.event_for_changed_pr()
        env = {**os.environ, "GITHUB_OUTPUT": str(self.repo / "outputs"),
               "GITHUB_STEP_SUMMARY": str(self.repo / "summary")}
        run = subprocess.run([sys.executable, "-I", str(ACTION), "--repo-root", str(self.repo),
                              "--event-name", "pull_request", "--event-path", str(event),
                              "--config-path", "config.json", "--comment-mode", "false"],
                             cwd=self.repo, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 2)
        self.assertNotIn("Traceback", run.stderr)
        self.assert_preserved()

    def test_invalid_input_error_does_not_follow_symlink(self):
        self.output.symlink_to(self.sentinel)
        run = subprocess.run([sys.executable, "-I", str(ACTION), "--repo-root", str(self.repo),
                              "--gpu-prices", "T4=invalid"], cwd=self.repo,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 2)
        self.assertNotIn("Traceback", run.stderr)
        self.assert_preserved()

    def test_bootstrap_setup_failure_does_not_follow_symlink(self):
        self.output.symlink_to(self.sentinel)
        spec = importlib.util.spec_from_file_location("bootstrap_release_safety", BOOTSTRAP)
        bootstrap = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = bootstrap
        spec.loader.exec_module(bootstrap)
        argv = [str(BOOTSTRAP), "--repo-root", str(self.repo)]
        with patch.object(sys, "argv", argv), patch.dict(os.environ, {"GITHUB_OUTPUT": "", "GITHUB_STEP_SUMMARY": ""}), \
                patch.object(bootstrap.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pip")), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bootstrap.main(), 2)
        self.assert_preserved()

    def test_output_parent_symlink_is_rejected(self):
        link = self.repo / "redirect"
        link.symlink_to(self.outer, target_is_directory=True)
        run = subprocess.run([sys.executable, "-I", str(ACTION), "--repo-root", str(self.repo),
                              "--event-name", "push", "--report-json-path", str(link / "outside.json")],
                             cwd=self.repo, capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 2)
        self.assertNotIn("Traceback", run.stderr)
        self.assert_preserved()

    def test_output_hardlink_is_rejected(self):
        os.link(self.sentinel, self.output)
        run = subprocess.run([sys.executable, "-I", str(ACTION), "--repo-root", str(self.repo),
                              "--event-name", "push"], cwd=self.repo, capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 2)
        self.assertNotIn("Traceback", run.stderr)
        self.assert_preserved()

    def test_explicit_external_regular_output_is_supported(self):
        report = self.outer / "external.md"
        machine = self.outer / "external.json"
        run = subprocess.run([sys.executable, "-I", str(ACTION), "--repo-root", str(self.repo),
                              "--event-name", "push", "--report-path", str(report),
                              "--report-json-path", str(machine)], cwd=self.repo,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(machine.read_text())["analysis_status"], "skipped")
        self.assertIn(r"requires a pull\_request event", report.read_text())
        self.assert_preserved()


if __name__ == "__main__":
    unittest.main()
