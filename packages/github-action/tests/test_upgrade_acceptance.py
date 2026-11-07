"""Subprocess acceptance tests for Action JSON and adapter boundaries."""

import json
import importlib.util
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ACTION = Path(__file__).resolve().parents[1] / "traincost_action.py"
TOKEN = "hf_" + "B" * 36
BASE = {"model_name": "distilbert/distilbert-base-uncased", "epochs": 1, "batch_size": 16,
        "precision": "bf16", "mixed_precision": True, "gpu_type": "T4", "gpu_count": 1,
        "estimated_minutes_per_epoch": 0.06, "budget_limit_usd": 0.002}


class ActionUpgradeAcceptance(unittest.TestCase):
    def invoke(self, root, base, head, *extra, suffix=".json", json_path=True):
        base_path, head_path = root / ("base" + suffix), root / ("head" + suffix)
        base_path.write_text(base if isinstance(base, str) else json.dumps(base), encoding="utf-8")
        head_path.write_text(head if isinstance(head, str) else json.dumps(head), encoding="utf-8")
        report, machine, output, summary = (root / name for name in ("report.md", "explicit.json", "outputs", "summary"))
        env = {**os.environ, "GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(summary),
               "GITHUB_EVENT_NAME": "", "GITHUB_EVENT_PATH": "", "GITHUB_TOKEN": TOKEN}
        cmd = [sys.executable, "-I", str(ACTION), "--repo-root", str(root), "--base-config", str(base_path),
               "--head-config", str(head_path), "--report-path", str(report), "--gpu-prices", "T4=1",
               "--comment-mode", "false", *extra]
        if json_path:
            cmd += ["--report-json-path", str(machine)]
        run = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
        machine = machine if json_path else report.with_suffix(".json")
        content = {name: path.read_text(encoding="utf-8") if path.exists() else ""
                   for name, path in (("report", report), ("machine", machine), ("outputs", output), ("summary", summary))}
        content.update(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr)
        return content

    def assert_safe(self, response):
        for key, value in response.items():
            if isinstance(value, str):
                self.assertNotIn(TOKEN, value, key)
        if response["machine"]:
            self.assertNotIn('"raw_fields"', response["machine"])

    def assert_envelope(self, response, status):
        data = json.loads(response["machine"])
        from jsonschema import Draft202012Validator
        schema_path = ACTION.parents[2] / "docs/schemas/report-v1.schema.json"
        schema = json.loads(schema_path.read_text())
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(data)), [])
        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(data["analysis_status"], status)
        self.assertIsInstance(data["analyses"], list)
        self.assertIsInstance(data["diagnostics"], list)
        self.assertEqual(data["summary"]["scope"], "analyzed_configs_only")
        self.assertIn("analysis-status=" + status, response["outputs"])
        self.assertIn("report-json-path=", response["outputs"])
        self.assertEqual(response["report"], response["summary"])
        self.assert_safe(response)
        return data

    def test_json_keeps_unrounded_costs_while_markdown_is_readable(self):
        with tempfile.TemporaryDirectory() as temp:
            response = self.invoke(Path(temp), BASE, {**BASE, "epochs": 3, "credentials": {"api_key": TOKEN}})
        self.assertEqual(response["returncode"], 0, response["stderr"])
        data = self.assert_envelope(response, "complete")
        self.assertEqual(data["summary"]["analyzed_count"], 1)
        self.assertEqual(data["summary"]["excluded_count"], 0)
        self.assertAlmostEqual(data["summary"]["base_cost_usd"], 0.001)
        self.assertAlmostEqual(data["summary"]["pr_cost_usd"], 0.003)
        self.assertEqual(len(data["analyses"]), 1)
        self.assertNotIn("$0.00, above the $0.00", response["report"])
        self.assertIn("Budget limit exceeded", response["report"])

    def test_default_json_path_and_no_false_clean_unsupported_change(self):
        base = {**BASE, "max_steps": 100, "num_train_epochs": 1}
        head = {**base, "max_steps": 10000, "num_train_epochs": 10}
        with tempfile.TemporaryDirectory() as temp:
            response = self.invoke(Path(temp), base, head, json_path=False)
        self.assertEqual(response["returncode"], 0, response["stderr"])
        self.assert_envelope(response, "complete")
        self.assertNotIn("No major cost risk detected.", response["report"])
        self.assertIn("unsupported", response["report"].lower())

    def test_zero_price_is_numeric_zero_not_missing_cost(self):
        with tempfile.TemporaryDirectory() as temp:
            response = self.invoke(Path(temp), BASE, {**BASE, "epochs": 3}, "--gpu-prices", "T4=0")
        self.assertEqual(response["returncode"], 0, response["stderr"])
        data = self.assert_envelope(response, "complete")
        self.assertEqual(data["summary"]["base_cost_usd"], 0)
        self.assertEqual(data["summary"]["pr_cost_usd"], 0)
        self.assertIsNotNone(data["summary"]["base_cost_usd"])

    def test_skipped_event_has_null_costs_and_no_analyses(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report, machine, output, summary = (root / name for name in ("report.md", "report.json", "outputs", "summary"))
            env = {**os.environ, "GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(summary),
                   "GITHUB_TOKEN": TOKEN, "GITHUB_EVENT_PATH": ""}
            run = subprocess.run([sys.executable, "-I", str(ACTION), "--repo-root", str(root), "--event-name", "push",
                                  "--report-path", str(report), "--comment-mode", "false"],
                                 capture_output=True, text=True, env=env, timeout=30)
            response = {name: path.read_text(encoding="utf-8") if path.exists() else ""
                        for name, path in (("report", report), ("machine", machine), ("outputs", output), ("summary", summary))}
            response.update(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr)
        self.assertEqual(response["returncode"], 0, response["stderr"])
        data = self.assert_envelope(response, "skipped")
        self.assertEqual(data["analyses"], [])
        self.assertIsNone(data["summary"]["base_cost_usd"])
        self.assertIsNone(data["summary"]["pr_cost_usd"])

    def test_huggingface_adapter_normalizes_json_before_estimation(self):
        base = {"model_name": "distilbert/distilbert-base-uncased", "gpu_type": "T4", "gpu_count": 2,
                "estimated_minutes_per_epoch": 30, "training_args": {"num_train_epochs": 2,
                "per_device_train_batch_size": 4, "gradient_accumulation_steps": 4, "world_size": 2,
                "bf16": True, "fp16": False, "max_steps": -1}}
        head = {**base, "training_args": {**base["training_args"], "num_train_epochs": 3}}
        with tempfile.TemporaryDirectory() as temp:
            response = self.invoke(Path(temp), base, head, "--config-adapter", "huggingface")
        self.assertEqual(response["returncode"], 0, response["stderr"])
        data = self.assert_envelope(response, "complete")
        self.assertAlmostEqual(data["summary"]["base_cost_usd"], 2.0)
        self.assertAlmostEqual(data["summary"]["pr_cost_usd"], 3.0)
        self.assertIn("epochs", response["report"])

    def test_positive_hf_max_steps_fails_with_safe_null_costs(self):
        valid = {"num_train_epochs": 1, "per_device_train_batch_size": 8, "world_size": 1,
                 "gpu_type": "T4", "estimated_minutes_per_epoch": 30}
        with tempfile.TemporaryDirectory() as temp:
            response = self.invoke(Path(temp), valid, {**valid, "max_steps": 100, "notes": TOKEN},
                                   "--config-adapter", "huggingface")
        self.assertEqual(response["returncode"], 2)
        data = self.assert_envelope(response, "error")
        self.assertEqual(data["analyses"], [])
        self.assertIsNone(data["summary"]["base_cost_usd"])
        self.assertIsNone(data["summary"]["pr_cost_usd"])
        self.assertTrue(data["diagnostics"])

    def test_invalid_yaml_and_adapter_report_safe_error_json(self):
        for base, head, suffix, flags in (("epochs: [", "epochs: 1", ".yaml", ()),
                                         (BASE, BASE, ".json", ("--config-adapter", TOKEN))):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as temp:
                response = self.invoke(Path(temp), base, head, *flags, suffix=suffix)
                self.assertEqual(response["returncode"], 2)
                data = self.assert_envelope(response, "error")
                self.assertIsNone(data["summary"]["base_cost_usd"])
                self.assertIsNone(data["summary"]["pr_cost_usd"])

    def test_unknown_cli_argument_does_not_echo_secret(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = subprocess.run([sys.executable, "-I", str(ACTION), "--repo-root", str(root),
                                  "--unknown-option", TOKEN], capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 2)
        self.assertNotIn(TOKEN, run.stdout + run.stderr)

    def test_mixed_key_unsupported_yaml_never_crashes_or_leaks(self):
        base = "epochs: 1\ngpu_type: T4\ngpu_count: 1\nestimated_minutes_per_epoch: 5\n"
        head = base + "dataset:\n  1: one\n  name: example\n  credentials:\n    api_key: " + TOKEN + "\n"
        with tempfile.TemporaryDirectory() as temp:
            response = self.invoke(Path(temp), base, head, suffix=".yaml")
        self.assertIn(response["returncode"], (0, 2), response["stderr"])
        self.assertNotIn("Traceback", response["stderr"])
        data = json.loads(response["machine"])
        self.assertIn(data["analysis_status"], ("complete", "error"))
        self.assert_safe(response)
        self.assertEqual(response["summary"], response["report"])

    def test_json_output_cannot_overwrite_input_config(self):
        for target in ("base", "head", "symlink", "hardlink"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                base, head = root / "base.json", root / "head.json"
                base.write_text(json.dumps(BASE), encoding="utf-8")
                head.write_text(json.dumps({**BASE, "epochs": 3}), encoding="utf-8")
                originals = (base.read_bytes(), head.read_bytes())
                destination = {"base": base, "head": head}.get(target, root / "alias.json")
                if target == "symlink":
                    destination.symlink_to(base)
                elif target == "hardlink":
                    os.link(base, destination)
                cmd = [sys.executable, "-I", str(ACTION), "--repo-root", str(root), "--base-config", str(base),
                       "--head-config", str(head), "--report-path", str(root / "report.md"),
                       "--report-json-path", str(destination), "--comment-mode", "false"]
                run = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                self.assertEqual((base.read_bytes(), head.read_bytes()), originals, "JSON output overwrote an input config")
                self.assertEqual(run.returncode, 2)

    def test_partial_envelope_totals_exclude_failed_configs_and_redact_paths(self):
        spec = importlib.util.spec_from_file_location("action_upgrade_acceptance", ACTION)
        action = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = action
        spec.loader.exec_module(action)
        result = action.analyze_configs(action.normalize_training_config(BASE),
                                        action.normalize_training_config({**BASE, "epochs": 3}),
                                        gpu_hourly_prices={"T4": 1.0})
        outcome = action.AnalysisRun("report", "partial", (action.ConfigReport(TOKEN, "report", result),),
                                     diagnostics=("Skipped invalid config.",), excluded_count=1)
        envelope = action.report_envelope(outcome)
        from jsonschema import Draft202012Validator
        schema = json.loads((ACTION.parents[2] / "docs/schemas/report-v1.schema.json").read_text())
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(envelope)), [])
        self.assertEqual(envelope["analysis_status"], "partial")
        self.assertEqual(envelope["summary"]["analyzed_count"], 1)
        self.assertEqual(envelope["summary"]["excluded_count"], 1)
        self.assertAlmostEqual(envelope["summary"]["base_cost_usd"], 0.001)
        self.assertAlmostEqual(envelope["summary"]["pr_cost_usd"], 0.003)
        self.assertNotIn(TOKEN, json.dumps(envelope))

    def test_overflowing_aggregate_returns_safe_error_artifacts(self):
        spec = importlib.util.spec_from_file_location("action_overflow_acceptance", ACTION)
        action = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = action
        spec.loader.exec_module(action)
        config = {"epochs": 1, "gpu_count": 1, "gpu_type": "T4", "estimated_minutes_per_epoch": 60}
        changes = [action.ChangedFile("one.json", "one.json"), action.ChangedFile("two.json", "two.json")]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report, machine, output, summary = (root / name for name in ("report.md", "report.json", "outputs", "summary"))
            env = {"GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(summary)}
            with patch.dict(os.environ, env), patch.object(action, "changed_supported_files", return_value=changes), \
                    patch.object(action, "read_git_file", return_value=json.dumps(config)), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = action.main(["--repo-root", str(root), "--event-name", "pull_request", "--report-path", str(report),
                                    "--config-path", "*.json", "--gpu-prices", "T4=1e308"])
            self.assertEqual(code, 2)
            self.assertTrue(machine.exists(), "aggregate overflow did not produce diagnostic JSON")
            data = json.loads(machine.read_text())
            self.assertEqual(data["analysis_status"], "error")
            self.assertIsNone(data["summary"]["base_cost_usd"])
            self.assertIn("analysis-status=error", output.read_text())
            self.assertEqual(summary.read_text(), report.read_text())


if __name__ == "__main__":
    unittest.main()
