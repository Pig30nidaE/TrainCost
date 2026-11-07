import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


DEMO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hf_demo_common", DEMO / "common.py")
common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(common)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.base = json.loads((DEMO / "fixtures/base.json").read_text())

    def test_input_contract_and_only_epoch_change(self):
        base, pr, manifest = common.input_contract()
        self.assertEqual({**base, "epochs": 3}, pr)
        self.assertEqual(manifest["model"], base["model_name"])
        self.assertEqual(common.validate_config(base, 1), base)

    def test_live_config_can_be_base_or_pr_but_not_another_change(self):
        original_read = common.read_json
        for epochs, allowed in ((1, True), (3, True), (2, False)):
            live = {**self.base, "epochs": epochs}
            def read(path):
                return live if Path(path) == DEMO / "config.json" else original_read(path)
            with self.subTest(epochs=epochs), patch.object(common, "read_json", side_effect=read):
                if allowed:
                    common.input_contract()
                else:
                    with self.assertRaises(ValueError):
                        common.input_contract()

    def test_native_hf_metadata_and_distributed_keys_are_rejected(self):
        for key, value in (("max_steps", 128), ("num_train_epochs", 3),
                           ("per_device_train_batch_size", 8), ("gradient_accumulation_steps", 1),
                           ("bf16", False), ("fp16", False), ("world_size", 1),
                           ("model_type", "distilbert"), ("architectures", ["DistilBertModel"])):
            with self.subTest(key=key), self.assertRaises(ValueError):
                common.validate_config({**self.base, key: value})
        with self.assertRaises(ValueError):
            common.validate_config({"model_type": "distilbert", "architectures": ["DistilBertModel"]})

    def test_live_config_rejects_equal_values_with_invalid_types(self):
        original_read = common.read_json
        for key, value in (("epochs", True), ("epochs", 1.0), ("batch_size", 8.0),
                           ("gpu_count", True), ("mixed_precision", 0)):
            live = {**self.base, key: value}
            def read(path):
                return live if Path(path) == DEMO / "config.json" else original_read(path)
            with self.subTest(key=key, value=value), patch.object(common, "read_json", side_effect=read):
                with self.assertRaises(ValueError):
                    common.input_contract()

    def test_invalid_or_inconsistent_values_are_rejected(self):
        for key, value in (("epochs", True), ("epochs", 2), ("batch_size", 4),
                           ("gpu_count", 2), ("precision", "bf16"),
                           ("estimated_minutes_per_epoch", 0), ("budget_limit_usd", float("nan"))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                common.validate_config({**self.base, key: value})
        with self.assertRaises(ValueError):
            common.validate_config(self.base, 3)

    def test_duplicate_and_nonfinite_json_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            for content in ('{"epochs": 1, "epochs": 3}', '{"epochs": NaN}'):
                path.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    common.read_json(path)

    def test_source_fingerprint_changes_when_contract_or_artifact_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            demo = root / "examples" / "huggingface-demo"
            core = root / "packages/core/src/traincost_ci_core"
            action = root / "packages/github-action"
            for directory in (demo / "fixtures", core, action):
                directory.mkdir(parents=True, exist_ok=True)
            files = [demo / name for name in ("run_validation.py", "worker.py", "common.py", "oracle.py", "model_safety.py", "manifest.json", "requirements.in", "requirements.lock")]
            files += [core / "engine.py", action / "traincost_action.py"]
            for path in files:
                path.write_text("original")
            with patch.object(common, "HERE", demo), patch.object(common, "ROOT", root), \
                    patch.object(common, "input_contract", return_value=(self.base, {}, {})):
                original = common.source_fingerprint()
                for path in files:
                    with self.subTest(path=path.name):
                        path.write_text("changed")
                        self.assertNotEqual(original, common.source_fingerprint())
                        path.write_text("original")
                self.base["estimated_minutes_per_epoch"] += 1
                self.assertNotEqual(original, common.source_fingerprint())


if __name__ == "__main__":
    unittest.main()
