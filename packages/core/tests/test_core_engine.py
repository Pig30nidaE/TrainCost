from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from traincost_ci_core import (  # noqa: E402
    analyze_config_dicts,
    analyze_config_files,
    estimate_cost,
    load_config_file,
    parse_config_text,
)


class ConfigParsingTests(unittest.TestCase):
    def test_loads_yaml_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                """
                model_name: resnet50
                training:
                  epochs: 5
                  batch_size: 64
                  precision: bf16
                  mixed_precision: true
                resources:
                  gpu_type: T4
                  gpu_count: 1
                estimated_minutes_per_epoch: 1.5
                budget_limit_usd: 5.00
                """,
                encoding="utf-8",
            )

            config = load_config_file(config_path)

        self.assertEqual(config.model_name, "resnet50")
        self.assertEqual(config.epochs, 5)
        self.assertEqual(config.batch_size, 64)
        self.assertEqual(config.precision, "bf16")
        self.assertTrue(config.mixed_precision)
        self.assertEqual(config.gpu_type, "T4")
        self.assertEqual(config.gpu_count, 1)
        self.assertEqual(config.estimated_minutes_per_epoch, 1.5)
        self.assertEqual(config.budget_limit_usd, 5.0)

    def test_invalid_yaml_raises_value_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid YAML"):
            parse_config_text("epochs: [1, 2", "yaml")

    def test_loads_json_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "model": "bert-large",
                        "max_epochs": 10,
                        "global_batch_size": 16,
                        "precision": "fp16",
                        "mixed_precision": True,
                        "gpu_type": "A100",
                        "gpu_count": 2,
                        "estimated_minutes_per_epoch": 4,
                    }
                ),
                encoding="utf-8",
            )

            config = load_config_file(config_path)

        self.assertEqual(config.model, "bert-large")
        self.assertEqual(config.max_epochs, 10)
        self.assertEqual(config.effective_epochs, 10)
        self.assertEqual(config.global_batch_size, 16)
        self.assertEqual(config.gpu_type, "A100")
        self.assertEqual(config.gpu_count, 2)

    def test_loads_simple_python_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.py"
            config_path.write_text(
                textwrap.dedent(
                    """
                model_name = "llama-13b"
                epochs = 8
                batch_size = 4
                precision = "fp32"
                mixed_precision = False
                resources = {"gpu_type": "A100", "gpu_count": 2}
                estimated_minutes_per_epoch: float = 12.5
                """
                ),
                encoding="utf-8",
            )

            config = load_config_file(config_path)

        self.assertEqual(config.model_name, "llama-13b")
        self.assertEqual(config.epochs, 8)
        self.assertEqual(config.batch_size, 4)
        self.assertEqual(config.precision, "fp32")
        self.assertFalse(config.mixed_precision)
        self.assertEqual(config.gpu_type, "A100")
        self.assertEqual(config.gpu_count, 2)
        self.assertEqual(config.estimated_minutes_per_epoch, 12.5)


class EstimationTests(unittest.TestCase):
    def test_estimates_gpu_cost_with_formula(self) -> None:
        result = analyze_config_dicts(
            {
                "epochs": 5,
                "estimated_minutes_per_epoch": 6,
                "gpu_count": 2,
                "gpu_type": "T4",
            },
            {
                "epochs": 5,
                "estimated_minutes_per_epoch": 6,
                "gpu_count": 2,
                "gpu_type": "T4",
            },
            gpu_hourly_prices={"T4": 0.50},
        )

        self.assertAlmostEqual(result.pr_estimate.estimated_total_minutes, 30.0)
        self.assertAlmostEqual(result.pr_estimate.estimated_gpu_hours, 1.0)
        self.assertAlmostEqual(result.pr_estimate.estimated_cost_usd, 0.50)

    def test_estimate_cost_defaults_missing_fields(self) -> None:
        result = analyze_config_dicts({}, {})

        self.assertEqual(result.confidence.level, "Low")
        self.assertIn("epochs", result.confidence.missing_fields)
        self.assertIn("estimated_minutes_per_epoch", result.confidence.missing_fields)
        self.assertIn("gpu_type", result.confidence.missing_fields)
        self.assertIn("gpu_count", result.confidence.missing_fields)
        self.assertIn("low_confidence_missing_fields", {warning.code for warning in result.warnings})
        self.assertGreater(result.pr_estimate.estimated_cost_usd, 0)
        self.assertIn("Low-confidence estimate.", result.markdown_report)
        self.assertIn("Missing fields reduce estimate confidence", result.markdown_report)

    def test_direct_estimate_cost_uses_known_gpu_price(self) -> None:
        config = analyze_config_dicts(
            {"epochs": 1, "estimated_minutes_per_epoch": 60, "gpu_count": 1, "gpu_type": "A100"},
            {"epochs": 1, "estimated_minutes_per_epoch": 60, "gpu_count": 1, "gpu_type": "A100"},
        ).pr_config

        estimate = estimate_cost(config)

        self.assertAlmostEqual(estimate.estimated_gpu_hours, 1.0)
        self.assertAlmostEqual(estimate.estimated_cost_usd, 4.10)
        self.assertEqual(estimate.price_source, "known_gpu_type")


