"""Exercise the matrix worker without downloading models or loading Torch."""
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("matrix_worker_test", HERE / "matrix_worker.py")
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)
common = worker.common


class Tensor:
    def __init__(self, value=1, finite=True):
        self.value = value
        self.finite = finite
        self.dtype = "float32"
        self.requires_grad = True
        self.device = SimpleNamespace(type="mps")
        self.grad = None

    def is_floating_point(self): return True
    def detach(self): return self
    def cpu(self): return self
    def clone(self): return Tensor(self.value, self.finite)
    def numel(self): return 8


class Dataset:
    def __init__(self, split):
        self.split = split
        self.labels = [0] * 32 + [1] * 32
        self.text = [f"{split}-{i}" for i in range(64)]

    def __len__(self): return 64
    def __getitem__(self, key): return {"label": self.labels, "text": self.text}[key]
    def map(self, callback, **kwargs):
        callback({"text": self.text})
        return self
    def rename_column(self, old, new): return self


class MatrixWorkerTests(unittest.TestCase):
    def run_train(self, key="distilbert", phase="base-1", epochs=1, **options):
        profile = common.profile_for(key)
        profiles = common.load_profiles()
        env = {"device": "mps", "packages": {"torch": options.get("torch_version", "synthetic")}}
        indices = list(range(64))
        selection = {"source_sha256": "source", "profile_sha256": common.digest(profile),
                     "model_files_sha256": {"model.safetensors": options.get("model_hash", "model-hash")}}
        for split in ("train", "test"):
            selection[split] = {"size": 64, "indices": indices, "indices_sha256": common.digest(indices),
                                "content_sha256": f"{split}-hash"}
        prepared = {"status": "PASS", "environment": env, "source_sha256": "source",
                    "profile_sha256": common.digest(profile)}
        param = Tensor()
        param.dtype = options.get("dtype", "float32")
        param.grad = Tensor(1, options.get("finite_gradient", True))
        base_model = SimpleNamespace(named_parameters=lambda: iter([("embeddings.weight", param)]))
        model = SimpleNamespace(config=SimpleNamespace(model_type=options.get("model_type", profile["model_type"]),
                                                       _attn_implementation=options.get("attention", "eager")),
                                base_model=base_model, parameters=lambda: iter([param]))
        captured = {"syncs": 0}
        torch = ModuleType("torch")
        torch.float32 = "float32"
        def synchronize(): captured["syncs"] += 1
        torch.mps = SimpleNamespace(synchronize=synchronize, current_allocated_memory=lambda: 128)
        torch.isfinite = lambda value: SimpleNamespace(all=lambda: SimpleNamespace(item=lambda: value.finite))
        torch.count_nonzero = lambda value: SimpleNamespace(item=lambda: bool(value.value))
        torch.equal = lambda first, second: first.value == second.value
        psutil = ModuleType("psutil")
        psutil.virtual_memory = lambda: SimpleNamespace(available=2 * 1024**3)
        psutil.Process = lambda: SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=256))
        datasets = ModuleType("datasets")
        datasets.load_from_disk = lambda path: Dataset("train" if path.endswith("selected-train") else "test")
        numpy = ModuleType("numpy")
        transformers = ModuleType("transformers")

        class Tokenizer:
            is_fast = options.get("fast_tokenizer", True)
            @classmethod
            def from_pretrained(cls, _path, **kwargs):
                captured["tokenizer"] = kwargs
                return cls()
            def __call__(self, text, **kwargs):
                captured["tokenization"] = kwargs
                return {"input_ids": [[1, 2]]}

        class Model:
            @classmethod
            def from_pretrained(cls, _path, **kwargs):
                captured["model"] = kwargs
                return model

        class TrainingArguments:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.device = SimpleNamespace(type=options.get("device", "mps"))
                self.world_size = options.get("world_size", 1)
                if self.report_to == "none":
                    self.report_to = []

        class Trainer:
            def __init__(self, model, args, train_dataset, eval_dataset, compute_metrics, callbacks):
                self.args, self.safety = args, callbacks[0]
                self.state = SimpleNamespace(global_step=0)
                if options.get("mutate_args"):
                    self.args.per_device_train_batch_size = 4
            def train(self):
                for _ in range(8 * epochs):
                    self.safety.on_pre_optimizer_step(None, self.state, None, model=model)
                    self.safety.on_log(None, self.state, None, logs={"loss": 1.0, "grad_norm": 1.0})
                self.state.global_step = 8 * epochs
                if options.get("change_encoder", True):
                    param.value += 1
                param.finite = options.get("finite_weights", True)
                return SimpleNamespace(training_loss=1.0)
            def evaluate(self): return {"eval_accuracy": .5, "eval_f1": .5}

        transformers.AutoTokenizer, transformers.AutoModelForSequenceClassification = Tokenizer, Model
        transformers.TrainingArguments, transformers.Trainer = TrainingArguments, Trainer
        transformers.TrainerCallback = type("TrainerCallback", (), {})
        transformers.set_seed = lambda seed: captured.update(seed=seed)
        modules = {"numpy": numpy, "torch": torch, "psutil": psutil, "datasets": datasets, "transformers": transformers}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_dir = root / key
            cache = model_dir / "cache"
            (cache / "model").mkdir(parents=True)
            for split in ("train", "test"):
                (cache / ("selected-" + split)).mkdir()
            (model_dir / "prepare.json").write_text("{}")
            (model_dir / "selection.json").write_text("{}")
            def read_json(path): return prepared if Path(path).name == "prepare.json" else selection
            with patch.dict(sys.modules, modules), patch.object(worker, "safe_environment", return_value=env), \
                    patch.object(worker, "model_hashes", return_value=(
                        {"model.safetensors": "tampered"} if options.get("tamper_model") else selection["model_files_sha256"])), \
                    patch.object(worker, "dataset_hash", side_effect=lambda data: data.split + "-hash"), \
                    patch.object(worker, "check_source", return_value="source"), \
                    patch.object(common, "read_json", side_effect=read_json):
                result = worker.train(root, model_dir, profile, profiles, phase, epochs, "source")
        return result, captured

    def test_three_architectures_and_actual_arguments(self):
        for key in ("distilbert", "bert", "albert"):
            with self.subTest(key=key):
                result, captured = self.run_train(key)
                self.assertEqual(result["model_type"], key)
                self.assertEqual(result["updates"], 8)
                self.assertEqual(result["finite_gradients_checked"], 8)
                self.assertTrue(result["encoder_updated"])
                self.assertEqual(result["observed_training_arguments"]["device"], "mps")
                self.assertEqual(result["observed_training_arguments"]["report_to"], [])
                self.assertTrue(captured["model"]["local_files_only"])
                self.assertTrue(captured["model"]["use_safetensors"])
                self.assertFalse(captured["model"]["trust_remote_code"])
                self.assertEqual(captured["tokenization"]["max_length"], 128)
                self.assertGreaterEqual(captured["syncs"], 4)

    def test_condition_hash_excludes_epoch_count(self):
        base, _ = self.run_train("bert", "base-1", 1)
        pr, _ = self.run_train("bert", "pr-1", 3)
        self.assertEqual(base["condition_sha256"], pr["condition_sha256"])
        self.assertEqual(pr["updates"], 24)
        for options in ({"model_hash": "changed"}, {"torch_version": "changed"}, {"attention": "sdpa"}):
            with self.subTest(options=options):
                changed, _ = self.run_train("bert", **options)
                self.assertNotEqual(base["condition_sha256"], changed["condition_sha256"])

    def test_worker_result_satisfies_controller_contract(self):
        root = HERE.parents[1]
        spec = importlib.util.spec_from_file_location("matrix_controller_test", root / "scripts/verify_hf_matrix.py")
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
        profile = common.profile_for("bert")
        base, _ = self.run_train("bert", "base-1", 1)
        pr, _ = self.run_train("bert", "pr-1", 3)
        prepared = {"environment": base["environment"]}
        selection = {"model_files_sha256": {"model.safetensors": "model-hash"},
                     "train": {"content_sha256": "train-hash"}, "test": {"content_sha256": "test-hash"}}
        condition = controller.validate_run(base, profile, prepared, selection, "source", "base-1")
        self.assertEqual(condition, controller.validate_run(pr, profile, prepared, selection, "source", "pr-1", condition))

    def test_unsafe_device_architecture_or_training_rejected(self):
        for options in ({"device": "cpu"}, {"world_size": 2}, {"model_type": "wrong"},
                        {"finite_gradient": False}, {"finite_weights": False}, {"dtype": "float16"},
                        {"mutate_args": True}, {"tamper_model": True},
                        {"change_encoder": False}, {"fast_tokenizer": False}):
            with self.subTest(options=options), self.assertRaises(worker.WorkerError):
                self.run_train(**options)

    def test_model_file_allowlist_and_parent_guard(self):
        bad = dict(common.profile_for("bert"), files=["config.json", "../model.safetensors"])
        with self.assertRaises(worker.WorkerError):
            worker.expected_files(bad)
        with self.assertRaises(worker.WorkerError):
            worker.check_supervisor(1)

    def test_model_hashes_reject_extra_and_symlinked_files(self):
        profile = common.profile_for("bert")
        with tempfile.TemporaryDirectory() as temp:
            model_dir = Path(temp) / "model"
            model_dir.mkdir()
            for name in profile["files"]:
                (model_dir / name).write_bytes(b"synthetic")
            original = worker.model_hashes(model_dir, profile)
            (model_dir / "vocab.txt").write_bytes(b"different")
            self.assertNotEqual(original, worker.model_hashes(model_dir, profile))
            (model_dir / "unlisted.json").write_text("{}")
            with self.assertRaises(worker.WorkerError):
                worker.model_hashes(model_dir, profile)
        with tempfile.TemporaryDirectory() as temp:
            model_dir = Path(temp) / "model"
            model_dir.mkdir()
            outside = Path(temp) / "outside"
            outside.write_text("synthetic")
            for name in profile["files"]:
                if name == "vocab.txt":
                    (model_dir / name).symlink_to(outside)
                else:
                    (model_dir / name).write_bytes(b"synthetic")
            with self.assertRaises(worker.WorkerError):
                worker.model_hashes(model_dir, profile)

    def test_prepare_uses_pinned_files_and_balanced_disjoint_indices(self):
        profile, profiles = common.profile_for("distilbert"), common.load_profiles()
        train_rows = [{"text": f"review-{label}-{i}", "label": label} for label in (0, 1) for i in range(80)]
        test_rows = [{"text": f"review-{label}-{i}", "label": label} for label in (0, 1) for i in range(100)]
        calls = []

        class Rows:
            def __init__(self, rows): self.rows = rows
            def __getitem__(self, key): return [row[key] for row in self.rows]
            def __iter__(self): return iter(self.rows)
            def select(self, indices): return Rows([self.rows[i] for i in indices])
            def save_to_disk(self, path): Path(path).mkdir(parents=True)

        datasets, hub = ModuleType("datasets"), ModuleType("huggingface_hub")
        datasets.load_dataset = lambda _name, data_files, **kwargs: Rows(train_rows if "train-" in data_files else test_rows)
        def snapshot_download(**kwargs):
            calls.append(kwargs)
            model_dir = Path(kwargs["local_dir"])
            model_dir.mkdir(parents=True)
            for name in kwargs["allow_patterns"]:
                (model_dir / name).write_text("synthetic")
        def hf_hub_download(**kwargs):
            calls.append(kwargs)
            return kwargs["filename"]
        hub.snapshot_download, hub.hf_hub_download = snapshot_download, hf_hub_download
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_dir = root / profile["key"]
            model_dir.mkdir()
            with patch.dict(sys.modules, {"datasets": datasets, "huggingface_hub": hub}), \
                    patch.object(worker, "safe_environment", return_value={"device": "mps"}), \
                    patch.object(worker, "check_source", return_value="source"):
                result = worker.prepare(root, model_dir, profile, profiles, "source")
                with self.assertRaises(worker.WorkerError):
                    worker.prepare(root, model_dir, profile, profiles, "source")
            selection = common.read_json(model_dir / "selection.json")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(selection["train"]["label_counts"], [32, 32])
            self.assertEqual(selection["test"]["label_counts"], [32, 32])
            train = {train_rows[i]["text"] for i in selection["train"]["indices"]}
            test = {test_rows[i]["text"] for i in selection["test"]["indices"]}
            self.assertFalse(train & test)
            self.assertEqual(set(selection["model_files_sha256"]), set(profile["files"]))
            self.assertEqual(calls[0]["revision"], profile["revision"])
            self.assertTrue(all(call["token"] is False for call in calls))

    def test_safe_errors_omit_exception_details(self):
        self.assertEqual(worker.safe_error_type(ValueError("private-token-value")), "ValueError")
        self.assertEqual(worker.safe_error_type(worker.WorkerError("private-token-value")), "WorkerError")


if __name__ == "__main__":
    unittest.main()
