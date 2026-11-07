import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "bootstrap.py"
spec = importlib.util.spec_from_file_location("bootstrap", FILE)
bootstrap = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bootstrap
spec.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def test_unsafe_output_path_is_rejected_before_install(self):
        secret = "ghp_" + "A" * 36
        for value in (secret, "report\nunsafe.md", "report\0unsafe.md"):
            with self.subTest(value=value[:6]), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                env = {"GITHUB_OUTPUT": str(root / "output"), "GITHUB_STEP_SUMMARY": str(root / "summary")}
                argv = [str(FILE), "--repo-root", temp, "--report-path", value]
                with patch.dict(os.environ, env), patch.object(sys, "argv", argv), patch.object(bootstrap.subprocess, "run") as run:
                    self.assertEqual(bootstrap.main(), 2)
                run.assert_not_called()
                for name in ("report.md", "output", "summary"):
                    self.assertNotIn(secret, (root / name).read_text())
                self.assertIn("analysis-status=error", (root / "output").read_text())

    def test_failed_install_is_error_with_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = {"INPUT_REPORT_PATH": str(root / "report.md"), "GITHUB_OUTPUT": str(root / "output"),
                   "GITHUB_STEP_SUMMARY": str(root / "summary"), "INPUT_COMMENT_MODE": "false"}
            with patch.dict(os.environ, env), patch.object(sys, "argv", [str(FILE)]), patch.object(bootstrap.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pip", stderr="private registry credential")):
                self.assertEqual(bootstrap.main(), 2)
            report = (root / "report.md").read_text()
            self.assertNotIn("private registry credential", report)
            self.assertIn("analysis-status=error", (root / "output").read_text())
            self.assertEqual(report, (root / "summary").read_text())

    def test_report_only_child_has_no_token_and_uses_isolated_python(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake", "GH_TOKEN": "fake", "INPUT_COMMENT_MODE": "false"}), patch.object(sys, "argv", [str(FILE)]), patch.object(bootstrap.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(bootstrap.main(), 0)
        for call in run.call_args_list:
            self.assertNotIn("GITHUB_TOKEN", call.kwargs["env"])
            self.assertNotIn("GH_TOKEN", call.kwargs["env"])
            self.assertIn("-I", call.args[0])
