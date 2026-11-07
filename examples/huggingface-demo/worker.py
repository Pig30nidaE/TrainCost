"""Isolated worker. Heavy dependencies are imported only inside an explicit stage."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import math
import platform
import os
from pathlib import Path
import random
import re
import subprocess
import signal
import sys
import time
from urllib.parse import unquote, urlparse

from common import HERE, digest, file_digest, input_contract, read_json, validate_config, write_json
from model_safety import DISTILBERT_METADATA, validate_local_model


def arm_parent_death_signal(parent_pid):
    if sys.platform != "linux":
        return
    if parent_pid <= 1 or os.getppid() != parent_pid:
        raise ValueError("parent process changed")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "could not arm parent-death signal")
    if os.getppid() != parent_pid:
        raise ValueError("parent process changed")


def validate_cuda_wheel(url_text, installed):
    from packaging.utils import canonicalize_name, parse_wheel_filename
    from packaging.version import Version
    url = urlparse(url_text)
    name, version, _, tags = parse_wheel_filename(Path(unquote(url.path)).name)
    if (canonicalize_name(name) != "torch" or version.local != "cu130"
            or url.scheme != "https" or url.netloc != "download.pytorch.org" or url.query
            or not url.path.startswith("/whl/cu130/")
            or not re.fullmatch(r"sha256=[a-f0-9]{64}", url.fragment)
            or {str(tag) for tag in tags} != {"cp312-cp312-manylinux_2_28_x86_64"}
            or Version(installed) != version):
        raise ValueError("Invalid or mismatched CUDA wheel")


def validate_cuda_runtime(driver, runtime):
    if (not isinstance(driver, str) or not re.fullmatch(r"\d{3,4}(?:\.\d{1,3}){1,2}", driver)
            or int(driver.split(".")[0]) < 580 or runtime != "13.0"):
        raise ValueError("CUDA 13.0 and an R580-or-newer host driver are required")


def environment():
    import torch
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Python 3.12 required")
    system, machine, kernel = platform.system(), platform.machine(), platform.release()
    if system != "Linux" or machine != "x86_64" or "microsoft" not in kernel.lower() or "wsl2" not in kernel.lower():
        raise ValueError("WSL2 Ubuntu x86-64 required")
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    versions = {}
    for line in (HERE / "requirements.lock").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "--")):
            continue
        requirement = Requirement(line.split(" --hash=", 1)[0].rstrip(" \\"))
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        installed = importlib.metadata.version(requirement.name)
        if requirement.url:
            if canonicalize_name(requirement.name) != "torch":
                raise ValueError("Unexpected direct dependency URL")
            validate_cuda_wheel(requirement.url, installed)
        else:
            if len(list(requirement.specifier)) != 1 or not str(requirement.specifier).startswith("=="):
                raise ValueError("requirements must use exact pins")
            if not requirement.specifier.contains(installed, prereleases=True):
                raise ValueError("installed dependency does not match lock")
        versions[requirement.name.lower()] = installed
    if not {"torch", "transformers", "accelerate", "datasets", "safetensors"}.issubset(versions):
        raise ValueError("incomplete dependency lock")
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise ValueError("dependency or CUDA check failed")
    info = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                          check=True, capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
    if len(info) != 1:
        raise ValueError("exactly one physical GPU is required")
    name, driver = (part.strip() for part in info[0].split(",", 1))
    validate_cuda_runtime(driver, torch.version.cuda)
    if "RTX 3060" not in name or "RTX 3060" not in torch.cuda.get_device_name(0):
        raise ValueError("RTX 3060 required")
    free, total = torch.cuda.mem_get_info(0)
    if free < 8 * 1024**3 or total < 11 * 1024**3:
        raise ValueError("insufficient GPU memory")
    distributions = sorted((d.metadata.get("Name", "").lower(), d.version)
                           for d in importlib.metadata.distributions())
    selected = {key: versions[key] for key in ("torch", "transformers", "accelerate", "datasets", "safetensors")}
    return {"python": ".".join(map(str, sys.version_info[:3])), "system": system, "machine": machine,
            "kernel_release": kernel, "packages": selected,
            "all_packages_sha256": digest(distributions), "gpu": name, "driver": driver,
            "cuda_runtime": torch.version.cuda, "compute_capability": list(torch.cuda.get_device_capability(0)),
            "total_vram_bytes": total}


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def balanced_indices(dataset, count, seed, excluded_text_hashes=frozenset()):
    labels = dataset["label"]
    rng = random.Random(seed)
    excluded_indices = set()
    if excluded_text_hashes:
        excluded_indices = {i for i, text in enumerate(dataset["text"]) if text_hash(text) in excluded_text_hashes}
    groups = [[i for i, label in enumerate(labels) if label == target and i not in excluded_indices] for target in (0, 1)]
    if any(len(group) < count // 2 for group in groups) or count % 2:
        raise ValueError("dataset cannot provide balanced subset")
    result = rng.sample(groups[0], count // 2) + rng.sample(groups[1], count // 2)
    rng.shuffle(result)
    return result


def dataset_hash(dataset):
    return digest([[row["text"], row["label"]] for row in dataset])


def prepare(workspace, manifest):
    from datasets import load_dataset
    from huggingface_hub import hf_hub_download, snapshot_download
    start = time.monotonic()
    cache = workspace / "cache"
    snapshot_download(repo_id=manifest["model"], revision=manifest["model_revision"], token=False,
                      local_dir=str(cache / "model"), allow_patterns=["config.json", "model.safetensors",
                      "tokenizer.json", "tokenizer_config.json", "vocab.txt", "special_tokens_map.json"])
    model_dir = cache / "model"
    allowed = {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "vocab.txt", "special_tokens_map.json"}
    model_files = {path.name: file_digest(path) for path in model_dir.iterdir()
                   if path.name in allowed and path.is_file() and not path.is_symlink()}
    if not {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "vocab.txt"}.issubset(model_files):
        raise ValueError("model files missing")
    selections = {"model_files_sha256": model_files}
    train_text_hashes = set()
    for split, size in (("train", manifest["train_size"]), ("test", manifest["test_size"])):
        parquet = hf_hub_download(repo_id=manifest["dataset"], repo_type="dataset",
                    revision=manifest["dataset_revision"], filename=f"plain_text/{split}-00000-of-00001.parquet",
                    cache_dir=str(cache / "hub"), token=False)
        data = load_dataset("parquet", data_files=parquet, split="train", cache_dir=str(cache / "datasets"))
        indices = balanced_indices(data, size, manifest["seed"], train_text_hashes)
        selected = data.select(indices)
        selected.save_to_disk(str(cache / ("selected-" + split)))
        selections[split] = {"size": size, "indices": indices, "indices_sha256": digest(indices),
                             "content_sha256": dataset_hash(selected), "label_counts": [size // 2, size // 2]}
        if split == "train":
            train_text_hashes = {text_hash(text) for text in selected["text"]}
            smoke_indices = balanced_indices(selected, manifest["smoke_size"], manifest["seed"])
            selections["smoke"] = {"size": len(smoke_indices), "indices": smoke_indices,
                                    "indices_sha256": digest(smoke_indices), "label_counts": [32, 32]}
    selections["prepare_seconds"] = time.monotonic() - start
    return selections


def train(workspace, request, manifest):
    import numpy as np
    import torch
    from datasets import load_from_disk
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer, Trainer,
                              TrainerCallback, TrainingArguments, set_seed)

    config = validate_config(request["config"])
    smoke = request["kind"] == "smoke"
    if environment() != read_json(workspace / "preflight.json"):
        raise ValueError("environment changed")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    set_seed(manifest["seed"])
    load_start = time.monotonic()
    selections = read_json(workspace / "selection.json")
    model_dir_path = workspace / "cache/model"
    actual_files = {path.name for path in model_dir_path.iterdir() if path.name != ".cache"}
    if actual_files != set(selections["model_files_sha256"]):
        raise ValueError("prepared model file set changed")
    for name, expected in selections["model_files_sha256"].items():
        path = model_dir_path / name
        if path.is_symlink() or not path.is_file() or file_digest(path) != expected:
            raise ValueError("prepared model files changed")
    train_data = load_from_disk(str(workspace / "cache/selected-train"))
    test_data = load_from_disk(str(workspace / "cache/selected-test"))
    if (dataset_hash(train_data) != selections["train"]["content_sha256"] or
            dataset_hash(test_data) != selections["test"]["content_sha256"]):
        raise ValueError("prepared dataset changed")
    if smoke:
        train_data = train_data.select(selections["smoke"]["indices"])
        labels = list(train_data["label"])
        if [labels.count(label) for label in (0, 1)] != [32, 32]:
            raise ValueError("smoke subset is not balanced")
    model_dir = str(workspace / "cache/model")
    validate_local_model(model_dir, "distilbert", hashes=DISTILBERT_METADATA)
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, token=False, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir, num_labels=2, local_files_only=True,
                                                               token=False, trust_remote_code=False,
                                                               use_safetensors=True)
    if any(p.is_floating_point() and p.dtype != torch.float32 for p in model.parameters()):
        raise ValueError("model is not FP32")
    encoder_before = next(model.distilbert.parameters()).detach().clone() if smoke else None
    load_seconds = time.monotonic() - load_start
    token_start = time.monotonic()
    def tokenize(batch):
        return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=manifest["max_length"])
    train_data = train_data.map(tokenize, batched=True, remove_columns=["text"]).rename_column("label", "labels")
    test_data = test_data.map(tokenize, batched=True, remove_columns=["text"]).rename_column("label", "labels")
    tokenize_seconds = time.monotonic() - token_start

    class Safety(TrainerCallback):
        def __init__(self):
            self.gradient_seen = False
            self.loss_seen = False
        def on_pre_optimizer_step(self, args, state, control, model=None, **kwargs):
            free, total = torch.cuda.mem_get_info(0)
            if free < total * .1 or torch.cuda.max_memory_allocated() > total * .9:
                raise ValueError("VRAM limit")
            if smoke:
                grads = [p.grad for p in model.parameters() if p.grad is not None]
                if not grads or not all(torch.isfinite(g).all().item() for g in grads):
                    raise ValueError("non-finite gradient")
                self.gradient_seen = self.gradient_seen or any(torch.count_nonzero(g).item() for g in grads)
        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs and "loss" in logs:
                self.loss_seen = True
                if not math.isfinite(logs["loss"]):
                    raise ValueError("non-finite loss")
            if logs and "grad_norm" in logs and not math.isfinite(logs["grad_norm"]):
                raise ValueError("non-finite gradient norm")

    args = TrainingArguments(output_dir=str(workspace / "cache/trainer-output"),
        num_train_epochs=config["epochs"], max_steps=-1, per_device_train_batch_size=config["batch_size"],
        per_device_eval_batch_size=config["batch_size"], gradient_accumulation_steps=1,
        learning_rate=manifest["learning_rate"], lr_scheduler_type="constant", warmup_steps=0,
        optim="adamw_torch", fp16=False, bf16=False, tf32=False, seed=manifest["seed"],
        data_seed=manifest["seed"], save_strategy="no", eval_strategy="no", logging_strategy="steps",
        logging_steps=1, logging_nan_inf_filter=False, report_to="none", push_to_hub=False,
        disable_tqdm=True, dataloader_num_workers=0, use_cpu=False)
    if (args.num_train_epochs != config["epochs"] or args.max_steps != -1 or
            args.per_device_train_batch_size != config["batch_size"] or args.gradient_accumulation_steps != 1 or
            args.fp16 or args.bf16 or args.tf32 or args.warmup_steps != 0):
        raise ValueError("training arguments mismatch")
    safety = Safety()
    def metrics(prediction):
        labels = prediction.label_ids
        predictions = np.argmax(prediction.predictions, axis=-1)
        tp = int(((predictions == 1) & (labels == 1)).sum())
        fp = int(((predictions == 1) & (labels == 0)).sum())
        fn = int(((predictions == 0) & (labels == 1)).sum())
        return {"accuracy": float((predictions == labels).mean()),
                "f1": float(2 * tp / (2 * tp + fp + fn)) if 2 * tp + fp + fn else 0.0}
    trainer = Trainer(model=model, args=args, train_dataset=train_data, eval_dataset=test_data,
                      compute_metrics=metrics, callbacks=[safety])
    if trainer.args.device.type != "cuda" or trainer.args.world_size != 1:
        raise ValueError("single CUDA GPU required")
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    start = time.monotonic()
    result = trainer.train()
    torch.cuda.synchronize()
    seconds = time.monotonic() - start
    parameter_check_start = time.monotonic()
    if not all(torch.isfinite(p).all().item() for p in model.parameters() if p.is_floating_point()):
        raise ValueError("non-finite model parameter")
    torch.cuda.synchronize()
    parameter_check_seconds = time.monotonic() - parameter_check_start
    free, total = torch.cuda.mem_get_info(0)
    if free < total * .1 or torch.cuda.max_memory_allocated() > total * .9:
        raise ValueError("VRAM limit")
    expected_steps = (8 if smoke else 128 * config["epochs"])
    if (trainer.state.global_step != expected_steps or not math.isfinite(result.training_loss)
            or not safety.loss_seen or seconds <= 0):
        raise ValueError("training validation failed")
    if smoke and (not safety.gradient_seen or torch.equal(encoder_before, next(model.distilbert.parameters()).detach().cpu())):
        raise ValueError("smoke did not update encoder")
    output = {"kind": request["kind"], "epochs": config["epochs"], "updates": expected_steps,
              "training_seconds": seconds, "loading_seconds": load_seconds, "tokenization_seconds": tokenize_seconds,
              "parameter_check_seconds": parameter_check_seconds,
              "peak_allocated_bytes": torch.cuda.max_memory_allocated(), "training_loss": result.training_loss}
    if request["kind"] in ("base", "pr"):
        torch.cuda.synchronize()
        eval_start = time.monotonic()
        evaluated = trainer.evaluate()
        torch.cuda.synchronize()
        output.update({"evaluation_seconds": time.monotonic() - eval_start,
                       "accuracy": evaluated["eval_accuracy"], "f1": evaluated["eval_f1"]})
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("preflight", "prepare", "train"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    args = parser.parse_args()
    try:
        arm_parent_death_signal(args.parent_pid)
        _, _, manifest = input_contract()
        if args.stage == "preflight":
            result = environment()
        elif args.stage == "prepare":
            result = prepare(args.workspace, manifest)
        else:
            result = train(args.workspace, read_json(args.request), manifest)
        write_json(args.output, result)
        return 0
    except Exception as exc:
        torch = sys.modules.get("torch")
        reason = "CUDA_OOM" if torch and isinstance(exc, torch.cuda.OutOfMemoryError) else "WORKER_ERROR"
        try:
            write_json(args.output, {"status": "FAIL", "reason": reason})
        except OSError:
            pass
        print("Worker failed; check CUDA, dependency, cache and experiment requirements.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
