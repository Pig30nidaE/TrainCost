import json
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
DEMO = ROOT / "examples/huggingface-demo"
ACTION = ROOT / "packages/github-action/traincost_action.py"


class StaticCliTests(unittest.TestCase):
    def test_static_verifier_runs_offline(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/verify_hf_demo.py")],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: canonical config", result.stdout)
        self.assertIn("KNOWN_LIMITATION:", result.stdout)
        self.assertIn("NOT RUN: model download, training, GPU measurement", result.stdout)

    def test_verifier_accepts_live_pr_config(self):
        spec = importlib.util.spec_from_file_location("static_verifier_test", ROOT / "scripts/verify_hf_demo.py")
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        original_read = verifier.read_json
        pr = original_read(DEMO / "fixtures/risky.json")
        def read(path):
            return pr if path == DEMO / "config.json" else original_read(path)
        with patch.object(verifier, "read_json", side_effect=read), contextlib.redirect_stdout(io.StringIO()):
            verifier.main()

    def test_actual_action_cli_report_and_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report, output, summary = (root / x for x in ("report.md", "outputs", "summary.md"))
            token = "hf_" + "A" * 36
            env = {**os.environ, "GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(summary),
                   "GITHUB_TOKEN": token}
            cmd = [sys.executable, "-B", str(ACTION), "--repo-root", str(root),
                   "--base-config", "examples/huggingface-demo/fixtures/base.json",
                   "--head-config", "examples/huggingface-demo/fixtures/risky.json",
                   "--gpu-prices", "RTX3060=1.00", "--comment-mode", "false",
                   "--report-path", str(report)]
            run = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            content = report.read_text()
            self.assertIn("Base branch: $0.10", content)
            self.assertIn("This PR: $0.30", content)
            self.assertIn("Increase: +200%", content)
            self.assertIn("Budget limit exceeded", content)
            self.assertIn("analysis-status=complete", output.read_text())
            self.assertIn("comment-posted=false", output.read_text())
            self.assertEqual(summary.read_text(), content)
            self.assertEqual(report.read_bytes(), (DEMO / "expected-report.md").read_bytes())
            self.assertNotIn(token, run.stdout + run.stderr + content + output.read_text() + summary.read_text())

    def test_actual_action_cli_missing_and_invalid_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base, head, report, output = (root / x for x in ("base.json", "head.json", "report.md", "outputs"))
            env = {**os.environ, "GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": ""}
            base.write_text(json.dumps({"model_name": "distilbert/distilbert-base-uncased"}))
            head.write_text(base.read_text())
            cmd = [sys.executable, "-B", str(ACTION), "--repo-root", str(root), "--base-config", str(base),
                   "--head-config", str(head), "--report-path", str(report), "--comment-mode", "false"]
            run = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0)
            self.assertIn("Low-confidence estimate", report.read_text())
            self.assertIn("analysis-status=complete", output.read_text())
            output.write_text("")
            head.write_text('{"epochs": ')
            run = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 2)
            self.assertIn("analysis-status=error", output.read_text())
            self.assertNotIn("This PR:", report.read_text())


if __name__ == "__main__":
    unittest.main()
