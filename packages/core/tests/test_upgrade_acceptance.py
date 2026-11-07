"""Independent acceptance tests for report safety and the opt-in HF adapter."""

from decimal import Decimal
from dataclasses import replace
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from traincost_ci_core import analyze_config_dicts, analyze_config_files, analyze_configs, load_config_file, normalize_training_config


BASE = {
    "model_name": "distilbert/distilbert-base-uncased", "epochs": 2,
    "batch_size": 16, "precision": "bf16", "mixed_precision": True,
    "dataset_size": 1000, "gpu_type": "T4", "gpu_count": 1,
    "estimated_minutes_per_epoch": 30,
}
TOKEN = "hf_" + "A" * 36


def warning_text(result):
    return " ".join(" ".join((w.code, w.title, w.what_changed, w.why_it_matters, w.how_to_reduce_risk))
                    for w in result.warnings).lower()


def money_values(text):
    return [Decimal(value) for value in re.findall(r"\$([0-9]+(?:\.[0-9]+)?)", text)]


class CanonicalReviewAcceptance(unittest.TestCase):
    def test_changed_unsupported_hf_fields_cannot_be_clean(self):
        original = {**BASE, "num_train_epochs": 2, "max_steps": 100,
                    "per_device_train_batch_size": 16, "world_size": 1, "bf16": True}
        changed = {**original, "num_train_epochs": 20, "max_steps": 10000,
                   "per_device_train_batch_size": 1, "world_size": 8, "bf16": False}
        result = analyze_config_dicts(original, changed, gpu_hourly_prices={"T4": 2})
        self.assertAlmostEqual(result.pr_estimate.estimated_cost_usd, 2.0)
        self.assertNotIn("No major cost risk detected.", result.markdown_report)
        text = warning_text(result)
        self.assertTrue(any(word in text for word in ("unsupported", "unrecognized", "not supported")), text)
        self.assertTrue(any(key in text for key in ("max_steps", "num_train_epochs", "per_device_train_batch_size")), text)

    def test_canonical_default_does_not_translate_hf_epoch_alias(self):
        raw = {**BASE, "num_train_epochs": 12}
        result = analyze_config_dicts(raw, raw)
        self.assertEqual(result.pr_config.effective_epochs, 2)
        self.assertTrue(any(word in warning_text(result) for word in ("unsupported", "unrecognized", "not supported")))

    def test_analyze_configs_preserves_normalized_unsupported_diagnostics(self):
        normalized = normalize_training_config({**BASE, "num_train_epochs": 12}, adapter="canonical")
        result = analyze_configs(normalized, normalized)
        self.assertTrue(any(word in warning_text(result) for word in ("unsupported", "unrecognized", "not supported")))
        self.assertNotIn("No major cost risk detected.", result.markdown_report)

    def test_stale_runtime_detected_for_changed_inputs_with_fixed_minutes(self):
        changes = ({"dataset_size": 10000}, {"batch_size": 8}, {"model_name": "another-model"},
                   {"gpu_type": "A100"}, {"gpu_count": 2}, {"precision": "fp32", "mixed_precision": False})
        for change in changes:
            with self.subTest(change=change):
                result = analyze_config_dicts(BASE, {**BASE, **change})
                text = warning_text(result)
                self.assertIn("runtime", text)
                self.assertTrue(any(word in text for word in ("stale", "reuse", "unchanged", "same", "revalid", "remeasur")), text)
                self.assertNotIn("No major cost risk detected.", result.markdown_report)

    def test_epoch_only_change_does_not_claim_stale_epoch_runtime(self):
        result = analyze_config_dicts(BASE, {**BASE, "epochs": 3})
        self.assertNotIn("stale", warning_text(result))

    def test_new_runtime_value_is_not_treated_as_reused(self):
        result = analyze_config_dicts(BASE, {**BASE, "dataset_size": 10000, "estimated_minutes_per_epoch": 31})
        text = warning_text(result)
        self.assertFalse("runtime" in text and any(x in text for x in ("stale", "reused", "unchanged")), text)

    def test_subcent_and_rounded_budget_comparison_remain_distinguishable(self):
        for seconds, price, budget in ((0.06, 1.0, 0.002), (60, 1.0002, 1.0001)):
            with self.subTest(price=price):
                base = {**BASE, "epochs": 1, "estimated_minutes_per_epoch": seconds,
                        "budget_limit_usd": budget}
                head = {**base, "epochs": 3 if seconds < 1 else 1}
                result = analyze_config_dicts(base, head, gpu_hourly_prices={"T4": price})
                warning = next(w for w in result.warnings if w.code == "budget_exceeded")
                displayed = money_values(warning.what_changed)
                self.assertGreaterEqual(len(displayed), 2, warning.what_changed)
                self.assertGreater(displayed[0], displayed[1], warning.what_changed)
                self.assertGreater(displayed[1], 0)
                cost_line = next(line for line in result.markdown_report.splitlines() if line.startswith("- This PR:"))
                self.assertGreater(money_values(cost_line)[0], 0, cost_line)

    def test_public_money_formatter_preserves_nonzero_subcent(self):
        formatter = importlib.import_module("traincost_ci_core.formatting").format_money
        self.assertEqual(formatter(0), "$0.00")
        self.assertEqual(formatter(1.234), "$1.23")
        self.assertGreater(money_values(formatter(0.001))[0], 0)

    def test_secret_in_unrecognized_field_never_reaches_report_or_analysis_json(self):
        result = analyze_config_dicts(BASE, {**BASE, "max_steps": TOKEN, "credentials": {"api_key": TOKEN}})
        self.assertNotIn(TOKEN, result.markdown_report)
        self.assertIn("sensitive", warning_text(result))
        serialization = importlib.import_module("traincost_ci_core.serialization")
        encoded = json.dumps(serialization.analysis_to_dict(result), allow_nan=False)
        self.assertNotIn(TOKEN, encoded)
        self.assertNotIn('"raw_fields"', encoded)

    def test_handcrafted_config_metadata_is_not_blindly_trusted(self):
        clean = normalize_training_config(BASE)
        forged = replace(clean, raw_fields={"api_key": TOKEN}, source_path=TOKEN,
                         field_sources={"epochs": (TOKEN,)}, sensitive_keys=(TOKEN,),
                         runtime_conditions={TOKEN: TOKEN})
        try:
            result = analyze_configs(clean, forged)
        except ValueError as error:
            self.assertNotIn(TOKEN, str(error))
        else:
            serialization = importlib.import_module("traincost_ci_core.serialization")
            text = result.markdown_report + json.dumps(serialization.analysis_to_dict(result))
            self.assertNotIn(TOKEN, text)
            self.assertNotIn('"raw_fields"', text)

    def test_nested_unsupported_setting_with_mixed_yaml_keys_is_safe(self):
        head = {**BASE, "dataset": {1: "one", "name": "example", "credentials": {"api_key": TOKEN}}}
        try:
            result = analyze_config_dicts(BASE, head)
        except ValueError as error:
            self.assertNotIn(TOKEN, str(error))
        else:
            self.assertNotIn(TOKEN, result.markdown_report)
            self.assertTrue(result.warnings)


