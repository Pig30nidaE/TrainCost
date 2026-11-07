"""Opt-in real-model Mac smoke, separate from the RTX 3060 experiment."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples/huggingface-demo"
sys.path.insert(0, str(DEMO))
from common import digest, file_digest, input_contract, read_json, source_fingerprint
from run_validation import worker_env
from worker import balanced_indices, dataset_hash, prepare


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def execution_fingerprint():
    return digest({"cuda_demo_and_core": source_fingerprint(), "mac_files": {
        str(path.relative_to(ROOT)): file_digest(path) for path in
        (Path(__file__).resolve(), DEMO / "macos-requirements.in", DEMO / "macos-requirements.lock")}})


def check_phase(workspace, phase, parent_pid):
    if parent_pid is None or parent_pid <= 1 or os.getppid() != parent_pid or os.getpgrp() != os.getpid():
        raise ValueError("Stage requires its supervising process")
    paths = [workspace / f"{phase}.json"]
    if phase == "prepare":
        paths.append(workspace / "selection.json")
    if any(path.exists() or path.is_symlink() for path in paths):
        raise ValueError("Existing stage evidence must be preserved")
    if read_json(workspace / "run-contract.json")["source_sha256"] != execution_fingerprint():
        raise ValueError("Execution source changed")


def smoke_config(device, epochs, minutes=6.0, budget=.2):
    if device not in {"cpu", "mps"} or type(epochs) is not int or epochs not in {1, 3}:
        raise ValueError("Unsupported smoke settings")
    base, _, _ = input_contract()
    return {**base, "epochs": epochs, "dataset_size": 64,
            "gpu_type": "APPLE_M1_MPS" if device == "mps" else "MAC_CPU_ASSUMED_UNIT",
            "estimated_minutes_per_epoch": minutes, "budget_limit_usd": budget}


def training_settings(config):
    return {"num_train_epochs": config["epochs"], "max_steps": -1,
            "per_device_train_batch_size": config["batch_size"], "per_device_eval_batch_size": 8,
            "gradient_accumulation_steps": 1, "learning_rate": 2e-5,
            "lr_scheduler_type": "constant", "warmup_steps": 0, "optim": "adamw_torch",
            "fp16": False, "bf16": False, "tf32": False, "seed": 42, "data_seed": 42,
            "save_strategy": "no", "eval_strategy": "no", "logging_strategy": "steps",
            "logging_steps": 1, "logging_nan_inf_filter": False, "report_to": "none",
            "push_to_hub": False, "disable_tqdm": True, "dataloader_num_workers": 0,
            "dataloader_pin_memory": False}


def check_environment(device):
    import psutil
    import torch
    from packaging.requirements import Requirement
    if platform.system() != "Darwin" or platform.machine() != "arm64" or sys.version_info[:2] != (3, 12):
        raise ValueError("Mac arm64 with Python 3.12 required")
    for raw in (DEMO / "macos-requirements.lock").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "--")):
            continue
        requirement = Requirement(line.rstrip(" \\"))
        if requirement.marker and not requirement.marker.evaluate():
            continue
        if not requirement.specifier.contains(importlib.metadata.version(requirement.name), prereleases=True):
            raise ValueError("Installed dependency differs from Mac lock")
    if psutil.virtual_memory().available < 3 * 1024**3:
        raise ValueError("At least 3 GiB available system memory required")
    if device == "mps" and not torch.backends.mps.is_available():
        raise ValueError("MPS unavailable; no automatic CPU fallback")
    torch.set_num_threads(4)
    if device == "mps":
        torch.mps.set_per_process_memory_fraction(.45)
    return {"os": platform.mac_ver(), "machine": platform.machine(), "python": platform.python_version(),
            "device": device, "packages": {name: importlib.metadata.version(name) for name in
                ("torch", "transformers", "accelerate", "datasets", "safetensors", "numpy", "huggingface-hub")},
            "lock_sha256": file_digest(DEMO / "macos-requirements.lock")}


def train(workspace, device, epochs):
    import numpy as np
    import psutil
    import torch
    from datasets import load_from_disk
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainerCallback, TrainingArguments, set_seed
    env = check_environment(device)
    config = smoke_config(device, epochs)
    selection = read_json(workspace / "selection.json")
    model_dir = workspace / "cache/model"
    for name, expected in selection["model_files_sha256"].items():
        if file_digest(model_dir / name) != expected:
            raise ValueError("Model file changed")
    data = {}
    indices = {}
    for split in ("train", "test"):
        full = load_from_disk(str(workspace / f"cache/selected-{split}"))
        if dataset_hash(full) != selection[split]["content_sha256"]:
            raise ValueError("Dataset changed")
        local = balanced_indices(full, 64, 42)
        data[split] = full.select(local)
        indices[split] = [selection[split]["indices"][i] for i in local]
        if [list(data[split]["label"]).count(i) for i in (0, 1)] != [32, 32]:
            raise ValueError("Subset balance mismatch")
    data_hashes = {split: dataset_hash(value) for split, value in data.items()}
    set_seed(42)
    start_load = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True, token=False, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir), num_labels=2,
        local_files_only=True, token=False, trust_remote_code=False, use_safetensors=True)
    if any(p.is_floating_point() and p.dtype != torch.float32 for p in model.parameters()):
        raise ValueError("Expected FP32 model")
    before = next(model.distilbert.parameters()).detach().cpu().clone()
    load_seconds = time.monotonic() - start_load
    start_tokenize = time.monotonic()
    def tokenize(batch):
        return tokenizer(batch["text"], max_length=128, padding="max_length", truncation=True)
    data = {split: value.map(tokenize, batched=True, remove_columns=["text"]).rename_column("label", "labels")
            for split, value in data.items()}
    tokenization_seconds = time.monotonic() - start_tokenize

    class Safety(TrainerCallback):
        def __init__(self):
            self.gradients = 0
            self.losses = []
            self.peak_rss = 0
            self.peak_mps = 0
        def on_pre_optimizer_step(self, args, state, control, model=None, **kwargs):
            if psutil.virtual_memory().available < 1024**3:
                raise ValueError("Memory reserve exhausted")
            grads = [p.grad for p in model.parameters() if p.grad is not None]
            if not grads or not all(torch.isfinite(g).all().item() for g in grads):
                raise ValueError("Nonfinite or absent gradients")
            if not any(torch.count_nonzero(g).item() for g in grads):
                raise ValueError("All gradients are zero")
            self.gradients += 1
            self.peak_rss = max(self.peak_rss, psutil.Process().memory_info().rss)
            if device == "mps":
                self.peak_mps = max(self.peak_mps, torch.mps.current_allocated_memory())
        def on_log(self, args, state, control, logs=None, **kwargs):
            for key in ("loss", "grad_norm"):
                if logs and key in logs and not math.isfinite(logs[key]):
                    raise ValueError("Nonfinite training metric")
            if logs and "loss" in logs:
                self.losses.append(logs["loss"])

    def metrics(prediction):
        labels, predicted = prediction.label_ids, np.argmax(prediction.predictions, axis=-1)
        tp = int(((predicted == 1) & (labels == 1)).sum())
        fp = int(((predicted == 1) & (labels == 0)).sum())
        fn = int(((predicted == 0) & (labels == 1)).sum())
        return {"accuracy": float((predicted == labels).mean()), "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0}
    args = TrainingArguments(output_dir=str(workspace / "cache/trainer-output"), use_cpu=device == "cpu", **training_settings(config))
    safety = Safety()
    trainer = Trainer(model=model, args=args, train_dataset=data["train"], eval_dataset=data["test"], compute_metrics=metrics, callbacks=[safety])
    if trainer.args.device.type != device or trainer.args.world_size != 1 or next(model.parameters()).device.type != device:
        raise ValueError("Actual training device mismatch")
    sync = torch.mps.synchronize if device == "mps" else lambda: None
    sync()
    start = time.monotonic()
    trained = trainer.train()
    sync()
    training_seconds = time.monotonic() - start
    updates = 8 * epochs
    if trainer.state.global_step != updates or safety.gradients != updates or len(safety.losses) != updates:
        raise ValueError("Unexpected update or safety-check count")
    if not math.isfinite(trained.training_loss) or training_seconds <= 0:
        raise ValueError("Invalid training result")
    if not all(torch.isfinite(p).all().item() for p in model.parameters()):
        raise ValueError("Nonfinite final weights")
    if torch.equal(before, next(model.distilbert.parameters()).detach().cpu()):
        raise ValueError("Encoder was not updated")
    sync()
    start_eval = time.monotonic()
    evaluated = trainer.evaluate()
    sync()
    return {"status": "PASS", "scope": "MAC_COMPATIBILITY_ONLY", "environment": env, "config": config,
            "updates": updates, "training_seconds": training_seconds, "loading_seconds": load_seconds,
            "tokenization_seconds": tokenization_seconds, "evaluation_seconds": time.monotonic() - start_eval,
            "training_loss": trained.training_loss, "losses": safety.losses, "encoder_changed": True,
            "finite_gradients_checked": safety.gradients, "accuracy": evaluated["eval_accuracy"], "f1": evaluated["eval_f1"],
            "sampled_peak_process_rss_bytes": safety.peak_rss, "sampled_peak_mps_allocated_bytes": safety.peak_mps,
            "subset_source_indices": indices, "subset_content_sha256": data_hashes}


def run_child(workspace, phase, device):
    timeout = 1200 if phase == "prepare" else 600
    env = worker_env(workspace, online=phase == "prepare")
    env.update({"PYTORCH_ENABLE_MPS_FALLBACK": "0", "HF_HUB_DISABLE_XET": "1"})
    command = [sys.executable, str(Path(__file__).resolve()), "--workspace", str(workspace), "--device", device,
               "--phase", phase, "--parent-pid", str(os.getpid())]
    proc = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        proc.wait(timeout=timeout)
    except BaseException:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        raise
    result = read_json(workspace / f"{phase}.json")
    if proc.returncode or result.get("status") != "PASS":
        raise RuntimeError("Isolated stage failed")
    print(f"{phase}: PASS", flush=True)
    return result


def check_report(workspace, device, base_run, pr_run):
    from oracle import decimal_cost
    sys.path.insert(0, str(ROOT / "packages/core/src"))
    from traincost_ci_core import analyze_config_dicts
    if (base_run["subset_content_sha256"] != pr_run["subset_content_sha256"] or
            base_run["environment"] != pr_run["environment"]):
        raise ValueError("Pair conditions differ")
    minutes = base_run["training_seconds"] / 60
    budget = float(decimal_cost(1, minutes) * 2)
    base, pr = (smoke_config(device, epochs, minutes, budget) for epochs in (1, 3))
    result = analyze_config_dicts(base, pr, gpu_hourly_prices={base["gpu_type"]: 1.0})
    for config, estimate in ((base, result.base_estimate), (pr, result.pr_estimate)):
        if not math.isclose(estimate.estimated_cost_usd, float(decimal_cost(config["epochs"], minutes)), rel_tol=1e-12):
            raise ValueError("Decimal/core cost mismatch")
    if not {"cost_increase", "epochs_increased", "budget_exceeded", "precision_risk"}.issubset({w.code for w in result.warnings}):
        raise ValueError("Expected report warning missing")
    write_json(workspace / "measured-base.json", base)
    write_json(workspace / "measured-pr.json", pr)
    with (workspace / "report.md").open("x", encoding="utf-8") as stream:
        stream.write("# Mac compatibility smoke\n\nHypothetical $1/hour arithmetic only, not billing or CUDA evidence.\n"
            "One run per condition, no independent calibration or accuracy claim.\n\n" + result.markdown_report)
    return {"base_seconds": base_run["training_seconds"], "pr_seconds": pr_run["training_seconds"],
            "predicted_pr_seconds_from_single_base_run": 3 * base_run["training_seconds"],
            "cost_increase_percent": result.increase_percent, "warnings": [w.code for w in result.warnings]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--device", required=True, choices=("mps", "cpu"))
    parser.add_argument("--phase", choices=("prepare", "base", "pr"), help=argparse.SUPPRESS)
    parser.add_argument("--parent-pid", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    workspace = args.workspace.expanduser().resolve()
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        parser.error("Actual model smoke is local-only")
    if args.phase:
        try:
            check_phase(workspace, args.phase, args.parent_pid)
        except Exception:
            print("Stage refused; existing evidence was not changed", file=sys.stderr)
            return 1
        deadline = time.monotonic() + (1205 if args.phase == "prepare" else 605)
        def supervise():
            while True:
                if os.getppid() != args.parent_pid or time.monotonic() > deadline:
                    os.killpg(os.getpid(), signal.SIGKILL)
                time.sleep(.25)
        threading.Thread(target=supervise, daemon=True).start()
        try:
            if args.phase == "prepare":
                check_environment(args.device)
                selection = prepare(workspace, input_contract()[2])
                write_json(workspace / "selection.json", selection)
                result = {"status": "PASS"}
            else:
                result = train(workspace, args.device, 1 if args.phase == "base" else 3)
            if read_json(workspace / "run-contract.json")["source_sha256"] != execution_fingerprint():
                raise ValueError("Execution source changed during stage")
            write_json(workspace / f"{args.phase}.json", result)
            return 0
        except Exception as exc:
            try:
                write_json(workspace / f"{args.phase}.json", {"status": "FAIL", "error_type": type(exc).__name__})
            except FileExistsError:
                pass
            return 1
    if workspace.exists():
        parser.error("Use a new workspace; evidence is never overwritten")
    workspace.mkdir(parents=True, mode=0o700)
    fingerprint = execution_fingerprint()
    write_json(workspace / "run-contract.json", {"source_sha256": fingerprint})
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        run_child(workspace, "prepare", args.device)
        base = run_child(workspace, "base", args.device)
        pr = run_child(workspace, "pr", args.device)
        comparison = check_report(workspace, args.device, base, pr)
        if execution_fingerprint() != fingerprint:
            raise ValueError("Execution source changed")
        write_json(workspace / "result.json", {"status": "PASS", "scope": "MAC_COMPATIBILITY_ONLY",
            "model": input_contract()[2]["model"], "model_revision": input_contract()[2]["model_revision"],
            "dataset_revision": input_contract()[2]["dataset_revision"], "comparison": comparison,
            "script_sha256": file_digest(Path(__file__)), "source_sha256": fingerprint, "cuda_validation": "NOT RUN"})
        print("PASS: real model training and report arithmetic; CUDA/timing acceptance NOT RUN")
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        status = "INCONCLUSIVE" if isinstance(exc, (subprocess.TimeoutExpired, KeyboardInterrupt)) else "FAIL"
        write_json(workspace / "result.json", {"status": status, "scope": "MAC_COMPATIBILITY_ONLY", "error_type": type(exc).__name__})
        print(f"{status}: inspect safe stage artifacts; no automatic retry", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
