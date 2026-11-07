"""Private, supervised MPS worker for the bounded sequence-classification matrix."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from enum import Enum
import json
import math
import os
from pathlib import Path
import re
import signal
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(ROOT))

import matrix_common as common
from scripts.verify_hf_macos import check_environment, balanced_indices, dataset_hash
from worker import text_hash
from model_safety import validate_local_model

PHASE_PATTERN = re.compile(r"^(calibration|base|pr)-([123])$")
ALLOWED_MODEL_FILES = {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                       "vocab.txt", "vocab.json", "merges.txt", "spiece.model", "special_tokens_map.json"}


class WorkerError(Exception):
    """A validation or integrity check failed; the details must not be serialized."""


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise WorkerError("Invalid worker arguments")


def check_workspace(path):
    path = Path(path).expanduser().absolute()
    if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_dir():
        raise WorkerError("Unsafe workspace")
    return path.resolve()


def ensure_no_symlinks(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise WorkerError("Unsafe cache")
    for item in path.rglob("*"):
        if item.is_symlink():
            raise WorkerError("Unsafe cache")


def check_supervisor(parent_pid):
    if parent_pid <= 1 or os.getppid() != parent_pid or os.getpgrp() != os.getpid():
        raise WorkerError("Worker requires an isolated supervisor")


def start_watchdog(parent_pid, timeout):
    deadline = time.monotonic() + timeout

    def supervise():
        while True:
            if os.getppid() != parent_pid or time.monotonic() > deadline:
                os.killpg(os.getpid(), signal.SIGKILL)
            time.sleep(.25)

    threading.Thread(target=supervise, daemon=True).start()


def check_source(workspace):
    path = workspace / "run-contract.json"
    if path.is_symlink() or not path.is_file():
        raise WorkerError("Unsafe run contract")
    expected = common.read_json(path)["source_sha256"]
    if expected != common.source_fingerprint():
        raise WorkerError("Experiment source changed")
    return expected


def expected_files(profile):
    files = profile["files"]
    if (not isinstance(files, list) or len(files) != len(set(files)) or
            not set(files).issubset(ALLOWED_MODEL_FILES) or
            not {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json"}.issubset(files)):
        raise WorkerError("Invalid model file allowlist")
    return set(files)


def model_hashes(path, profile):
    required = expected_files(profile)
    if path.is_symlink() or not path.is_dir():
        raise WorkerError("Unsafe model cache")
    files = {entry.name for entry in path.iterdir() if entry.name != ".cache"}
    if files != required:
        raise WorkerError("Unexpected model files")
    result = {}
    for name in sorted(required):
        file = path / name
        if file.is_symlink() or not file.is_file():
            raise WorkerError("Unsafe model file")
        result[name] = common.file_digest(file)
    return result


def safe_environment():
    # check_environment returns tuples which need the same JSON form after reload.
    return json.loads(json.dumps(check_environment("mps"), allow_nan=False))


def prepare(workspace, model_dir, profile, profiles, source_sha256):
    from datasets import load_dataset
    from huggingface_hub import hf_hub_download, snapshot_download

    env = safe_environment()
    if (model_dir / "cache").exists() or (model_dir / "cache").is_symlink():
        raise WorkerError("Prepared cache already exists")
    start = time.monotonic()
    cache = model_dir / "cache"
    snapshot_download(repo_id=profile["model_id"], revision=profile["revision"], token=False,
                      local_dir=str(cache / "model"), allow_patterns=sorted(expected_files(profile)))
    hashes = model_hashes(cache / "model", profile)
    data_spec, protocol = profiles["dataset"], profiles["protocol"]
    selection = {"model_files_sha256": hashes, "source_sha256": source_sha256,
                 "profile_sha256": common.digest(profile)}
    train_hashes = set()
    for split in ("train", "test"):
        path = hf_hub_download(repo_id=data_spec["id"], repo_type="dataset", revision=data_spec["revision"],
                               filename=data_spec[split + "_file"], cache_dir=str(cache / "hub"), token=False)
        data = load_dataset("parquet", data_files=path, split="train", cache_dir=str(cache / "datasets"))
        count = protocol[split + "_size"]
        indices = balanced_indices(data, count, protocol["seed"], train_hashes)
        selected = data.select(indices)
        labels = list(selected["label"])
        if len(indices) != count or [labels.count(i) for i in (0, 1)] != [count // 2, count // 2]:
            raise WorkerError("Dataset selection mismatch")
        selected.save_to_disk(str(cache / ("selected-" + split)))
        ensure_no_symlinks(cache / ("selected-" + split))
        selection[split] = {"size": count, "indices": indices, "indices_sha256": common.digest(indices),
                            "content_sha256": dataset_hash(selected), "label_counts": [count // 2, count // 2]}
        if split == "train":
            train_hashes = {text_hash(text) for text in selected["text"]}
        elif any(text_hash(text) in train_hashes for text in selected["text"]):
            raise WorkerError("Dataset split overlap")
    selection["prepare_seconds"] = time.monotonic() - start
    check_source(workspace)
    common.write_json(model_dir / "selection.json", selection)
    return {"status": "PASS", "environment": env, "source_sha256": source_sha256,
            "profile_sha256": common.digest(profile)}


def safe_setting(value):
    if isinstance(value, Enum):
        return safe_setting(value.value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    if isinstance(value, (list, tuple)):
        return [safe_setting(item) for item in value]
    raise WorkerError("Unsupported training argument value")


def checked_training_arguments(args, settings):
    actual = {}
    for key, expected in settings.items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise WorkerError("Invalid training argument name")
        value = safe_setting(getattr(args, key))
        actual[key] = value
        if key == "report_to" and expected == "none" and value == []:
            continue
        if value != safe_setting(expected) or isinstance(value, bool) != isinstance(expected, bool):
            raise WorkerError("Training argument mismatch")
    return actual


def checked_config(profile, protocol, epochs):
    settings = common.training_settings(epochs)
    config = common.hf_config(profile, epochs, 6.0, .2)
    expected = {"model_name": profile["model_id"], "dataset_size": protocol["train_size"],
                "gpu_type": "APPLE_M1_MPS", "gpu_count": 1, "precision": "fp32",
                "estimated_minutes_per_epoch": 6.0, "budget_limit_usd": .2, "training_args": settings}
    if config != expected or settings.get("num_train_epochs") != epochs or settings.get("max_steps") != -1:
        raise WorkerError("Raw HF configuration mismatch")
    return config, settings


def safe_error_type(exc):
    for cls in (KeyboardInterrupt, WorkerError, FileNotFoundError, PermissionError,
                OSError, ValueError, RuntimeError, ImportError, TypeError, KeyError):
        if isinstance(exc, cls):
            return cls.__name__
    return "OtherError"


def train(workspace, model_dir, profile, profiles, phase, epochs, source_sha256):
    import numpy as np
    import psutil
    import torch
    from datasets import load_from_disk
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer, Trainer,
                              TrainerCallback, TrainingArguments, set_seed)

    env = safe_environment()
    prepare_path, selection_path = model_dir / "prepare.json", model_dir / "selection.json"
    if any(path.is_symlink() or not path.is_file() for path in (prepare_path, selection_path)):
        raise WorkerError("Unsafe prepared evidence")
    prepared = common.read_json(prepare_path)
    selection = common.read_json(selection_path)
    profile_sha256 = common.digest(profile)
    if (prepared.get("status") != "PASS" or prepared.get("environment") != env or
            prepared.get("source_sha256") != source_sha256 or selection.get("source_sha256") != source_sha256 or
            prepared.get("profile_sha256") != profile_sha256 or selection.get("profile_sha256") != profile_sha256):
        raise WorkerError("Prepared conditions changed")
    cache = model_dir / "cache"
    if cache.is_symlink() or not cache.is_dir():
        raise WorkerError("Unsafe cache")
    if model_hashes(cache / "model", profile) != selection["model_files_sha256"]:
        raise WorkerError("Prepared model changed")
    protocol = profiles["protocol"]
    data = {}
    hashes = {}
    for split in ("train", "test"):
        path = cache / ("selected-" + split)
        ensure_no_symlinks(path)
        dataset = load_from_disk(str(path))
        metadata = selection[split]
        labels = list(dataset["label"])
        count = protocol[split + "_size"]
        if (len(dataset) != count or metadata["size"] != count or len(metadata["indices"]) != count or
                common.digest(metadata["indices"]) != metadata["indices_sha256"] or
                dataset_hash(dataset) != metadata["content_sha256"] or
                [labels.count(i) for i in (0, 1)] != [count // 2, count // 2]):
            raise WorkerError("Prepared dataset changed")
        data[split] = dataset
        hashes[split] = metadata["content_sha256"]
    seen = {text_hash(text) for text in data["train"]["text"]}
    if any(text_hash(text) in seen for text in data["test"]["text"]):
        raise WorkerError("Dataset split overlap")
    config, settings = checked_config(profile, protocol, epochs)
    set_seed(protocol["seed"])
    load_start = time.monotonic()
    validate_local_model(cache / "model", profile["model_type"], hashes=profile["metadata_sha256"])
    tokenizer = AutoTokenizer.from_pretrained(str(cache / "model"), local_files_only=True, token=False,
                                              trust_remote_code=False, use_fast=True)
    if not tokenizer.is_fast:
        raise WorkerError("Fast tokenizer required")
    model = AutoModelForSequenceClassification.from_pretrained(str(cache / "model"), num_labels=2,
                 local_files_only=True, token=False, trust_remote_code=False, use_safetensors=True)
    if model.config.model_type != profile["model_type"] or model.base_model is model:
        raise WorkerError("Unexpected model architecture")
    if any(p.is_floating_point() and p.dtype != torch.float32 for p in model.parameters()):
        raise WorkerError("Expected FP32 model")
    candidates = ((name, value) for name, value in model.base_model.named_parameters()
                  if value.requires_grad and value.is_floating_point())
    name, sample = next(candidates)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", name):
        raise WorkerError("Unexpected encoder parameter name")
    before = sample.detach().cpu().clone()
    parameter_count = sum(value.numel() for value in model.parameters())
    load_seconds = time.monotonic() - load_start
    token_start = time.monotonic()

    def tokenize(batch):
        return tokenizer(batch["text"], max_length=protocol["max_length"], padding="max_length", truncation=True)

    data = {split: value.map(tokenize, batched=True, remove_columns=["text"]).rename_column("label", "labels")
            for split, value in data.items()}
    tokenize_seconds = time.monotonic() - token_start

    class Safety(TrainerCallback):
        def __init__(self):
            self.gradients = 0
            self.losses = []
            self.peak_rss = 0
            self.peak_mps = 0

        def on_pre_optimizer_step(self, args, state, control, model=None, **kwargs):
            if psutil.virtual_memory().available < 1024**3:
                raise WorkerError("Memory reserve exhausted")
            gradients = [p.grad for p in model.parameters() if p.grad is not None]
            if (not gradients or not all(torch.isfinite(g).all().item() for g in gradients) or
                    not any(torch.count_nonzero(g).item() for g in gradients)):
                raise WorkerError("Invalid gradients")
            self.gradients += 1
            self.peak_rss = max(self.peak_rss, psutil.Process().memory_info().rss)
            self.peak_mps = max(self.peak_mps, torch.mps.current_allocated_memory())

        def on_log(self, args, state, control, logs=None, **kwargs):
            for key in ("loss", "grad_norm"):
                if logs and key in logs and not math.isfinite(logs[key]):
                    raise WorkerError("Nonfinite training metric")
            if logs and "loss" in logs:
                self.losses.append(float(logs["loss"]))

    def metrics(prediction):
        labels, predicted = prediction.label_ids, np.argmax(prediction.predictions, axis=-1)
        tp = int(((predicted == 1) & (labels == 1)).sum())
        fp = int(((predicted == 1) & (labels == 0)).sum())
        fn = int(((predicted == 0) & (labels == 1)).sum())
        return {"accuracy": float((predicted == labels).mean()),
                "f1": float(2 * tp / (2 * tp + fp + fn)) if 2 * tp + fp + fn else 0.0}

    args = TrainingArguments(output_dir=str(cache / "trainer-output"), **settings)
    safety = Safety()
    trainer = Trainer(model=model, args=args, train_dataset=data["train"], eval_dataset=data["test"],
                      compute_metrics=metrics, callbacks=[safety])
    if (trainer.args.device.type != "mps" or trainer.args.world_size != 1 or
            any(p.device.type != "mps" for p in model.parameters())):
        raise WorkerError("MPS training required")
    actual = checked_training_arguments(trainer.args, settings)
    actual.update({"world_size": trainer.args.world_size, "device": trainer.args.device.type})
    sys.path.insert(0, str(ROOT / "packages/core/src"))
    from traincost_ci_core import normalize_training_config
    normalized = normalize_training_config(config, adapter="huggingface")
    if (normalized.model_name != profile["model_id"] or normalized.dataset_size != protocol["train_size"] or
            normalized.gpu_type != "APPLE_M1_MPS" or normalized.gpu_count != trainer.args.world_size or
            normalized.epochs != actual["num_train_epochs"] or
            normalized.batch_size != actual["per_device_train_batch_size"] or
            normalized.global_batch_size != (actual["per_device_train_batch_size"] *
                actual["gradient_accumulation_steps"] * trainer.args.world_size) or
            normalized.precision != "fp32" or normalized.mixed_precision is not False):
        raise WorkerError("Normalized HF config does not match actual training")
    attention = getattr(model.config, "_attn_implementation", None)
    if attention is not None and (not isinstance(attention, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", attention)):
        raise WorkerError("Invalid attention implementation")
    conditions = {"profile": profile, "model_files_sha256": selection["model_files_sha256"],
                  "subset_content_sha256": hashes, "environment": env,
                  "training_settings": {k: v for k, v in actual.items() if k != "num_train_epochs"},
                  "attention_implementation": attention}
    condition_sha256 = common.digest(conditions)
    torch.mps.synchronize()
    start = time.monotonic()
    trained = trainer.train()
    torch.mps.synchronize()
    training_seconds = time.monotonic() - start
    updates = protocol["train_size"] // settings["per_device_train_batch_size"] * epochs
    if (protocol["train_size"] % settings["per_device_train_batch_size"] or
            trainer.state.global_step != updates or safety.gradients != updates or len(safety.losses) != updates or
            not math.isfinite(trained.training_loss) or training_seconds <= 0):
        raise WorkerError("Invalid training result")
    check_start = time.monotonic()
    if not all(torch.isfinite(p).all().item() for p in model.parameters() if p.is_floating_point()):
        raise WorkerError("Nonfinite model parameters")
    after = dict(model.base_model.named_parameters())[name]
    encoder_changed = not torch.equal(before, after.detach().cpu())
    if not encoder_changed:
        raise WorkerError("Encoder did not update")
    torch.mps.synchronize()
    check_seconds = time.monotonic() - check_start
    torch.mps.synchronize()
    eval_start = time.monotonic()
    evaluated = trainer.evaluate()
    torch.mps.synchronize()
    evaluation_seconds = time.monotonic() - eval_start
    accuracy, f1 = float(evaluated["eval_accuracy"]), float(evaluated["eval_f1"])
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in (accuracy, f1)):
        raise WorkerError("Invalid evaluation metrics")
    check_source(workspace)
    return {"status": "PASS", "phase": phase, "epochs": epochs, "environment": env,
            "model_id": profile["model_id"], "model_revision": profile["revision"],
            "source_sha256": source_sha256, "profile_sha256": profile_sha256, "condition_sha256": condition_sha256,
            "config": config, "observed_training_arguments": actual, "attention_implementation": attention,
            "model_type": profile["model_type"], "parameter_count": parameter_count,
            "encoder_parameter_name": name, "encoder_updated": encoder_changed,
            "finite_gradients_checked": safety.gradients, "updates": updates,
            "training_loss": float(trained.training_loss), "losses": safety.losses,
            "accuracy": accuracy, "f1": f1, "loading_seconds": load_seconds,
            "tokenization_seconds": tokenize_seconds, "training_seconds": training_seconds,
            "parameter_check_seconds": check_seconds, "evaluation_seconds": evaluation_seconds,
            "sampled_peak_process_rss_bytes": safety.peak_rss,
            "sampled_peak_mps_allocated_bytes": safety.peak_mps, "subset_content_sha256": hashes}


def main(argv=None):
    parser = SafeParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=("prepare", "train"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--phase")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--parent-pid", required=True, type=int)
    output = None
    try:
        args = parser.parse_args(argv)
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            raise WorkerError("Worker cannot run in CI")
        check_supervisor(args.parent_pid)
        workspace = check_workspace(args.workspace)
        profiles = common.load_profiles()
        profile = common.profile_for(args.model)
        if profile["key"] != args.model or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", args.model):
            raise WorkerError("Invalid profile")
        if args.stage == "prepare":
            if args.phase is not None or args.epochs is not None:
                raise WorkerError("Unexpected prepare arguments")
            phase = "prepare"
        else:
            match = PHASE_PATTERN.fullmatch(args.phase or "")
            if not match or args.epochs != (3 if match.group(1) == "pr" else 1):
                raise WorkerError("Invalid phase or epochs")
            phase = args.phase
        model_dir = workspace / args.model
        if model_dir.is_symlink():
            raise WorkerError("Unsafe model directory")
        if args.stage == "prepare":
            model_dir.mkdir(mode=0o700, exist_ok=True)
            if not model_dir.is_dir() or any(model_dir.iterdir()):
                raise WorkerError("Existing model evidence")
        elif not model_dir.is_dir():
            raise WorkerError("Missing model directory")
        output = model_dir / (phase + ".json")
        if output.exists() or output.is_symlink():
            raise WorkerError("Existing stage evidence")
        source_sha256 = check_source(workspace)
        timeout = profiles["protocol"]["prepare_timeout_seconds"] if args.stage == "prepare" else profiles["protocol"]["run_timeout_seconds"]
        start_watchdog(args.parent_pid, timeout + 5)
        os.environ.update({"HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
                           "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1", "HF_HUB_DISABLE_PROGRESS_BARS": "1",
                           "TOKENIZERS_PARALLELISM": "false", "PYTORCH_ENABLE_MPS_FALLBACK": "0"})
        if args.stage == "train":
            os.environ.update({"HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1"})
        with open(os.devnull, "w", encoding="utf-8") as sink, redirect_stdout(sink), redirect_stderr(sink):
            result = (prepare(workspace, model_dir, profile, profiles, source_sha256) if args.stage == "prepare"
                      else train(workspace, model_dir, profile, profiles, phase, args.epochs, source_sha256))
        check_source(workspace)
        common.write_json(output, result)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        if output is not None and not output.exists() and not output.is_symlink():
            try:
                common.write_json(output, {"status": "FAIL", "error_type": safe_error_type(exc), "stage": args.stage})
            except (OSError, ValueError):
                pass
        print("Matrix worker failed; inspect the safe stage result.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
