from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from traincost_ci_core import analyze_config_dicts


class MicrobatchRegressionTests(unittest.TestCase):
    def test_hf_per_device_batch_drives_utilization_warning(self):
        for accumulation in (1, 64):
            for world_size in (1, 4):
                for model, microbatch, expected in (
                    ("llama-7b", 1, True),
                    ("llama-7b", 8, True),
                    ("resnet18", 4, True),
                    ("resnet18", 8, False),
                    ("llama-7b", 16, False),
                ):
                    config = {"model_name": model, "num_train_epochs": 1,
                              "per_device_train_batch_size": microbatch,
                              "gradient_accumulation_steps": accumulation, "world_size": world_size,
                              "bf16": True, "gpu_type": "A100", "estimated_minutes_per_epoch": 5}
                    with self.subTest(accumulation=accumulation, world_size=world_size,
                                      model=model, microbatch=microbatch):
                        result = analyze_config_dicts(config, config, adapter="huggingface")
                        warnings = [warning for warning in result.warnings if warning.code == "small_batch_size"]
                        self.assertEqual(bool(warnings), expected)
                        self.assertEqual(result.pr_config.global_batch_size, microbatch * accumulation * world_size)
                        if warnings:
                            self.assertEqual(warnings[0].what_changed, f"Per-device batch size is {microbatch}.")
                            self.assertNotIn("accumulation", warnings[0].how_to_reduce_risk.lower())
                            self.assertNotIn("effective", warnings[0].recommendation.lower())
                            self.assertIn(warnings[0].what_changed, result.markdown_report)

    def test_canonical_global_batch_precedence_is_unchanged(self):
        base = {"model_name": "resnet18", "epochs": 1, "gpu_type": "T4", "gpu_count": 1,
                "estimated_minutes_per_epoch": 5}
        for fields, expected in (({"batch_size": 1, "global_batch_size": 64}, False),
                                 ({"batch_size": 64, "global_batch_size": 1}, True),
                                 ({"batch_size": 1}, True), ({"global_batch_size": 8}, False)):
            with self.subTest(fields=fields):
                config = {**base, **fields}
                result = analyze_config_dicts(config, config)
                warnings = [warning for warning in result.warnings if warning.code == "small_batch_size"]
                self.assertEqual(bool(warnings), expected)
                if warnings:
                    self.assertNotIn("Per-device", warnings[0].what_changed)
                    self.assertNotIn("accumulation", warnings[0].how_to_reduce_risk.lower())

    def test_hf_global_only_falls_back_to_available_batch(self):
        config = {"num_train_epochs": 1, "global_batch_size": 4, "gpu_type": "T4",
                  "gpu_count": 1, "estimated_minutes_per_epoch": 5}
        result = analyze_config_dicts(config, config, adapter="huggingface")
        warning = next(warning for warning in result.warnings if warning.code == "small_batch_size")
        self.assertEqual(warning.what_changed, "Batch size is 4.")
