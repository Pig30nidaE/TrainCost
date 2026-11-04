from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from traincost_ci_core import analyze_config_dicts, normalize_training_config, parse_config_text
from traincost_ci_core.safety import ConfigError, MAX_CONFIG_BYTES

BASE = dict(epochs=5, gpu_type="T4", gpu_count=1, estimated_minutes_per_epoch=1.5)
SECRET = "ghp_" + "A" * 36


class BoundaryTests(unittest.TestCase):
    def test_numeric_boundaries_all_formats(self):
        for field in ("epochs", "max_epochs", "gpu_count", "batch_size", "global_batch_size", "dataset_size", "estimated_minutes_per_epoch", "budget_limit_usd"):
            for bad in (-1, "nan", "inf", "-inf", True, "1e999", {}, ""):
                for fmt, text in (("json", json.dumps({field: bad})), ("py", f"{field} = {bad!r}"), ("yaml", json.dumps({field: bad}))):
                    with self.subTest(field=field, bad=bad, fmt=fmt), self.assertRaises(ConfigError):
                        normalize_training_config(parse_config_text(text, fmt))

    def test_integer_counts_do_not_truncate(self):
        for field in ("gpu_count", "batch_size", "global_batch_size", "dataset_size"):
            for bad in (0, 1.8):
                with self.subTest(field=field, bad=bad), self.assertRaises(ConfigError):
                    analyze_config_dicts(BASE, {**BASE, field: bad})

    def test_fractional_epochs_preserved(self):
        result = analyze_config_dicts(BASE, {**BASE, "epochs": 2.9})
        self.assertEqual(result.pr_config.epochs, 2.9)
        self.assertAlmostEqual(result.pr_estimate.estimated_cost_usd, 2.9 * 1.5 / 60 * .35)

    def test_zero_epoch_time_and_epochs_rejected(self):
        for field in ("epochs", "estimated_minutes_per_epoch"):
            with self.assertRaises(ConfigError):
                analyze_config_dicts(BASE, {**BASE, field: 0})

    def test_overflow_is_diagnostic(self):
        with self.assertRaisesRegex(ConfigError, "overflow"):
            analyze_config_dicts(BASE, {**BASE, "epochs": 1e308, "estimated_minutes_per_epoch": 1e308})

    def test_all_public_numeric_options_validate(self):
        for opts in ({"default_budget_limit_usd": math.nan}, {"gpu_hourly_prices": {"T4": math.inf}}, {"cost_increase_threshold_percent": math.nan}):
            with self.subTest(opts=opts), self.assertRaises(ConfigError):
                analyze_config_dicts(BASE, BASE, **opts)

    def test_threshold_edges_and_decrease(self):
        for epochs, expected in ((14.9, False), (15, False), (15.1, True), (5, False)):
            result = analyze_config_dicts({**BASE, "epochs": 10}, {**BASE, "epochs": epochs})
            self.assertEqual("cost_increase" in {w.code for w in result.warnings}, expected)

    def test_budget_edges_and_free_price(self):
        result = analyze_config_dicts(BASE, BASE)
        cost = result.pr_estimate.estimated_cost_usd
        for budget, expected in ((cost, False), (cost / 2, True), (cost * 2, False), (0, True)):
            result = analyze_config_dicts(BASE, {**BASE, "budget_limit_usd": budget})
            self.assertEqual("budget_exceeded" in {w.code for w in result.warnings}, expected)
        free = analyze_config_dicts(BASE, BASE, gpu_hourly_prices={"T4": 0})
        self.assertIsNone(free.increase_percent)

    def test_secret_excluded_before_diff_and_metadata(self):
        for field in ("api_key", "model_name", "model", "gpu_type", "precision"):
            for on_base in (True, False):
                dirty = {**BASE, field: SECRET, "credentials": {"model_name": SECRET}}
                result = analyze_config_dicts(dirty if on_base else BASE, BASE if on_base else dirty)
                self.assertNotIn(SECRET, repr(result))
                self.assertIn("Sensitive-looking", result.markdown_report)

    def test_parse_errors_do_not_include_input(self):
        for fmt, text in (("yaml", "api_key: [" + SECRET), ("json", '{"api_key": "' + SECRET), ("py", 'api_key = "' + SECRET)):
            with self.subTest(fmt=fmt), self.assertRaises(ConfigError) as caught:
                parse_config_text(text, fmt)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_duplicate_keys_all_formats(self):
        for fmt, text in (("yaml", "epochs: 1\nepochs: 2"), ("json", '{"epochs":1,"epochs":2}'), ("py", 'config={"epochs":1,"epochs":2}'), ("py", 'epochs=1\nepochs=2')):
            with self.subTest(fmt=fmt), self.assertRaises(ConfigError):
                parse_config_text(text, fmt)

    def test_ambiguous_fields_and_list_experiments_rejected(self):
        for cfg in ({"eval": {"batch_size": 128}, "training": {"batch_size": 4}}, {"epochs": 5, "max_epochs": 10}, {"experiments": [{"epochs": 5}, {"gpu_type": "T4"}]}):
            with self.assertRaises(ConfigError):
                normalize_training_config(cfg)

    def test_equal_fields_keep_all_sources(self):
        config = normalize_training_config({"a": {"epochs": "5"}, "b": {"epochs": 5}, "max_epochs": 5})
        self.assertEqual(config.field_sources["epochs"], ("a.epochs", "b.epochs"))

    def test_missing_and_unknown_prices_show_assumptions(self):
        missing = analyze_config_dicts({}, {})
        self.assertEqual(missing.confidence.level, "Low")
        self.assertIn("minutes/epoch=30", missing.markdown_report)
        self.assertIn("defaulted fields:", missing.markdown_report)
        unknown = analyze_config_dicts(BASE, {**BASE, "gpu_type": "unlisted"})
        self.assertEqual(unknown.confidence.level, "Medium")
        self.assertIn("not billing accuracy", unknown.markdown_report)

    def test_yaml_cycles_depth_and_size(self):
        cases = ["x: &x\n  child: *x", "x: " + "[" * 50 + "0" + "]" * 50, "x: " + "a" * MAX_CONFIG_BYTES, "x: &x {epochs: 1}\ny: {<<: *x}"]
        for text in cases:
            with self.assertRaises(ConfigError):
                parse_config_text(text, "yaml")

    def test_missing_yaml_dependency_is_explicit(self):
        with patch.dict(sys.modules, {"yaml": None}), self.assertRaisesRegex(ConfigError, "requires PyYAML"):
            parse_config_text("epochs: 5", "yaml")

    def test_python_never_executes_expressions(self):
        for text in ('epochs = 5 * 2', 'import os\nos.system("false")', 'epochs = int("5")'):
            with self.assertRaises(ConfigError):
                parse_config_text(text, "py")

    def test_equivalent_formats(self):
        texts = {"yaml": "epochs: 5\ngpu_type: T4\ngpu_count: 1\nestimated_minutes_per_epoch: 1.5", "json": json.dumps(BASE), "py": f"config = {BASE!r}"}
        for fmt, text in texts.items():
            config = normalize_training_config(parse_config_text(text, fmt))
            self.assertEqual(config.epochs, 5)
            self.assertEqual(config.gpu_type, "T4")

    def test_markdown_cannot_inject_image_or_heading(self):
        value = 'model\n# heading ![x](https://example.invalid/leak) <script>x</script>'
        result = analyze_config_dicts(BASE, {**BASE, "model_name": value})
        self.assertNotIn("\n# heading", result.markdown_report)
        self.assertNotIn("![x]", result.markdown_report)
        self.assertNotIn("<script>", result.markdown_report)