class HuggingFaceAdapterAcceptance(unittest.TestCase):
    def test_flat_and_explicit_training_args_preserve_micro_and_global_batch(self):
        metadata = {"model_name": "distilbert/distilbert-base-uncased", "gpu_type": "T4",
                    "gpu_count": 2, "estimated_minutes_per_epoch": 6}
        args = {"num_train_epochs": 2.5, "per_device_train_batch_size": 4,
                "gradient_accumulation_steps": 4, "world_size": 2, "bf16": True, "fp16": False,
                "max_steps": -1}
        for config in ({**metadata, **args}, {**metadata, "training_args": args}):
            with self.subTest(config=config):
                result = analyze_config_dicts(config, config, adapter="huggingface")
                self.assertEqual(result.pr_config.effective_epochs, 2.5)
                self.assertEqual(result.pr_config.batch_size, 4)
                self.assertEqual(result.pr_config.global_batch_size, 32)
                self.assertEqual(result.pr_config.gpu_count, 2)
                self.assertEqual(result.pr_config.precision.lower(), "bf16")
                self.assertTrue(result.pr_config.mixed_precision)

    def test_unsupported_stopping_batch_and_distributed_options_fail_closed(self):
        valid = {"num_train_epochs": 2, "per_device_train_batch_size": 8, "world_size": 1,
                 "gpu_type": "T4", "estimated_minutes_per_epoch": 6}
        bad = ({"max_steps": 100}, {"auto_find_batch_size": True}, {"deepspeed": "config.json"},
               {"fsdp": "full_shard"}, {"bf16": True, "fp16": True},
               {"bf16": True, "precision": "fp32"}, {"epochs": 3}, {"gpu_count": 2}, {"batch_size": 16},
               {"global_batch_size": 999})
        for update in bad:
            with self.subTest(update=update), self.assertRaises(ValueError):
                analyze_config_dicts(valid, {**valid, **update}, adapter="huggingface")

    def test_hf_root_stopping_and_distributed_settings_cannot_bypass_nested_args(self):
        args = {"num_train_epochs": 1, "per_device_train_batch_size": 8, "world_size": 1}
        for extra in ({"max_steps": 100}, {"deepspeed": "config.json"}, {"fsdp": "full_shard"},
                      {"auto_find_batch_size": True}):
            config = {"training_args": args, "gpu_type": "T4", "estimated_minutes_per_epoch": 6, **extra}
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                analyze_config_dicts(config, config, adapter="huggingface")

    def test_missing_world_size_is_not_assumed_to_be_one_for_global_batch(self):
        raw = {"num_train_epochs": 1, "per_device_train_batch_size": 4,
               "gradient_accumulation_steps": 3, "estimated_minutes_per_epoch": 6, "gpu_type": "T4"}
        result = analyze_config_dicts(raw, raw, adapter="huggingface")
        self.assertIsNone(result.pr_config.gpu_count)
        self.assertIsNone(result.pr_config.global_batch_size)
        self.assertEqual(result.confidence.level, "Low")

    def test_equivalent_hf_aliases_compare_after_type_normalization(self):
        raw = {"num_train_epochs": 2, "bf16": True, "world_size": 2,
               "gpu_type": "T4", "estimated_minutes_per_epoch": 6,
               "training_args": {"num_train_epochs": "2", "bf16": "true", "world_size": "2",
                                 "per_device_train_batch_size": 4}}
        result = analyze_config_dicts(raw, raw, adapter="huggingface")
        self.assertEqual(result.pr_config.effective_epochs, 2)
        self.assertEqual(result.pr_config.gpu_count, 2)
        self.assertTrue(result.pr_config.mixed_precision)

    def test_model_metadata_alone_is_not_a_training_config(self):
        metadata = {"model_type": "distilbert", "architectures": ["DistilBertModel"], "torch_dtype": "float32"}
        with self.assertRaises(ValueError):
            analyze_config_dicts(metadata, metadata, adapter="huggingface")

    def test_unsupported_or_invalid_adapter_diagnostic_does_not_echo_secret(self):
        raw = {"num_train_epochs": 1, "per_device_train_batch_size": 8, "max_steps": TOKEN}
        with self.assertRaises(ValueError) as error:
            analyze_config_dicts(raw, raw, adapter="huggingface")
        self.assertNotIn(TOKEN, str(error.exception))
        with self.assertRaises(ValueError) as error:
            analyze_config_dicts(BASE, BASE, adapter=TOKEN)
        self.assertNotIn(TOKEN, str(error.exception))

    def test_file_and_normalized_config_paths_keep_adapter_metadata(self):
        raw = {"training_args": {"num_train_epochs": 2, "per_device_train_batch_size": 4,
                                 "gradient_accumulation_steps": 2, "world_size": 2, "bf16": True},
               "gpu_type": "T4", "estimated_minutes_per_epoch": 6}
        normalized = normalize_training_config(raw, adapter="huggingface")
        result = analyze_configs(normalized, normalized)
        self.assertEqual(result.pr_config.global_batch_size, 16)
        self.assertEqual(result.pr_config.precision.lower(), "bf16")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            loaded = load_config_file(path, adapter="huggingface")
            from_files = analyze_config_files(path, path, adapter="huggingface")
        self.assertEqual(loaded.global_batch_size, 16)
        self.assertEqual(from_files.pr_config.global_batch_size, 16)
        self.assertEqual(from_files.pr_config.precision.lower(), "bf16")


