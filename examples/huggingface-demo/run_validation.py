#!/usr/bin/env python3
"""Run the opt-in RTX 3060 validation in a new, private workspace."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from decimal import Decimal
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from common import HERE, ROOT, digest, file_digest, input_contract, read_json, source_fingerprint, validate_config, write_json


class DemoError(Exception):
    def __init__(self, message, status="FAIL", reason="VALIDATION_FAILED"):
        super().__init__(message)
        self.status = status
        self.reason = reason


@contextmanager
def workspace_lock(workspace):
    workspace.mkdir(parents=True, exist_ok=True)
    lock = workspace / ".traincost.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise DemoError("Workspace is locked; inspect for an interrupted run.") from None
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def save_state(workspace, state):
    temp = workspace / ".state.tmp"
    write_json(temp, state)
    os.replace(temp, workspace / "state.json")


def seal(workspace, state, path):
    state["artifacts"][str(path.relative_to(workspace))] = file_digest(path)


def check_seals(workspace, state):
    for name, expected in state["artifacts"].items():
        path = workspace / name
        if path.is_symlink() or not path.is_file() or file_digest(path) != expected:
            raise DemoError("Evidence changed or is missing.")


def worker_env(workspace, online=False):
    env = {key: os.environ[key] for key in ("PATH", "LD_LIBRARY_PATH", "LANG", "LC_ALL", "TZ", "TMPDIR",
                                            "CUDA_VISIBLE_DEVICES", "SYSTEMROOT") if key in os.environ}
    home = workspace / "cache/home"
    home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(home)
    env.update({"HF_HOME": str(workspace / "cache/hf"), "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1", "WANDB_DISABLED": "true",
                "HF_HUB_OFFLINE": "0" if online else "1", "HF_DATASETS_OFFLINE": "0" if online else "1",
                "TOKENIZERS_PARALLELISM": "false", "PYTHONNOUSERSITE": "1"})
    return env


def worker(workspace, stage, output, *, request=None, timeout=600, online=False):
    if output.exists():
        raise DemoError("Refusing to overwrite evidence.")
    cmd = [sys.executable, str(HERE / "worker.py"), stage, "--workspace", str(workspace), "--output", str(output),
           "--parent-pid", str(os.getpid())]
    if request is not None:
        cmd += ["--request", str(request)]
    proc = subprocess.Popen(cmd, env=worker_env(workspace, online), stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        code = proc.wait(timeout=timeout)
    except BaseException as exc:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        if isinstance(exc, subprocess.TimeoutExpired):
            raise DemoError("Worker timed out; outcome is inconclusive.", "INCONCLUSIVE", "TIMEOUT") from None
        raise
    if code or not output.is_file():
        reason = "WORKER_ERROR"
        if output.is_file():
            candidate = read_json(output).get("reason")
            if candidate in ("CUDA_OOM", "WORKER_ERROR"):
                reason = candidate
        failure = workspace / f"failure-{stage}.json"
        if not failure.exists():
            write_json(failure, {"status": "FAIL", "reason": reason})
        raise DemoError("Worker failed; inspect prerequisites and start with a new workspace.", reason=reason)
    return read_json(output)


def checked_environment(workspace, state):
    temporary = workspace / ".environment-check.json"
    if temporary.exists():
        raise DemoError("Interrupted environment check; use a new workspace.")
    try:
        actual = worker(workspace, "preflight", temporary, timeout=120)
    finally:
        temporary.unlink(missing_ok=True)
    if digest(actual) != state["environment_sha256"]:
        raise DemoError("Environment changed since preflight.")


def timed_training(workspace, state, kind, index, config):
    validate_config(config, 3 if kind == "pr" else 1)
    remaining = 3600 - state["spent_seconds"]
    if remaining <= 0:
        raise DemoError("Training time budget exhausted.", "INCONCLUSIVE")
    allowance = min(600, remaining)
    request = workspace / f"request-{kind}-{index}.json"
    result_path = workspace / f"run-{kind}-{index}.json"
    if request.exists() or result_path.exists():
        raise DemoError("Refusing to overwrite a run.")
    write_json(request, {"kind": kind, "config": config})
    seal(workspace, state, request)
    # Reserve the entire allowance before launch: a crash cannot restore the budget.
    state["spent_seconds"] += allowance
    save_state(workspace, state)
    start = time.monotonic()
    try:
        result = worker(workspace, "train", result_path, request=request, timeout=allowance)
    finally:
        elapsed = time.monotonic() - start
        state["spent_seconds"] -= max(0, allowance - elapsed)
        save_state(workspace, state)
    seal(workspace, state, result_path)
    save_state(workspace, state)
    return result


def action_report(base, pr):
    from oracle import decimal_cost
    path = ROOT / "packages/github-action/traincost_action.py"
    spec = importlib.util.spec_from_file_location("traincost_validation_action", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    base_config, pr_config = read_json(base), read_json(pr)
    comparison = module.analyze_configs(module.normalize_training_config(base_config),
                                        module.normalize_training_config(pr_config),
                                        gpu_hourly_prices={"RTX3060": 1.0})
    expected_costs = []
    for config, estimate in ((base_config, comparison.base_estimate), (pr_config, comparison.pr_estimate)):
        expected = decimal_cost(config["epochs"], config["estimated_minutes_per_epoch"], config["gpu_count"], "1.00")
        expected_costs.append(expected)
        if not math.isclose(estimate.estimated_cost_usd, float(expected), rel_tol=1e-12, abs_tol=1e-15):
            raise DemoError("Independent cost calculation does not match the core engine.")
    if not {"budget_exceeded", "precision_risk", "cost_increase"}.issubset({w.code for w in comparison.warnings}):
        raise DemoError("Expected TrainCost warnings are missing.")
    if base.parent != pr.parent:
        raise DemoError("Config files must share a directory.")
    previous = Path.cwd()
    try:
        os.chdir(base.parent)
        result = module.run_local_pair(Path(base.name), Path(pr.name), default_budget_limit_usd=None,
                                       gpu_hourly_prices={"RTX3060": 1.0})
    finally:
        os.chdir(previous)
    if result.status != "complete":
        raise DemoError("TrainCost could not generate a complete report.")
    for label, cost in zip(("Base branch", "This PR"), expected_costs):
        if f"{label}: ${float(cost):,.2f}" not in result.report:
            raise DemoError("Report rounding does not match the independent cost calculation.")
    return result.report


def write_new(path, text):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def preflight(workspace):
    if any(p.name != ".traincost.lock" for p in workspace.iterdir()):
        raise DemoError("Preflight requires a new empty workspace.")
    base, risky, _ = input_contract()
    fingerprint = source_fingerprint()
    state = {"schema": 1, "stage": "preflight-running", "spent_seconds": 0.0,
             "source_sha256": fingerprint, "artifacts": {}}
    save_state(workspace, state)
    env_path = workspace / "preflight.json"
    env = worker(workspace, "preflight", env_path, timeout=120)
    seal(workspace, state, env_path)
    state["environment_sha256"] = digest(env)
    report = action_report(HERE / "fixtures/base.json", HERE / "fixtures/risky.json")
    for expected in ("Base branch: $0.10", "This PR: $0.30", "Increase: +200%", "Mixed precision appears disabled"):
        if expected not in report:
            raise DemoError("Static fixture report did not match the expected calculation.")
    static_report = workspace / "static-report.md"
    write_new(static_report, report)
    seal(workspace, state, static_report)
    state["stage"] = "preflight"
    save_state(workspace, state)


def prepare(workspace, state):
    output = workspace / "selection.json"
    worker(workspace, "prepare", output, timeout=1800, online=True)
    seal(workspace, state, output)
    base, _, _ = input_contract()
    timed_training(workspace, state, "smoke", 1, base)


def calibrate(workspace, state):
    from oracle import decimal_cost, evaluate_measurements
    base, risky, _ = input_contract()
    seconds = [timed_training(workspace, state, "calibration", i, base)["training_seconds"] for i in range(1, 4)]
    if not evaluate_measurements(seconds, seconds, [value * 3 for value in seconds])["repeatable"]["calibration"]:
        raise DemoError("Calibration is not repeatable.")
    median = sorted(seconds)[1]
    minutes = Decimal(str(median)) / Decimal(60)
    budget = decimal_cost(1, minutes, 1, "1.00") * 2
    for name, config in (("base", base), ("pr", risky)):
        config["estimated_minutes_per_epoch"] = float(minutes)
        config["budget_limit_usd"] = float(budget)
        path = workspace / f"measured-{name}.json"
        if path.exists():
            raise DemoError("Refusing to overwrite measured config.")
        write_json(path, config)
        seal(workspace, state, path)
    report_path = workspace / "report.md"
    write_new(report_path, action_report(workspace / "measured-base.json", workspace / "measured-pr.json"))
    seal(workspace, state, report_path)
    path = workspace / "calibration.json"
    write_json(path, {"seconds": seconds, "median_seconds": median, "minutes_per_epoch": float(minutes),
                      "hypothetical_price_usd_per_gpu_hour": "1.00", "budget_usd": str(budget)})
    seal(workspace, state, path)


def verify(workspace, state):
    from oracle import decimal_cost, evaluate_measurements
    calibration = read_json(workspace / "calibration.json")
    calibration_runs = [read_json(workspace / f"run-calibration-{i}.json") for i in range(1, 4)]
    overhead = max(r["loading_seconds"] + r["tokenization_seconds"] + r.get("parameter_check_seconds", 0)
                   for r in calibration_runs)
    minimum_estimate = 3 * (4 * calibration["median_seconds"] + 2 * overhead)
    if minimum_estimate > 3600 - state["spent_seconds"]:
        raise DemoError("Insufficient budget for verification.", "INCONCLUSIVE", "BUDGET")
    base = validate_config(read_json(workspace / "measured-base.json"), 1)
    pr = validate_config(read_json(workspace / "measured-pr.json"), 3)
    if {**base, "epochs": 3} != pr:
        raise DemoError("Measured configs differ beyond epochs.")
    original, _, _ = input_contract()
    if {k: v for k, v in base.items() if k not in ("estimated_minutes_per_epoch", "budget_limit_usd")} != {
            k: v for k, v in original.items() if k not in ("estimated_minutes_per_epoch", "budget_limit_usd")}:
        raise DemoError("Measured training config changed.")
    results = {"base": [], "pr": []}
    for i in range(1, 4):
        order = (("base", base), ("pr", pr)) if i % 2 else (("pr", pr), ("base", base))
        for kind, config in order:
            results[kind].append(timed_training(workspace, state, kind, i, config)["training_seconds"])
    evaluation = evaluate_measurements(calibration["seconds"], results["base"], results["pr"])
    evaluation["hypothetical_base_usd"] = str(decimal_cost(1, base["estimated_minutes_per_epoch"], 1, "1.00"))
    evaluation["hypothetical_pr_usd"] = str(decimal_cost(3, pr["estimated_minutes_per_epoch"], 1, "1.00"))
    evaluation["price_note"] = "Hypothetical arithmetic input; not billed cost or electricity cost."
    path = workspace / "verification.json"
    write_json(path, evaluation)
    seal(workspace, state, path)
    if evaluation.get("status") != "PASS":
        raise DemoError("Measured time validation failed.")


def bundle(workspace, state):
    dest = workspace / "bundle"
    if dest.exists():
        raise DemoError("Refusing to overwrite bundle.")
    fixed = {"preflight.json", "static-report.md", "selection.json", "measured-base.json", "measured-pr.json",
             "calibration.json", "verification.json", "report.md", "outcome.json"}
    runs = {f"run-{kind}-{i}.json" for kind, count in (("smoke", 1), ("calibration", 3), ("base", 3), ("pr", 3))
            for i in range(1, count + 1)}
    requests = {name.replace("run-", "request-", 1) for name in runs}
    if set(state["artifacts"]) - fixed - runs - requests:
        raise DemoError("Evidence contains a non-allowlisted file.")
    names = sorted(name for name in state["artifacts"] if name in fixed | runs)
    sys.path.insert(0, str(ROOT / "packages/core/src"))
    from traincost_ci_core.safety import looks_sensitive
    schemas = {
        "preflight.json": {"python", "system", "machine", "kernel_release", "packages", "all_packages_sha256", "gpu", "driver", "cuda_runtime", "compute_capability", "total_vram_bytes"},
        "selection.json": {"model_files_sha256", "train", "test", "smoke", "prepare_seconds"},
        "calibration.json": {"seconds", "median_seconds", "minutes_per_epoch", "hypothetical_price_usd_per_gpu_hour", "budget_usd"},
        "verification.json": {"status", "calibration_median_seconds", "predicted_seconds", "observed_median_seconds", "relative_errors", "repeatable", "hypothetical_base_usd", "hypothetical_pr_usd", "price_note"},
        "outcome.json": {"stage", "status", "reason"},
    }
    run_fields = {"kind", "epochs", "updates", "training_seconds", "loading_seconds", "tokenization_seconds", "parameter_check_seconds", "peak_allocated_bytes", "training_loss"}
    for name in names:
        content = (workspace / name).read_text(encoding="utf-8")
        if looks_sensitive(content):
            raise DemoError("Evidence contains a credential-shaped value.")
        if name.endswith(".json"):
            value = read_json(workspace / name)
            expected = schemas.get(name)
            if name.startswith("run-"):
                expected = run_fields | ({"evaluation_seconds", "accuracy", "f1"} if name.startswith(("run-base-", "run-pr-")) else set())
            if name.startswith("measured-"):
                validate_config(value, 1 if name == "measured-base.json" else 3)
            elif expected is None or not isinstance(value, dict) or set(value) != expected:
                raise DemoError("Unexpected evidence schema.")
            if name == "preflight.json" and set(value["packages"]) != {"torch", "transformers", "accelerate", "datasets", "safetensors"}:
                raise DemoError("Unexpected package metadata.")
            if name == "selection.json":
                allowed_files = {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "vocab.txt", "special_tokens_map.json"}
                if not set(value["model_files_sha256"]).issubset(allowed_files):
                    raise DemoError("Unexpected model metadata.")
                for split in ("train", "test", "smoke"):
                    subset = value[split]
                    fields = {"size", "indices", "indices_sha256", "label_counts"}
                    if split != "smoke":
                        fields.add("content_sha256")
                    if (set(subset) != fields or not isinstance(subset["indices"], list)
                            or any(type(i) is not int or i < 0 for i in subset["indices"])):
                        raise DemoError("Unexpected subset metadata.")
            if name == "verification.json":
                for key in ("predicted_seconds", "observed_median_seconds", "relative_errors"):
                    if set(value[key]) != {"base", "pr"}:
                        raise DemoError("Unexpected verification metadata.")
                if set(value["repeatable"]) != {"calibration", "base", "pr"}:
                    raise DemoError("Unexpected repeatability metadata.")
                if value["status"] not in {"PASS", "FAIL"}:
                    raise DemoError("Unexpected verification status.")
            if name == "outcome.json" and (value["stage"] not in {"preflight", "prepare", "calibrate", "verify"}
                    or value["status"] not in {"FAIL", "INCONCLUSIVE"}
                    or value["reason"] not in {"VALIDATION_FAILED", "CUDA_OOM", "WORKER_ERROR", "TIMEOUT", "BUDGET", "INTERRUPTED"}):
                raise DemoError("Unexpected outcome metadata.")
    dest.mkdir()
    for name in names:
        shutil.copyfile(workspace / name, dest / name)
    write_json(dest / "bundle-manifest.json", {"files": {name: file_digest(dest / name) for name in names},
                                                "status": state.get("status", "PASS"), "source_sha256": state["source_sha256"]})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicit, local-only RTX 3060 validation")
    parser.add_argument("stage", choices=("preflight", "prepare", "calibrate", "verify", "bundle"))
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args(argv)
    raw_workspace = args.workspace.expanduser().absolute()
    workspace = raw_workspace.resolve()
    state = None
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def interrupted(_signum, _frame):
        raise DemoError("Run interrupted.", "INCONCLUSIVE", "INTERRUPTED")

    try:
        signal.signal(signal.SIGTERM, interrupted)
        if any(path.is_symlink() for path in (raw_workspace, *raw_workspace.parents)):
            raise DemoError("Workspace paths may not contain symlinks.")
        if os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"):
            raise DemoError("This experiment is not allowed in CI or pull requests.")
        with workspace_lock(workspace):
            if args.stage == "preflight":
                # Only a newly claimed empty workspace can belong to this attempt.
                if any(p.name != ".traincost.lock" for p in workspace.iterdir()):
                    raise DemoError("Preflight requires a new empty workspace.")
                try:
                    preflight(workspace)
                except Exception as exc:
                    if (workspace / "state.json").is_file():
                        failed = read_json(workspace / "state.json")
                        outcome = {"stage": "preflight", "status": exc.status if isinstance(exc, DemoError) else "FAIL",
                                   "reason": exc.reason if isinstance(exc, DemoError) else "WORKER_ERROR"}
                        write_new(workspace / "outcome.json", json.dumps(outcome, indent=2, sort_keys=True) + "\n")
                        seal(workspace, failed, workspace / "outcome.json")
                        failed.update(stage="failed", status=outcome["status"])
                        save_state(workspace, failed)
                    raise
            else:
                state = read_json(workspace / "state.json")
                if state["source_sha256"] != source_fingerprint():
                    raise DemoError("Source or experiment contract changed since preflight.")
                check_seals(workspace, state)
                previous = {"prepare": "preflight", "calibrate": "prepare", "verify": "calibrate", "bundle": "verify"}
                if state["stage"] != previous[args.stage] and not (args.stage == "bundle" and state["stage"] == "failed"):
                    raise DemoError("Unexpected stage; evidence cannot be overwritten or resumed.")
                if args.stage != "bundle" and ((workspace / "outcome.json").exists() or (workspace / "outcome.json").is_symlink()):
                    raise DemoError("Refusing to overwrite an outcome.")
                state["stage"] = args.stage + "-running"
                save_state(workspace, state)
                try:
                    if args.stage != "bundle":
                        checked_environment(workspace, state)
                    {"prepare": prepare, "calibrate": calibrate, "verify": verify, "bundle": bundle}[args.stage](workspace, state)
                except (Exception, KeyboardInterrupt) as exc:
                    if args.stage != "bundle":
                        outcome = {"stage": args.stage,
                                   "status": exc.status if isinstance(exc, DemoError) else ("INCONCLUSIVE" if isinstance(exc, KeyboardInterrupt) else "FAIL"),
                                   "reason": exc.reason if isinstance(exc, DemoError) else "WORKER_ERROR"}
                        write_new(workspace / "outcome.json", json.dumps(outcome, indent=2, sort_keys=True) + "\n")
                        seal(workspace, state, workspace / "outcome.json")
                        state.update(stage="failed", status=outcome["status"])
                        save_state(workspace, state)
                    raise
                state["stage"] = args.stage
                save_state(workspace, state)
        if args.stage == "bundle":
            print(f"bundle: PASS; experiment: {state.get('status', 'PASS')}")
        else:
            print(f"{args.stage}: PASS")
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        status = exc.status if isinstance(exc, DemoError) else ("INCONCLUSIVE" if isinstance(exc, KeyboardInterrupt) else "FAIL")
        # Do not serialize exception text, paths, subprocess output, or environment values.
        print(f"{args.stage}: {status}; stage did not complete. Use a new workspace after investigation.", file=sys.stderr)
        return 2 if status == "INCONCLUSIVE" else 1
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)


if __name__ == "__main__":
    raise SystemExit(main())
