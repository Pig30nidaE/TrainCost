from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from traincost_ci_core import analyze_config_dicts, analyze_configs, format_money, format_money_pair, normalize_training_config

BASE = dict(epochs=2, gpu_type="T4", gpu_count=1, estimated_minutes_per_epoch=10, model_name="base", batch_size=16, precision="bf16")


class ReviewFixes(unittest.TestCase):
    def test_unmodeled_settings_are_reported_without_values(self):
        result = analyze_config_dicts({**BASE, "max_steps": 200}, {**BASE, "max_steps": 400})
        self.assertIn("unsupported_training_settings", {w.code for w in result.warnings})
        self.assertIn("stale_runtime_assumption", {w.code for w in result.warnings})
        self.assertNotIn("400", result.markdown_report)
        self.assertIn("not modeled", result.confidence.reason)

    def test_runtime_changes_with_reused_minutes_warn(self):
        for key, value in (("model_name", "other"), ("batch_size", 32), ("gpu_type", "A100"),
                           ("gpu_count", 2), ("precision", "fp32"), ("dataset_size", 20),
                           ("gradient_checkpointing", True), ("model_name_or_path", "model-v2"),
                           ("max_train_samples", 100), ("tokenizer_name", "tokenizer-v2"),
                           ("dataset_revision", "v2")):
            with self.subTest(key=key):
                result = analyze_config_dicts(BASE, {**BASE, key: value})
                self.assertIn("stale_runtime_assumption", {w.code for w in result.warnings})
                self.assertIn("stale", result.confidence.reason)
                self.assertNotIn("No major cost risk detected", result.markdown_report)

    def test_tokenizer_values_still_follow_secret_redaction(self):
        secret = "hf_" + "a" * 36
        result = analyze_config_dicts(BASE, {**BASE, "tokenizer_name": secret})
        self.assertNotIn(secret, repr(result))
        self.assertIn("sensitive_config_value", {w.code for w in result.warnings})

    def test_changed_runtime_with_fresh_minutes_does_not_trigger_stale(self):
        result = analyze_config_dicts(BASE, {**BASE, "model_name": "other", "estimated_minutes_per_epoch": 11})
        self.assertNotIn("stale_runtime_assumption", {w.code for w in result.warnings})

    def test_normalized_api_preserves_and_filters_runtime_metadata(self):
        config = normalize_training_config({**BASE, "max_steps": 5})
        config = replace(config, runtime_conditions={**config.runtime_conditions, "password": "x", "fsdp": "bad"})
        result = analyze_configs(config, config)
        self.assertEqual(set(result.pr_config.runtime_conditions), {"max_steps"})
        self.assertIn("unsupported_training_settings", {w.code for w in result.warnings})

    def test_money_subcent_and_ambiguous_budget(self):
        self.assertEqual(format_money(0), "$0.00")
        self.assertEqual(format_money(0.00001), "$0.00001")
        self.assertEqual(format_money(1.234), "$1.23")
        self.assertNotEqual(*format_money_pair(1.234, 1.233))
        config = {**BASE, "epochs": 1, "estimated_minutes_per_epoch": 60, "budget_limit_usd": 1.233}
        result = analyze_config_dicts(config, config, gpu_hourly_prices={"T4": 1.234})
        warning = next(w for w in result.warnings if w.code == "budget_exceeded")
        self.assertIn("$1.234", warning.what_changed)
        self.assertIn("$1.233", warning.what_changed)
        subcent = analyze_config_dicts(config, config, gpu_hourly_prices={"T4": 0.0001})
        self.assertIn("$0.0001/hour", subcent.markdown_report)
        self.assertIn("This PR: $0.0001", subcent.markdown_report)