class CoreCliAcceptance(unittest.TestCase):
    def test_module_cli_writes_safe_json_with_unrounded_estimates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base, head = root / "base.json", root / "head.json"
            base.write_text(json.dumps({**BASE, "epochs": 1, "estimated_minutes_per_epoch": .06, "budget_limit_usd": .002}))
            head.write_text(json.dumps({**BASE, "epochs": 3, "estimated_minutes_per_epoch": .06,
                                        "budget_limit_usd": .002, "api_key": TOKEN}))
            report, machine = root / "report.md", root / "result.json"
            env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
            cmd = [sys.executable, "-B", "-m", "traincost_ci_core", "--base-config", str(base),
                   "--head-config", str(head), "--gpu-prices", "T4=1", "--report-path", str(report),
                   "--json-path", str(machine)]
            run = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            data = json.loads(machine.read_text())
            self.assertEqual(data["schema_version"], "1.0")
            self.assertEqual(data["analysis_status"], "complete")
            from jsonschema import Draft202012Validator
            schema_path = Path(__file__).resolve().parents[3] / "docs/schemas/report-v1.schema.json"
            schema = json.loads(schema_path.read_text())
            Draft202012Validator.check_schema(schema)
            self.assertEqual(list(Draft202012Validator(schema).iter_errors(data)), [])
            self.assertAlmostEqual(data["summary"]["base_cost_usd"], 0.001)
            self.assertAlmostEqual(data["summary"]["pr_cost_usd"], 0.003)
            self.assertNotIn(TOKEN, run.stdout + run.stderr + report.read_text() + machine.read_text())
            self.assertNotIn('"raw_fields"', machine.read_text())
            self.assertNotIn("$0.00, above the $0.00", report.read_text())

    def test_module_cli_rejects_output_equal_to_input_without_overwrite(self):
        for target in ("base", "symlink", "hardlink"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                base, head = root / "base.json", root / "head.json"
                base.write_text(json.dumps(BASE))
                head.write_text(json.dumps({**BASE, "epochs": 3}))
                original = base.read_bytes()
                destination = base if target == "base" else root / "alias.json"
                if target == "symlink":
                    destination.symlink_to(base)
                elif target == "hardlink":
                    os.link(base, destination)
                env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
                cmd = [sys.executable, "-B", "-m", "traincost_ci_core", "--base-config", str(base),
                       "--head-config", str(head), "--report-path", str(root / "report.md"), "--json-path", str(destination)]
                run = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(base.read_bytes(), original, "JSON output overwrote an input config")
                self.assertEqual(run.returncode, 2)

    def test_cli_argument_error_never_overwrites_default_named_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base, head = root / "report.json", root / "head.json"
            base.write_text(json.dumps(BASE))
            head.write_text(json.dumps({**BASE, "epochs": 3}))
            original = base.read_bytes()
            env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
            cmd = [sys.executable, "-B", "-m", "traincost_ci_core", "--base-config", str(base),
                   "--head-config", str(head), "--unknown-option", TOKEN]
            run = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn(TOKEN, run.stdout + run.stderr)
            self.assertEqual(base.read_bytes(), original, "argument error overwrote the input config")


if __name__ == "__main__":
    unittest.main()