class RiskWarningTests(unittest.TestCase):
    def test_detects_budget_exceeded_warning(self) -> None:
        result = analyze_config_dicts(
            {
                "epochs": 1,
                "estimated_minutes_per_epoch": 30,
                "gpu_count": 1,
                "gpu_type": "T4",
            },
            {
                "epochs": 10,
                "estimated_minutes_per_epoch": 60,
                "gpu_count": 1,
                "gpu_type": "A100",
                "budget_limit_usd": 5,
            },
        )

        self.assertIn("budget_exceeded", {warning.code for warning in result.warnings})
        self.assertGreater(result.pr_estimate.estimated_cost_usd, result.pr_config.budget_limit_usd)

    def test_detects_cost_increase_warning(self) -> None:
        result = analyze_config_dicts(
            {
                "epochs": 2,
                "estimated_minutes_per_epoch": 10,
                "gpu_count": 1,
                "gpu_type": "T4",
            },
            {
                "epochs": 4,
                "estimated_minutes_per_epoch": 10,
                "gpu_count": 1,
                "gpu_type": "T4",
            },
        )

        self.assertIn("cost_increase", {warning.code for warning in result.warnings})
        self.assertGreater(result.increase_percent, 50)

    def test_detects_precision_warning(self) -> None:
        result = analyze_config_dicts(
            {
                "epochs": 2,
                "estimated_minutes_per_epoch": 10,
                "gpu_count": 1,
                "gpu_type": "T4",
                "precision": "bf16",
                "mixed_precision": True,
            },
            {
                "epochs": 2,
                "estimated_minutes_per_epoch": 10,
                "gpu_count": 1,
                "gpu_type": "T4",
                "precision": "fp32",
                "mixed_precision": False,
            },
        )

        self.assertIn("precision_risk", {warning.code for warning in result.warnings})

    def test_detects_gpu_and_batch_warnings(self) -> None:
        result = analyze_config_dicts(
            {
                "model_name": "llama-13b",
                "epochs": 5,
                "batch_size": 32,
                "estimated_minutes_per_epoch": 10,
                "gpu_count": 1,
                "gpu_type": "T4",
            },
            {
                "model_name": "llama-13b",
                "epochs": 12,
                "batch_size": 4,
                "estimated_minutes_per_epoch": 10,
                "gpu_count": 2,
                "gpu_type": "A100",
            },
        )

        warning_codes = {warning.code for warning in result.warnings}
        self.assertIn("epochs_increased", warning_codes)
        self.assertIn("gpu_type_more_expensive", warning_codes)
        self.assertIn("gpu_count_increased", warning_codes)
        self.assertIn("small_batch_size", warning_codes)

    def test_sensitive_config_values_are_not_rendered_in_report(self) -> None:
        result = analyze_config_dicts(
            {
                "epochs": 1,
                "estimated_minutes_per_epoch": 5,
                "gpu_count": 1,
                "gpu_type": "T4",
            },
            {
                "epochs": 1,
                "estimated_minutes_per_epoch": 5,
                "gpu_count": 1,
                "gpu_type": "T4",
                "api_key": "super-secret-token",
            },
        )

        warning_codes = {warning.code for warning in result.warnings}
        self.assertIn("sensitive_config_value", warning_codes)
        self.assertIn("api_key", result.markdown_report)
        self.assertNotIn("super-secret-token", result.markdown_report)


class MarkdownReportTests(unittest.TestCase):
    def test_generates_markdown_report(self) -> None:
        result = analyze_config_dicts(
            {
                "epochs": 5,
                "batch_size": 64,
                "precision": "bf16",
                "mixed_precision": True,
                "gpu_type": "T4",
                "gpu_count": 1,
                "estimated_minutes_per_epoch": 1.5,
                "budget_limit_usd": 5,
            },
            {
                "epochs": 50,
                "batch_size": 8,
                "precision": "fp32",
                "mixed_precision": False,
                "gpu_type": "A100",
                "gpu_count": 2,
                "estimated_minutes_per_epoch": 1.5,
                "budget_limit_usd": 5,
            },
        )

        report = result.markdown_report

        self.assertIn("## TrainCost CI Report", report)
        self.assertIn("Cost risk detected.", report)
        self.assertIn("### Changed", report)
        self.assertIn("- epochs: 5 -> 50", report)
        self.assertIn("### Estimated cost", report)
        self.assertIn("- Base branch:", report)
        self.assertIn("- This PR:", report)
        self.assertIn("### Warnings", report)
        self.assertIn("Budget limit exceeded", report)
        self.assertIn("Mixed precision appears disabled", report)
        self.assertIn("### Recommendations", report)
        self.assertIn("### Confidence", report)

    def test_report_uses_estimate_language_without_exact_prediction_claims(self) -> None:
        result = analyze_config_dicts(
            {
                "epochs": 5,
                "estimated_minutes_per_epoch": 3,
                "gpu_count": 1,
                "gpu_type": "T4",
            },
            {
                "epochs": 10,
                "estimated_minutes_per_epoch": 3,
                "gpu_count": 1,
                "gpu_type": "T4",
            },
        )

        report = result.markdown_report.lower()

        self.assertIn("estimated cost", report)
        for forbidden_phrase in (
            "exact cost",
            "exact bill",
            "guaranteed savings",
            "optimal gpu",
            "precise runtime",
        ):
            self.assertNotIn(forbidden_phrase, report)

    def test_analyzes_config_files_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "base.yaml"
            pr_path = Path(tmpdir) / "pr.json"
            base_path.write_text(
                """
                epochs: 1
                estimated_minutes_per_epoch: 10
                gpu_count: 1
                gpu_type: T4
                """,
                encoding="utf-8",
            )
            pr_path.write_text(
                json.dumps(
                    {
                        "epochs": 3,
                        "estimated_minutes_per_epoch": 10,
                        "gpu_count": 1,
                        "gpu_type": "T4",
                    }
                ),
                encoding="utf-8",
            )

            result = analyze_config_files(base_path, pr_path)

        self.assertEqual(result.pr_config.epochs, 3)
        self.assertIn("cost_increase", {warning.code for warning in result.warnings})


if __name__ == "__main__":
    unittest.main()
