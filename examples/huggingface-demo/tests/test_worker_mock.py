"""Exercise the real worker control flow with fake, CPU-only ML modules."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO))
SPEC = importlib.util.spec_from_file_location("hf_demo_worker_mock", DEMO / "worker.py")
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class Tensor:
    def __init__(self, value=1, finite=True):
        self.value, self.finite, self.dtype, self.grad = value, finite, "float32", None

    def detach(self): return self
    def clone(self): return Tensor(self.value, self.finite)
    def cpu(self): return self
    def is_floating_point(self): return True


class Data:
    def __init__(self, labels): self.labels = list(labels)
    def __getitem__(self, key): return self.labels if key == "label" else []
    def select(self, indices): return Data([self.labels[i] for i in indices])
    def map(self, callback, **kwargs):
        callback({"text": ["synthetic"]})
        return self
    def rename_column(self, old, new): return self


class WorkerMockTests(unittest.TestCase):
    def exercise(self, kind="base", **options):
        base = json.loads((DEMO / "fixtures/base.json").read_text())
        manifest = json.loads((DEMO / "manifest.json").read_text())
        config = {**base, "epochs": 3 if kind == "pr" else 1}
        captured = {"syncs": 0, "tokenizer": []}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_dir = root / "cache/model"
            model_dir.mkdir(parents=True)
            model_file = model_dir / "model.safetensors"
            model_file.write_bytes(b"fake-not-a-real-model")
            (root / "preflight.json").write_text('{"environment": "mock"}')
            selection = {"model_files_sha256": {model_file.name: worker.file_digest(model_file)},
                         "train": {"content_sha256": "mock-hash"}, "test": {"content_sha256": "mock-hash"},
                         "smoke": {"indices": list(range(64))}}
            (root / "selection.json").write_text(json.dumps(selection))
            param = Tensor()
            param.dtype = options.get("dtype", "float32")
            param.grad = None if options.get("no_gradient") else Tensor(options.get("gradient", 1), options.get("gradient_finite", True))
            model = SimpleNamespace(parameters=lambda: iter([param]), distilbert=SimpleNamespace(parameters=lambda: iter([param])))

            torch = ModuleType("torch")
            torch.float32 = "float32"
            torch.backends = SimpleNamespace(cuda=SimpleNamespace(matmul=SimpleNamespace(allow_tf32=True)),
                                             cudnn=SimpleNamespace(allow_tf32=True))
            def synchronize(): captured["syncs"] += 1
            torch.cuda = SimpleNamespace(mem_get_info=lambda *_: options.get("memory", (10_000, 12_000)),
                reset_peak_memory_stats=lambda: None, synchronize=synchronize, max_memory_allocated=lambda: 42)
            torch.isfinite = lambda value: SimpleNamespace(all=lambda: SimpleNamespace(item=lambda: value.finite))
            torch.count_nonzero = lambda value: SimpleNamespace(item=lambda: bool(value.value))
            torch.equal = lambda left, right: left.value == right.value

            datasets = ModuleType("datasets")
            datasets.load_from_disk = lambda _path: Data([0] * 32 + [1] * 32)
            numpy = ModuleType("numpy")
            transformers = ModuleType("transformers")
            class Tokenizer:
                @classmethod
                def from_pretrained(cls, path, **kwargs):
                    captured["tokenizer_loader"] = kwargs
                    def tokenize(text, **kwargs):
                        captured["tokenizer"].append(kwargs)
                        return {"input_ids": [[1, 2]]}
                    return tokenize
            class Model:
                @classmethod
                def from_pretrained(cls, path, **kwargs):
                    captured["model_loader"] = kwargs
                    return model
            class TrainingArguments:
                def __init__(self, **kwargs):
                    captured["arguments"] = kwargs.copy()
                    self.__dict__.update(kwargs)
                    self.device = SimpleNamespace(type=options.get("device", "cuda"))
                    self.world_size = options.get("world_size", 1)
                    if options.get("alter_arguments"):
                        self.per_device_train_batch_size = 999
            class Trainer:
                def __init__(self, model, args, train_dataset, eval_dataset, compute_metrics, callbacks):
                    self.args, self.callback = args, callbacks[0]
                    self.state = SimpleNamespace(global_step=0)
                def train(self):
                    self.callback.on_pre_optimizer_step(None, self.state, None, model=model)
                    self.callback.on_log(None, self.state, None,
                                         logs={"loss": options.get("logged_loss", 1.0),
                                               "grad_norm": options.get("logged_grad_norm", 1.0)})
                    self.state.global_step = options.get("steps", 8 if kind == "smoke" else 128 * config["epochs"])
                    if options.get("change_weights", True): param.value += 1
                    param.finite = options.get("parameters_finite", True)
                    return SimpleNamespace(training_loss=options.get("training_loss", 1.0))
                def evaluate(self): return {"eval_accuracy": 0.5, "eval_f1": 0.5}
            transformers.AutoTokenizer = Tokenizer
            transformers.AutoModelForSequenceClassification = Model
            transformers.Trainer = Trainer
            transformers.TrainerCallback = type("TrainerCallback", (), {})
            transformers.TrainingArguments = TrainingArguments
            transformers.set_seed = lambda value: captured.update(seed=value)
            modules = {"torch": torch, "datasets": datasets, "transformers": transformers, "numpy": numpy}
            with patch.dict(sys.modules, modules), patch.object(worker, "environment", return_value={"environment": "mock"}), \
                    patch.object(worker, "dataset_hash", return_value="mock-hash"):
                output = worker.train(root, {"kind": kind, "config": config}, manifest)
            return output, captured

    def test_training_arguments_and_steps_propagate(self):
        for kind, epochs, steps in (("base", 1, 128), ("pr", 3, 384), ("smoke", 1, 8)):
            with self.subTest(kind=kind):
                result, captured = self.exercise(kind)
                self.assertEqual(result["updates"], steps)
                args = captured["arguments"]
                for key, value in {"num_train_epochs": epochs, "max_steps": -1, "per_device_train_batch_size": 8,
                                   "gradient_accumulation_steps": 1, "learning_rate": 2e-5,
                                   "lr_scheduler_type": "constant", "warmup_steps": 0, "optim": "adamw_torch",
                                   "fp16": False, "bf16": False, "tf32": False, "seed": 42,
                                   "save_strategy": "no", "eval_strategy": "no", "report_to": "none"}.items():
                    self.assertEqual(args[key], value, key)
                self.assertGreaterEqual(captured["syncs"], 2)
                self.assertEqual(captured["tokenizer"][0], {"padding": "max_length", "truncation": True, "max_length": 128})
                self.assertFalse(captured["model_loader"]["trust_remote_code"])
                self.assertTrue(captured["model_loader"]["local_files_only"])

    def test_device_and_config_invariants(self):
        for options in ({"device": "cpu"}, {"world_size": 2}, {"dtype": "float16"}, {"alter_arguments": True}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.exercise(**options)

    def test_wrong_steps_nonfinite_loss_and_vram_are_rejected(self):
        for kind, options in (("base", {"steps": 127}), ("pr", {"steps": 383}),
                              ("base", {"training_loss": float("nan")}),
                              ("base", {"logged_loss": float("nan")}),
                              ("base", {"memory": (10, 1000)})):
            with self.subTest(kind=kind, options=options), self.assertRaises(ValueError):
                self.exercise(kind, **options)

    def test_smoke_requires_finite_nonzero_gradient_and_changed_encoder(self):
        for options in ({"no_gradient": True}, {"gradient_finite": False}, {"gradient": 0}, {"change_weights": False}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.exercise("smoke", **options)

    def test_nonfinite_logged_gradient_norm_and_final_parameters_are_rejected(self):
        for options in ({"logged_grad_norm": float("nan")}, {"logged_grad_norm": float("inf")},
                        {"parameters_finite": False}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.exercise("base", **options)

    def test_worker_start_rejects_parent_mismatch_before_preflight(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "result.json"
            args = ["worker.py", "preflight", "--workspace", str(root), "--output", str(output), "--parent-pid", "12345"]
            with patch.object(sys, "argv", args), patch.object(sys, "platform", "linux"), \
                    patch.object(worker.os, "getppid", return_value=12346), \
                    patch.object(worker, "input_contract") as contract, \
                    patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(worker.main(), 1)
            contract.assert_not_called()
            self.assertEqual(json.loads(output.read_text()), {"status": "FAIL", "reason": "WORKER_ERROR"})

    def test_parent_change_after_arming_is_rejected(self):
        libc = SimpleNamespace(prctl=lambda *_: 0)
        with patch.object(sys, "platform", "linux"), patch.object(worker.os, "getppid", side_effect=[12345, 12346]), \
                patch.object(worker.ctypes, "CDLL", return_value=libc):
            with self.assertRaises(ValueError):
                worker.arm_parent_death_signal(12345)


if __name__ == "__main__":
    unittest.main()
