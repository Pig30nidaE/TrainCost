import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from traincost_ci_core import analyze_config_dicts


class PrecisionPrecedenceTests(unittest.TestCase):
    def codes(self, **overrides):
        config = {"epochs": 1, "gpu_type": "T4", "gpu_count": 1,
                  "estimated_minutes_per_epoch": 1, **overrides}
        return {warning.code for warning in analyze_config_dicts(config, config).warnings}

    def test_explicit_enabled_mixed_precision_overrides_fp32_storage_dtype(self):
        for precision in ("fp32", "float32", "torch.float32", None):
            with self.subTest(precision=precision):
                self.assertNotIn("precision_risk", self.codes(precision=precision, mixed_precision=True))

    def test_disabled_and_inferred_fp32_still_warn(self):
        for precision in ("fp32", "bf16", None):
            with self.subTest(precision=precision):
                self.assertIn("precision_risk", self.codes(precision=precision, mixed_precision=False))
        self.assertIn("precision_risk", self.codes(precision="fp32"))
        self.assertNotIn("precision_risk", self.codes(precision="bf16"))
        self.assertNotIn("precision_risk", self.codes())
