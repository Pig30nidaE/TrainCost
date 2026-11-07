"""Independent report-oracle regressions; no model or GPU is used."""

from dataclasses import replace
from decimal import Decimal
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch


DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO))
sys.path.insert(0, str(DEMO.parents[1] / "packages/core/src"))
import run_validation
from traincost_ci_core import analyze_config_files


def inject_action_override(change):
    """Wrap the dynamically loaded action while leaving the real analysis intact."""
    original = importlib.util.spec_from_file_location
    def factory(*args, **kwargs):
        spec = original(*args, **kwargs)
        execute = spec.loader.exec_module
        def load(module):
            execute(module)
            change(module)
        spec.loader.exec_module = load
        return spec
    return patch.object(run_validation.importlib.util, "spec_from_file_location", side_effect=factory)


class SubcentCalibrationTests(unittest.TestCase):
    def test_calibration_handles_subcent_half_cent_cent_and_fixture(self):
        for seconds in (0.036, 2.4, 17.999, 18.0, 18.001, 24.0, 35.999, 36.0, 36.001, 360.0):
            with self.subTest(seconds=seconds), tempfile.TemporaryDirectory() as temp:
                workspace = Path(temp)
                with patch.object(run_validation, "timed_training", return_value={"training_seconds": seconds}):
                    run_validation.calibrate(workspace, {"artifacts": {}})
                result = json.loads((workspace / "calibration.json").read_text())
                self.assertEqual(result["median_seconds"], seconds)
                expected = Decimal(str(seconds)) / Decimal(3600)
                analysis = analyze_config_files(workspace / "measured-base.json", workspace / "measured-pr.json",
                                                gpu_hourly_prices={"RTX3060": 1.0})
                report = (workspace / "report.md").read_text()
                for label, factor, numeric in (("Base branch", 1, analysis.base_estimate.estimated_cost_usd),
                                               ("This PR", 3, analysis.pr_estimate.estimated_cost_usd)):
                    lines = [line for line in report.splitlines() if line.startswith(f"- {label}: ")]
                    self.assertEqual(len(lines), 1)
                    match = re.fullmatch(r"- " + re.escape(label) + r": \$([0-9,]+\.\d{2,})", lines[0])
                    self.assertIsNotNone(match, lines[0])
                    shown = Decimal(match.group(1).replace(",", ""))
                    target = expected * factor
                    self.assertTrue(math.isclose(numeric, float(target), rel_tol=1e-12, abs_tol=0))
                    if target < Decimal("0.01"):
                        self.assertGreater(shown, 0)
                        self.assertTrue(math.isclose(float(shown), float(target), rel_tol=1e-12, abs_tol=0))
                    else:
                        self.assertEqual(shown, Decimal(str(numeric)).quantize(Decimal("0.01")))

    def test_rejects_cost_line_that_only_matches_a_prefix(self):
        def mutate(module):
            original = module.run_local_pair
            def altered(*args, **kwargs):
                outcome = original(*args, **kwargs)
                return replace(outcome, report=outcome.report.replace("- Base branch: $0.10\n", "- Base branch: $0.100001\n"))
            module.run_local_pair = altered
        with tempfile.TemporaryDirectory() as temp, inject_action_override(mutate):
            base, pr = Path(temp) / "base.json", Path(temp) / "pr.json"
            base.write_text((DEMO / "fixtures/base.json").read_text())
            pr.write_text((DEMO / "fixtures/risky.json").read_text())
            with self.assertRaises(run_validation.DemoError):
                run_validation.action_report(base, pr)

    def test_rejects_incorrect_machine_readable_summary(self):
        def mutate(module):
            original = module.report_envelope
            def altered(outcome):
                document = original(outcome)
                document["summary"]["pr_cost_usd"] = 9876.5
                return document
            module.report_envelope = altered
        with tempfile.TemporaryDirectory() as temp, inject_action_override(mutate):
            base, pr = Path(temp) / "base.json", Path(temp) / "pr.json"
            base.write_text((DEMO / "fixtures/base.json").read_text())
            pr.write_text((DEMO / "fixtures/risky.json").read_text())
            with self.assertRaises(run_validation.DemoError):
                run_validation.action_report(base, pr)

    def test_rejects_incorrect_per_analysis_numeric_value(self):
        def mutate(module):
            original = module.report_envelope
            def altered(outcome):
                document = original(outcome)
                document["analyses"][0]["pr"]["estimate"]["estimated_cost_usd"] = 0.31
                return document
            module.report_envelope = altered
        with tempfile.TemporaryDirectory() as temp, inject_action_override(mutate):
            base, pr = Path(temp) / "base.json", Path(temp) / "pr.json"
            base.write_text((DEMO / "fixtures/base.json").read_text())
            pr.write_text((DEMO / "fixtures/risky.json").read_text())
            with self.assertRaises(run_validation.DemoError):
                run_validation.action_report(base, pr)

    def test_unequal_cent_rounded_costs_must_be_disambiguated(self):
        run_validation._verify_cost_display("- Base branch: $1.234\n- This PR: $1.233\n", [1.234, 1.233])
        with self.assertRaises(ValueError):
            run_validation._verify_cost_display("- Base branch: $1.23\n- This PR: $1.23\n", [1.234, 1.233])

    def test_regular_costs_keep_two_decimal_places(self):
        with self.assertRaises(ValueError):
            run_validation._verify_cost_display("- Base branch: $0.1000\n- This PR: $0.30\n", [0.1, 0.3])


if __name__ == "__main__":
    unittest.main()
