import importlib.util
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
spec = importlib.util.spec_from_file_location("action_json_test", ACTION)
action = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = action
spec.loader.exec_module(action)


class JsonOutputTests(unittest.TestCase):
    def test_unknown_argument_never_echoes_secret(self):
        secret = "ghp_" + "A" * 36
        for entrypoint in (ACTION, BOOTSTRAP):
            with self.subTest(entrypoint=entrypoint.name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                env = {**os.environ, "GITHUB_WORKSPACE": temp, "GITHUB_OUTPUT": str(root / "output"),
                       "GITHUB_STEP_SUMMARY": str(root / "summary")}
                run = subprocess.run([sys.executable, "-I", str(entrypoint), "--unknown-" + secret],
                                     cwd=root, env=env, capture_output=True, text=True)
                self.assertEqual(run.returncode, 2)
                self.assertFalse((root / "report.json").exists())
                self.assertNotIn(secret, run.stdout + run.stderr)

    def test_explicit_json_path_and_safe_invalid_adapter(self):
        secret = "ghp_" + "A" * 36
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outputs, summary = root / "outputs", root / "summary"
            env = {**os.environ, "GITHUB_OUTPUT": str(outputs), "GITHUB_STEP_SUMMARY": str(summary)}
            run = subprocess.run([sys.executable, "-I", str(ACTION), "--repo-root", temp,
                                  "--config-adapter", secret, "--report-json-path", "nested/result.json"],
                                 env=env, capture_output=True, text=True)
            document = json.loads((root / "nested/result.json").read_text())
            self.assertEqual(run.returncode, 2)
            self.assertEqual(document["analysis_status"], "error")
            self.assertIsNone(document["summary"]["base_cost_usd"])
            self.assertEqual(document["analyses"], [])
            self.assertNotIn(secret, json.dumps(document) + run.stdout + run.stderr)
            self.assertIn("report-json-path=" + str((root / "nested/result.json").resolve()), outputs.read_text())
            self.assertEqual((root / "report.md").read_text(), summary.read_text())

    def test_conflicting_output_paths_produce_error_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report, machine, error = action.resolve_output_paths(root, "same.json", "same.json")
            self.assertIsNotNone(error)
            self.assertEqual(report, root / "report.md")
            self.assertEqual(machine, root / "report.json")

    def test_combined_totals_do_not_hide_small_cost_change(self):
        base = {"epochs": 1, "gpu_type": "T4", "gpu_count": 1, "estimated_minutes_per_epoch": 0.84}
        head = {**base, "estimated_minutes_per_epoch": 0.846}
        result = action.analyze_configs(action.normalize_training_config(base), action.normalize_training_config(head),
                                        gpu_hourly_prices={"T4": 1})
        totals = action.render_combined_totals([action.ConfigReport("config.json", "", result)])
        self.assertIn("$0.014", totals[-3])
        self.assertIn("$0.0141", totals[-2])

    def test_bootstrap_failure_writes_safe_json(self):
        spec = importlib.util.spec_from_file_location("bootstrap_json_test", BOOTSTRAP)
        bootstrap = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = bootstrap
        spec.loader.exec_module(bootstrap)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = {"GITHUB_OUTPUT": str(root / "output"), "GITHUB_STEP_SUMMARY": str(root / "summary")}
            argv = [str(BOOTSTRAP), "--repo-root", temp, "--report-json-path", "failure.json"]
            with patch.dict(os.environ, env), patch.object(sys, "argv", argv), patch.object(
                    bootstrap.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pip", stderr="private registry credential")):
                self.assertEqual(bootstrap.main(), 2)
            document = json.loads((root / "failure.json").read_text())
            self.assertEqual(document["analysis_status"], "error")
            self.assertIsNone(document["summary"]["pr_cost_usd"])
            self.assertNotIn("private registry credential", json.dumps(document))
            self.assertIn("report-json-path=" + str((root / "failure.json").resolve()), (root / "output").read_text())

    def test_bootstrap_refuses_to_overwrite_config_before_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "config.json"
            config.write_text('{"epochs": 1}')
            run = subprocess.run([sys.executable, "-I", str(BOOTSTRAP), "--repo-root", temp,
                                  "--config-path", "config.json", "--report-json-path", str(config)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(config.read_text(), '{"epochs": 1}')


if __name__ == "__main__":
    unittest.main()
