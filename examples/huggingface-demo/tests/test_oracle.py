import importlib.util
import math
from decimal import Decimal
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location("demo_oracle", Path(__file__).resolve().parents[1] / "oracle.py")
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)


class OracleTests(unittest.TestCase):
    def test_independent_decimal_formula(self):
        self.assertEqual(oracle.decimal_cost(1, 6), Decimal("0.10"))
        self.assertEqual(oracle.decimal_cost(3, 6, 1, "1.00"), Decimal("0.30"))
        self.assertEqual(oracle.decimal_cost("2.5", "3", 2, "0.60"), Decimal("0.15"))
        self.assertEqual(oracle.decimal_cost(1, 6, price=0), Decimal(0))

    def test_invalid_cost_inputs_are_rejected(self):
        for args in ((0, 6), (1, 0), (math.inf, 1), (True, 1), (1, 1, 1.5),
                     (1, 1, 0), (1, 1, 1, -1), (1, 1, 1, "NaN")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                oracle.decimal_cost(*args)

    def test_uses_calibration_median_not_evaluation_samples(self):
        result = oracle.evaluate_measurements([99, 100, 101], [105, 105, 105], [315, 315, 315])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["calibration_median_seconds"], 100)
        self.assertEqual(result["predicted_seconds"], {"base": 100, "pr": 300})
        self.assertEqual(result["observed_median_seconds"], {"base": 105, "pr": 315})

    def test_threshold_boundaries_are_inclusive(self):
        result = oracle.evaluate_measurements([85, 100, 115], [125, 125, 125], [375, 375, 375])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["relative_errors"], {"base": 0.2, "pr": 0.2})
        for group in (0, 1, 2):
            values = [[100, 100, 100], [100, 100, 100], [300, 300, 300]]
            values[group][0] *= 0.84999
            with self.subTest(group=group):
                self.assertEqual(oracle.evaluate_measurements(*values)["status"], "FAIL")
        self.assertEqual(oracle.evaluate_measurements([100]*3, [125.001]*3, [300]*3)["status"], "FAIL")
        self.assertEqual(oracle.evaluate_measurements([100]*3, [100]*3, [375.001]*3)["status"], "FAIL")

    def test_each_group_requires_three_positive_finite_numbers(self):
        for bad in ([], [1, 2], [1, 2, 3, 4], [0, 1, 1], [-1, 1, 1],
                    [math.nan, 1, 1], [math.inf, 1, 1], [True, 1, 1], ["1", 1, 1], "123", None):
            for group in (0, 1, 2):
                values = [[1]*3, [1]*3, [3]*3]
                values[group] = bad
                with self.subTest(bad=bad, group=group), self.assertRaises(ValueError):
                    oracle.evaluate_measurements(*values)


if __name__ == "__main__":
    unittest.main()
