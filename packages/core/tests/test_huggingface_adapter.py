from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from traincost_ci_core import analyze_config_dicts, analyze_config_files, normalize_training_config
from traincost_ci_core.safety import ConfigError

BASE = {"num_train_epochs": 2.5, "per_device_train_batch_size": 4, "gradient_accumulation_steps": 2,
        "bf16": True, "world_size": 2, "gpu_type": "A100", "estimated_minutes_per_epoch": 3}


class HuggingFaceAdapterTests(unittest.TestCase):
    def test_flat_adapter_and_canonical_opt_in(self):
        canonical = normalize_training_config(BASE)
        self.assertIsNone(canonical.epochs)
        config = normalize_training_config(BASE, adapter="huggingface")
        self.assertEqual((config.epochs, config.batch_size, config.global_batch_size, config.gpu_count), (2.5, 4, 16, 2))
        self.assertEqual((config.precision, config.mixed_precision), ("bf16", True))
        result = analyze_config_dicts(BASE, BASE, adapter="huggingface")
        self.assertEqual(result.pr_config.global_batch_size, 16)
        self.assertNotIn("unsupported_training_settings", {w.code for w in result.warnings})

    def test_nested_training_args_and_metadata(self):
        args = {key: value for key, value in BASE.items() if key not in {"gpu_type", "world_size", "estimated_minutes_per_epoch"}}
        config = {"training_args": args, "gpu_type": "T4", "world_size": 2, "estimated_minutes_per_epoch": 10}
        result = analyze_config_dicts(config, config, adapter="huggingface")
        self.assertEqual(result.pr_config.global_batch_size, 16)
        self.assertEqual(result.pr_config.field_sources["gpu_count"], ("world_size",))

    def test_file_adapter_yaml_json_and_literal_python(self):
        texts = (('a.yaml', 'num_train_epochs: 2\nper_device_train_batch_size: 4\nworld_size: 1\n'),
                 ('a.json', json.dumps(BASE)), ('a.py', 'num_train_epochs = 2\nworld_size = 1\n'))
        with tempfile.TemporaryDirectory() as temp:
            for name, text in texts:
                path = Path(temp) / name
                path.write_text(text)
                self.assertEqual(analyze_config_files(path, path, adapter="huggingface").pr_config.epochs, 2.5 if name.endswith("json") else 2)

    def test_conflicting_aliases_are_rejected(self):
        variants = ({"epochs": 3}, {"max_epochs": 3}, {"batch_size": 8}, {"gpu_count": 4},
                    {"global_batch_size": 8}, {"fp16": True}, {"precision": "fp32"})
        for extra in variants:
            with self.subTest(extra=extra), self.assertRaises(ConfigError):
                normalize_training_config({**BASE, **extra}, adapter="huggingface")
        with self.assertRaises(ConfigError):
            normalize_training_config({"training_args": {**BASE, "world_size": 2}, "world_size": 3}, adapter="huggingface")
        with self.assertRaises(ConfigError):
            normalize_training_config({"num_train_epochs": 2, "precision": "bf16", "bf16": False}, adapter="huggingface")

    def test_unsupported_and_ambiguous_execution_settings(self):
        for key, value in (("max_steps", 1), ("max_steps", "nan"), ("auto_find_batch_size", True),
                           ("per_device_train_batch_size", "auto"), ("deepspeed", "config.json"),
                           ("fsdp", "full_shard"), ("strategy", "deepspeed_stage_2"),
                           ("gradient_accumulation_steps", 1.5), ("use_cpu", True),
                           ("no_cuda", True), ("use_tpu", True), ("tpu_num_cores", 8)):
            with self.subTest(key=key), self.assertRaises(ConfigError):
                normalize_training_config({**BASE, key: value}, adapter="huggingface")
        for value in (-1, 0):
            normalize_training_config({**BASE, "max_steps": value}, adapter="huggingface")
        normalize_training_config({**BASE, "use_cpu": False, "no_cuda": False, "use_tpu": False}, adapter="huggingface")
        with self.assertRaises(ConfigError):
            normalize_training_config({"num_train_epochs": 1, "per_device_train_batch_size": 4, "global_batch_size": 16}, adapter="huggingface")

    def test_model_only_invalid_adapter_and_precision(self):
        for config in ({"model_type": "bert", "hidden_size": 768}, {"training_args": []}):
            with self.assertRaises(ConfigError):
                normalize_training_config(config, adapter="huggingface")
        with self.assertRaises(ConfigError):
            normalize_training_config(BASE, adapter="not-a-real-adapter")
        config = normalize_training_config({**BASE, "bf16": False, "fp16": False}, adapter="huggingface")
        self.assertFalse(config.mixed_precision)
        config = normalize_training_config({"num_train_epochs": 2, "bf16": False}, adapter="huggingface")
        self.assertIsNone(config.mixed_precision)
        config = normalize_training_config({"num_train_epochs": 2}, adapter="huggingface")
        self.assertIsNone(config.mixed_precision)

    def test_root_and_nested_settings_cannot_bypass_validation(self):
        for key, value in (("max_steps", 100), ("deepspeed", "config.json"), ("fsdp", "full_shard"),
                           ("auto_find_batch_size", True), ("per_device_train_batch_size", "auto")):
            with self.subTest(key=key), self.assertRaises(ConfigError):
                normalize_training_config({"training_args": {"num_train_epochs": 2}, key: value}, adapter="huggingface")
        for key, value in (("max_steps", 100), ("deepspeed", "config.json"), ("bf16", True)):
            with self.subTest(nested=key), self.assertRaises(ConfigError):
                normalize_training_config({"training_args": {"num_train_epochs": 2}, "other": {key: value}}, adapter="huggingface")
        with self.assertRaises(ConfigError):
            normalize_training_config({"training_args": {"num_train_epochs": 2}, "num_train_epochs": 3}, adapter="huggingface")
        config = normalize_training_config({"training_args": {"num_train_epochs": 2}, "per_device_train_batch_size": 4, "world_size": 2}, adapter="huggingface")
        self.assertEqual(config.global_batch_size, 8)
        self.assertEqual(config.field_sources["batch_size"], ("per_device_train_batch_size",))

    def test_case_variant_aliases_are_compared_and_containers_are_unambiguous(self):
        for args in ({"num_train_epochs": 1, "NUM_TRAIN_EPOCHS": 3},
                     {"bf16": True, "BF16": False},
                     {"max_steps": -1, "MAX_STEPS": 4}):
            for config in (args, {"training_args": args}):
                with self.subTest(config=config), self.assertRaises(ConfigError):
                    normalize_training_config(config, adapter="huggingface")
        config = normalize_training_config({"NUM_TRAIN_EPOCHS": "2", "num_train_epochs": 2,
                                            "bf16": True, "BF16": "true"}, adapter="huggingface")
        self.assertEqual(config.epochs, 2)
        self.assertTrue(config.mixed_precision)
        with self.assertRaises(ConfigError):
            normalize_training_config({"training_args": {"num_train_epochs": 2},
                                       "Training_Args": {"num_train_epochs": 2}}, adapter="huggingface")
        config = normalize_training_config({"Training_Args": {"num_train_epochs": 2}}, adapter="huggingface")
        self.assertEqual(config.epochs, 2)
        self.assertEqual(config.field_sources["epochs"], ("Training_Args.num_train_epochs",))

    def test_accumulation_changes_trigger_runtime_warning(self):
        result = analyze_config_dicts(BASE, {**BASE, "gradient_accumulation_steps": 4}, adapter="huggingface")
        self.assertIn("stale_runtime_assumption", {w.code for w in result.warnings})
        self.assertEqual(result.pr_config.global_batch_size, 32)

    def test_epoch_and_inactive_max_steps_do_not_stale_runtime(self):
        for changed in ({"num_train_epochs": 5}, {"max_steps": 0}):
            result = analyze_config_dicts({**BASE, "max_steps": -1}, {**BASE, "max_steps": -1, **changed}, adapter="huggingface")
            self.assertNotIn("stale_runtime_assumption", {w.code for w in result.warnings})

    def test_equivalent_typed_aliases_do_not_stale_runtime(self):
        result = analyze_config_dicts(BASE, {**BASE, "per_device_train_batch_size": "4", "bf16": "true"}, adapter="huggingface")
        self.assertNotIn("stale_runtime_assumption", {w.code for w in result.warnings})
        without = {key: value for key, value in BASE.items() if key not in {"gradient_accumulation_steps", "world_size"}}
        result = analyze_config_dicts({**without, "gpu_count": 1}, {**without, "gpu_count": 1, "world_size": "1", "gradient_accumulation_steps": "1"}, adapter="huggingface")
        self.assertNotIn("stale_runtime_assumption", {w.code for w in result.warnings})
