"""Opt-in local MPS study; CI runs its contract tests, never model training."""
from __future__ import annotations

import argparse
from decimal import Decimal
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "examples/hf-model-matrix"
sys.path.insert(0, str(MATRIX))
sys.path.insert(1, str(ROOT / "examples/huggingface-demo"))
from matrix_common import (digest, file_digest, hf_config, load_profiles, read_json,
                           source_fingerprint, training_settings, validate_profiles, write_json)
from oracle import decimal_cost, evaluate_measurements
from run_validation import _verify_cost_display, worker_env
from provenance import capture_snapshot, validate_snapshot


class MatrixError(Exception):
    def __init__(self, reason, status="FAIL"):
        self.reason, self.status = reason, status
        super().__init__(reason)


def claim_workspace(path):
    path = Path(path).expanduser().absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise MatrixError("UNSAFE_WORKSPACE")
    path.mkdir(mode=0o700, parents=False, exist_ok=False)
    return path


def run_process(command, env, timeout, *, cwd=None):
    process = subprocess.Popen(command, env=env, cwd=cwd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise


def launch(workspace, profile, stage, budget, *, phase=None, epochs=None):
    protocol = load_profiles()["protocol"]
    timeout = protocol["prepare_timeout_seconds"]
    if stage == "train":
        timeout = min(protocol["run_timeout_seconds"], protocol["total_train_seconds"] - budget["spent"])
        if timeout <= 0:
            raise MatrixError("TRAINING_BUDGET", "INCONCLUSIVE")
    command = [sys.executable, "-I", str(MATRIX / "matrix_worker.py"), "--workspace", str(workspace),
               "--stage", stage, "--model", profile["key"], "--parent-pid", str(os.getpid())]
    if phase is not None:
        command += ["--phase", phase, "--epochs", str(epochs)]
    env = worker_env(workspace, online=stage == "prepare")
    env.update(PYTORCH_ENABLE_MPS_FALLBACK="0", HF_HUB_DISABLE_XET="1")
    start = time.monotonic()
    output = workspace / profile["key"] / ((phase or stage) + ".json")
    try:
        code = run_process(command, env, timeout)
    except subprocess.TimeoutExpired:
        if not output.exists():
            output.parent.mkdir(exist_ok=True)
            write_json(output, {"status": "INCONCLUSIVE", "error_type": "TIMEOUT"})
        raise MatrixError("TIMEOUT", "INCONCLUSIVE") from None
    finally:
        if stage == "train":
            budget["spent"] += time.monotonic() - start
    if code or not output.is_file() or output.is_symlink():
        raise MatrixError("WORKER_FAILURE")
    result = read_json(output)
    if result.get("status") != "PASS":
        raise MatrixError("WORKER_FAILURE")
    print(f"{profile['key']} {phase or stage}: PASS", flush=True)
    return result


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def validate_run(run, profile, prepared, selection, source, phase, condition=None):
    epochs = 3 if phase.startswith("pr-") else 1
    if (run.get("status") != "PASS" or run.get("phase") != phase or run.get("epochs") != epochs
            or run.get("model_id") != profile["model_id"] or run.get("model_revision") != profile["revision"]
            or run.get("model_type") != profile["model_type"] or run.get("source_sha256") != source
            or run.get("profile_sha256") != digest(profile) or run.get("environment") != prepared["environment"]
            or run.get("encoder_updated") is not True or run.get("updates") != 8 * epochs
            or run.get("finite_gradients_checked") != 8 * epochs):
        raise MatrixError("RUN_CONTRACT")
    actual = run["observed_training_arguments"]
    expected = {**training_settings(epochs), "report_to": [], "world_size": 1, "device": "mps"}
    if actual != expected or run.get("config") != hf_config(profile, epochs, 6.0, .2):
        raise MatrixError("TRAINING_ARGUMENTS")
    hashes = {split: selection[split]["content_sha256"] for split in ("train", "test")}
    if run.get("subset_content_sha256") != hashes:
        raise MatrixError("DATASET_MISMATCH")
    computed = digest({"profile": profile, "model_files_sha256": selection["model_files_sha256"],
                       "subset_content_sha256": hashes, "environment": prepared["environment"],
                       "training_settings": {k: v for k, v in actual.items() if k != "num_train_epochs"},
                       "attention_implementation": run["attention_implementation"]})
    if run.get("condition_sha256") != computed or (condition is not None and condition != computed):
        raise MatrixError("CONDITIONS_CHANGED")
    for key in ("training_seconds", "loading_seconds", "tokenization_seconds", "evaluation_seconds",
                "parameter_count", "sampled_peak_process_rss_bytes", "sampled_peak_mps_allocated_bytes"):
        if not positive(run.get(key)):
            raise MatrixError("INVALID_MEASUREMENT")
    if (not positive(run.get("training_loss")) or len(run["losses"]) != 8 * epochs
            or any(not positive(loss) for loss in run["losses"])):
        raise MatrixError("INVALID_LOSS")
    if any(type(run.get(key)) not in (int, float) or not math.isfinite(run[key])
           or not 0 <= run[key] <= 1 for key in ("accuracy", "f1")):
        raise MatrixError("INVALID_METRIC")
    return computed


def seal_calibration(directory, profile, runs, condition):
    median_seconds = sorted(run["training_seconds"] for run in runs)[1]
    minutes = float(Decimal(str(median_seconds)) / Decimal(60))
    budget = float(decimal_cost(1, minutes) * 2)
    calibration = {"seconds": [r["training_seconds"] for r in runs], "median_seconds": median_seconds,
                   "minutes_per_epoch": minutes, "budget_usd": budget, "condition_sha256": condition,
                   "price_usd_per_unit_hour": 1.0}
    write_json(directory / "calibration.json", calibration)
    for name, epochs in (("base", 1), ("pr", 3)):
        write_json(directory / f"measured-{name}.json", hf_config(profile, epochs, minutes, budget))
    return {name: file_digest(directory / name) for name in
            ("calibration.json", "measured-base.json", "measured-pr.json")}


def check_seals(directory, seals):
    if any((directory / name).is_symlink() or file_digest(directory / name) != expected
           for name, expected in seals.items()):
        raise MatrixError("EVIDENCE_CHANGED")


def check_report_document(document, report, minutes):
    if (document["analysis_status"] != "complete" or document["schema_version"] != "1.0"
            or len(document["analyses"]) != 1 or document["summary"]["excluded_count"] != 0
            or document["summary"]["analyzed_count"] != 1):
        raise MatrixError("REPORT_STATUS")
    item = document["analyses"][0]
    costs = []
    for side, epochs in (("base", 1), ("pr", 3)):
        expected = float(decimal_cost(epochs, minutes))
        cost = item[side]["estimate"]["estimated_cost_usd"]
        if (not positive(cost) or not math.isclose(cost, expected, rel_tol=1e-12)
                or item[side]["adapter"] != "huggingface" or item[side]["config"]["epochs"] != epochs
                or not math.isclose(document["summary"][f"{side}_cost_usd"], expected, rel_tol=1e-12)):
            raise MatrixError("DECIMAL_COST")
        costs.append(cost)
    if (not math.isclose(item["increase_percent"], 200, abs_tol=1e-10)
            or not {"budget_exceeded", "cost_increase", "epochs_increased", "precision_risk"}
                <= {warning["code"] for warning in item["warnings"]}):
        raise MatrixError("REPORT_WARNINGS")
    _verify_cost_display(report, costs)
    return {"status": "PASS", "analysis_status": "complete", "comment_posted": "false",
            "base_usd": costs[0], "pr_usd": costs[1], "increase_percent": item["increase_percent"]}


def action_report(workspace, profile, seals):
    directory = workspace / profile["key"]
    check_seals(directory, seals)
    env = worker_env(workspace)
    output, summary = directory / "action-output.txt", directory / "step-summary.md"
    env.update(GITHUB_OUTPUT=str(output), GITHUB_STEP_SUMMARY=str(summary))
    command = [sys.executable, "-I", str(ROOT / "packages/github-action/traincost_action.py"),
               "--base-config", "measured-base.json", "--head-config", "measured-pr.json",
               "--config-adapter", "huggingface", "--gpu-prices", "APPLE_M1_MPS=1",
               "--report-path", "report.md", "--report-json-path", "report.json", "--comment-mode", "false"]
    if run_process(command, env, 120, cwd=directory):
        raise MatrixError("ACTION_FAILURE")
    values = dict(line.split("=", 1) for line in output.read_text().splitlines())
    if values != {"report-path": str(directory / "report.md"), "report-json-path": str(directory / "report.json"),
                  "analysis-status": "complete", "comment-posted": "false"}:
        raise MatrixError("ACTION_OUTPUTS")
    report = (directory / "report.md").read_text()
    if summary.read_text() != report:
        raise MatrixError("STEP_SUMMARY")
    result = check_report_document(read_json(directory / "report.json"), report,
                                  read_json(directory / "calibration.json")["minutes_per_epoch"])
    check_seals(directory, seals)
    write_json(directory / "report-check.json", result)
    return result


def run_model(workspace, profile, source, budget):
    prepared = launch(workspace, profile, "prepare", budget)
    directory = workspace / profile["key"]
    selection = read_json(directory / "selection.json")
    if any(value.get("source_sha256") != source or value.get("profile_sha256") != digest(profile)
           for value in (prepared, selection)):
        raise MatrixError("PREPARE_CONTRACT")
    seals = {name: file_digest(directory / name) for name in ("prepare.json", "selection.json")}
    runs = {"calibration": [], "base": [], "pr": []}
    condition = None
    phases = [("calibration", i) for i in range(1, 4)]
    phases += [(kind, i) for i in range(1, 4) for kind in (("base", "pr") if i % 2 else ("pr", "base"))]
    for kind, index in phases:
        check_seals(directory, seals)
        phase = f"{kind}-{index}"
        run = launch(workspace, profile, "train", budget, phase=phase, epochs=3 if kind == "pr" else 1)
        condition = validate_run(run, profile, prepared, selection, source, phase, condition)
        runs[kind].append(run)
        seals[phase + ".json"] = file_digest(directory / (phase + ".json"))
        if kind == "calibration" and index == 3:
            seals.update(seal_calibration(directory, profile, runs["calibration"], condition))
    report = action_report(workspace, profile, seals)
    timing = evaluate_measurements(*([run["training_seconds"] for run in runs[kind]]
                                    for kind in ("calibration", "base", "pr")))
    write_json(directory / "timing.json", timing)
    check_seals(directory, seals)
    return {"compatibility_status": "PASS", "report_status": report["status"],
            "timing_status": timing["status"], "model_id": profile["model_id"], "revision": profile["revision"],
            "condition_sha256": condition, "training_runs": 9,
            "timing": timing, "price_note": "Hypothetical $1/unit-hour; not billed or electricity cost."}


def aggregate_status(results):
    def group(values):
        if "FAIL" in values:
            return "FAIL"
        return "PASS" if values and all(value == "PASS" for value in values) else "INCONCLUSIVE"
    compatibility = group([r["compatibility_status"] for r in results.values()])
    reports = group([r["report_status"] for r in results.values()])
    timing = group([r["timing_status"] for r in results.values()])
    return {"status": group([compatibility, reports, timing]), "compatibility_status": compatibility,
            "report_status": reports, "timing_status": timing}


def validate_export(name, value):
    """Reject unrecognized fields before sharing local measurement metadata."""
    filename = Path(name).name
    if filename == "source.json":
        validate_snapshot(value)
        return
    run_keys = {"status", "phase", "epochs", "environment", "model_id", "model_revision", "source_sha256",
                "profile_sha256", "condition_sha256", "config", "observed_training_arguments",
                "attention_implementation", "model_type", "parameter_count", "encoder_parameter_name",
                "encoder_updated", "finite_gradients_checked", "updates", "training_loss", "losses", "accuracy",
                "f1", "loading_seconds", "tokenization_seconds", "training_seconds", "parameter_check_seconds",
                "evaluation_seconds", "sampled_peak_process_rss_bytes", "sampled_peak_mps_allocated_bytes",
                "subset_content_sha256"}
    schemas = {
        "run-contract.json": {"schema", "source_sha256", "profiles", "selected_models"},
        "outcome.json": {"status", "compatibility_status", "report_status", "timing_status", "source_sha256", "training_process_seconds", "models"},
        "prepare.json": {"status", "environment", "source_sha256", "profile_sha256"},
        "selection.json": {"model_files_sha256", "source_sha256", "profile_sha256", "train", "test", "prepare_seconds"},
        "calibration.json": {"seconds", "median_seconds", "minutes_per_epoch", "budget_usd", "condition_sha256", "price_usd_per_unit_hour"},
        "timing.json": {"status", "calibration_median_seconds", "predicted_seconds", "observed_median_seconds", "relative_errors", "repeatable"},
        "report-check.json": {"status", "analysis_status", "comment_posted", "base_usd", "pr_usd", "increase_percent"},
        "result.json": {"compatibility_status", "report_status", "timing_status", "model_id", "revision", "condition_sha256", "training_runs", "timing", "price_note"},
    }
    if not isinstance(value, dict):
        raise MatrixError("BUNDLE_SCHEMA")
    expected = schemas.get(filename)
    if re.fullmatch(r"(?:calibration|base|pr)-[123]\.json", filename):
        expected = run_keys
    if value.get("status") in {"FAIL", "INCONCLUSIVE"} and "error_type" in value:
        expected = {"status", "error_type"} | ({"stage"} if "stage" in value else set())
        if value["error_type"] not in {"TIMEOUT", "WorkerError", "ValueError", "RuntimeError", "OSError",
                                       "ImportError", "MemoryError", "KeyboardInterrupt", "WORKER_FAILURE",
                                       "FileNotFoundError", "PermissionError", "TypeError", "KeyError", "OtherError"}:
            raise MatrixError("BUNDLE_SCHEMA")
    if filename == "result.json" and "reason" in value:
        expected = {"compatibility_status", "report_status", "timing_status", "reason"}
        if value["reason"] not in {"TIMEOUT", "TRAINING_BUDGET", "WORKER_FAILURE", "VALIDATION_FAILURE",
                "RUN_CONTRACT", "TRAINING_ARGUMENTS", "DATASET_MISMATCH", "CONDITIONS_CHANGED",
                "INVALID_MEASUREMENT", "INVALID_LOSS", "INVALID_METRIC", "PREPARE_CONTRACT",
                "EVIDENCE_CHANGED", "ACTION_FAILURE", "ACTION_OUTPUTS", "STEP_SUMMARY",
                "REPORT_STATUS", "DECIMAL_COST", "REPORT_WARNINGS"}:
            raise MatrixError("BUNDLE_SCHEMA")
    if filename.startswith("measured-"):
        expected = set(hf_config(load_profiles()["models"][0], 1, 6, .2))
        if set(value.get("training_args", {})) != set(training_settings(1)):
            raise MatrixError("BUNDLE_SCHEMA")
        profile = next((p for p in load_profiles()["models"] if p["key"] == Path(name).parent.name), None)
        epochs = {"measured-base.json": 1, "measured-pr.json": 3}.get(filename)
        if (profile is None or epochs is None or not positive(value.get("estimated_minutes_per_epoch"))
                or not positive(value.get("budget_limit_usd")) or value != hf_config(profile, epochs,
                        value["estimated_minutes_per_epoch"], value["budget_limit_usd"])):
            raise MatrixError("BUNDLE_SCHEMA")
    if filename == "report.json":
        expected = {"schema_version", "analysis_status", "analyses", "diagnostics", "summary"}
    if expected is None or set(value) != expected:
        raise MatrixError("BUNDLE_SCHEMA")
    for key in ("status", "compatibility_status", "report_status", "timing_status"):
        if key in value and value[key] not in {"PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN"}:
            raise MatrixError("BUNDLE_SCHEMA")
    if "model_id" in value:
        profile = next((p for p in load_profiles()["models"] if p["model_id"] == value["model_id"]), None)
        if profile is None or value.get("model_revision", value.get("revision")) != profile["revision"]:
            raise MatrixError("BUNDLE_SCHEMA")
    if "price_note" in value and value["price_note"] != "Hypothetical $1/unit-hour; not billed or electricity cost.":
        raise MatrixError("BUNDLE_SCHEMA")
    if "environment" in value:
        env = value["environment"]
        if (set(env) != {"os", "machine", "python", "device", "packages", "lock_sha256"}
                or set(env["packages"]) != {"torch", "transformers", "accelerate", "datasets", "safetensors", "numpy", "huggingface-hub"}):
            raise MatrixError("BUNDLE_SCHEMA")
        if (env["machine"] != "arm64" or env["device"] != "mps"
                or not re.fullmatch(r"3\.12\.\d+", env["python"])
                or not isinstance(env["os"], list) or len(env["os"]) != 3
                or not re.fullmatch(r"\d+(?:\.\d+)*", env["os"][0])
                or env["os"][1:] != [["", "", ""], "arm64"]
                or any(not isinstance(version, str) or not re.fullmatch(r"\d+(?:\.\d+)*(?:[a-z]+\d+)?", version)
                       for version in env["packages"].values())
                or not re.fullmatch(r"[a-f0-9]{64}", env["lock_sha256"])):
            raise MatrixError("BUNDLE_SCHEMA")
    if "observed_training_arguments" in value:
        expected_args = {**training_settings(value["epochs"]), "report_to": [], "world_size": 1, "device": "mps"}
        if value["observed_training_arguments"] != expected_args:
            raise MatrixError("BUNDLE_SCHEMA")
        if value["config"] != hf_config(next(p for p in load_profiles()["models"] if p["model_id"] == value["model_id"]), value["epochs"], 6.0, .2):
            raise MatrixError("BUNDLE_SCHEMA")
    if filename == "selection.json":
        for split in ("train", "test"):
            if (set(value[split]) != {"size", "indices", "indices_sha256", "content_sha256", "label_counts"}
                    or type(value[split]["size"]) is not int or value[split]["size"] != 64
                    or value[split]["label_counts"] != [32, 32]
                    or not isinstance(value[split]["indices"], list) or len(value[split]["indices"]) != 64
                    or any(type(index) is not int or index < 0 for index in value[split]["indices"])
                    or len(set(value[split]["indices"])) != 64
                    or digest(value[split]["indices"]) != value[split]["indices_sha256"]
                    or not isinstance(value[split]["content_sha256"], str)
                    or not re.fullmatch(r"[a-f0-9]{64}", value[split]["content_sha256"])):
                raise MatrixError("BUNDLE_SCHEMA")
        allowed = set().union(*(set(p["files"]) for p in load_profiles()["models"]))
        if (not set(value["model_files_sha256"]) <= allowed
                or any(not isinstance(h, str) or not re.fullmatch(r"[a-f0-9]{64}", h)
                       for h in value["model_files_sha256"].values())):
            raise MatrixError("BUNDLE_SCHEMA")
    if filename == "run-contract.json":
        validate_profiles(value["profiles"])
    if filename == "outcome.json":
        for result in value["models"].values():
            validate_export("result.json", result)
    if filename == "result.json" and "timing" in value:
        validate_export("timing.json", value["timing"])
    # Metadata strings are identifiers, hashes or fixed labels, never arbitrary notes.
    for key, item in value.items():
        if key.endswith("_sha256") and isinstance(item, str) and not re.fullmatch(r"[a-f0-9]{64}", item):
            raise MatrixError("BUNDLE_SCHEMA")
        if (key.endswith("_seconds") or key in {"accuracy", "f1", "training_loss", "parameter_count",
                                               "updates", "finite_gradients_checked",
                                               "sampled_peak_process_rss_bytes", "sampled_peak_mps_allocated_bytes"}) and not isinstance(item, dict):
            if type(item) not in (int, float) or not math.isfinite(item) or item < 0:
                raise MatrixError("BUNDLE_SCHEMA")
    for key in ("seconds", "losses"):
        if key in value and (not isinstance(value[key], list) or any(not positive(item) for item in value[key])):
            raise MatrixError("BUNDLE_SCHEMA")
    if filename == "timing.json":
        for key in ("predicted_seconds", "observed_median_seconds", "relative_errors"):
            if (set(value[key]) != {"base", "pr"}
                    or any(type(item) not in (int, float) or not math.isfinite(item) or item < 0 for item in value[key].values())):
                raise MatrixError("BUNDLE_SCHEMA")
        if (set(value["repeatable"]) != {"calibration", "base", "pr"}
                or any(type(item) is not bool for item in value["repeatable"].values())):
            raise MatrixError("BUNDLE_SCHEMA")


def reproduce_report(directory):
    """Only export report text produced from the reviewed, measured inputs."""
    sys.path.insert(0, str(ROOT / "packages/core/src"))
    from traincost_ci_core import analyze_configs, normalize_training_config
    from traincost_ci_core.serialization import analysis_to_dict, make_document
    configs = [normalize_training_config(read_json(directory / f"measured-{side}.json"),
                source_path=f"measured-{side}.json", adapter="huggingface") for side in ("base", "pr")]
    result = analyze_configs(*configs, gpu_hourly_prices={"APPLE_M1_MPS": 1.0})
    document = make_document("complete", [{"path": "measured-pr.json", **analysis_to_dict(result)}])
    if (read_json(directory / "report.json") != document
            or (directory / "report.md").read_text() != result.markdown_report
            or (directory / "step-summary.md").read_text() != result.markdown_report):
        raise MatrixError("BUNDLE_REPORT")


def export_bundle(workspace, selected, outcome):
    # Only metadata/report names are exported; caches, raw data, and weights never are.
    names = ["run-contract.json", "outcome.json"]
    if (workspace / "source.json").exists():
        names.append("source.json")
    fixed = ["prepare.json", "selection.json", "calibration.json", "measured-base.json", "measured-pr.json",
             "report.md", "report.json", "step-summary.md", "report-check.json", "timing.json", "result.json"]
    fixed += [f"{phase}-{i}.json" for phase in ("calibration", "base", "pr") for i in range(1, 4)]
    for profile in selected:
        names.extend(profile["key"] + "/" + name for name in fixed
                     if (workspace / profile["key"] / name).is_file())
    dest = workspace / "bundle"
    sys.path.insert(0, str(ROOT / "packages/core/src"))
    from traincost_ci_core.safety import looks_sensitive
    for name in names:
        path = workspace / name
        if path.is_symlink() or path.stat().st_size > 1_000_000:
            raise MatrixError("UNSAFE_BUNDLE")
        content = path.read_text(encoding="utf-8")
        if looks_sensitive(content):
            raise MatrixError("SENSITIVE_BUNDLE")
        if name.endswith(".json"):
            validate_export(name, read_json(path))
    for profile in selected:
        directory = workspace / profile["key"]
        if (directory / "report.json").is_file():
            reproduce_report(directory)
    dest.mkdir(mode=0o700)
    for name in names:
        path = workspace / name
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    write_json(dest / "manifest.json", {"schema": 1, "status": outcome["status"],
                                        "files": {name: file_digest(dest / name) for name in names}})


def verify_bundle(directory):
    """Recheck published arithmetic and metadata without loading models or data."""
    directory = Path(directory)
    if (directory / "manifest.json").stat().st_size > 100_000:
        raise MatrixError("BUNDLE_SIZE")
    manifest = read_json(directory / "manifest.json")
    if manifest["schema"] != 1 or not isinstance(manifest["files"], dict):
        raise MatrixError("BUNDLE_SCHEMA")
    for name, expected in manifest["files"].items():
        if (not re.fullmatch(r"[a-z0-9_-]+(?:/[a-z0-9_-]+)?\.(?:json|md)", name)
                or any(p.is_symlink() for p in (directory / name, (directory / name).parent))
                or (directory / name).stat().st_size > 1_000_000
                or file_digest(directory / name) != expected):
            raise MatrixError("BUNDLE_HASH")
        if name.endswith(".json"):
            validate_export(name, read_json(directory / name))
    required = {"run-contract.json", "outcome.json"}
    if not required <= set(manifest["files"]):
        raise MatrixError("BUNDLE_INCOMPLETE")
    contract, outcome = (read_json(directory / name) for name in ("run-contract.json", "outcome.json"))
    if "source.json" in manifest["files"]:
        source = read_json(directory / "source.json")
        validate_snapshot(source)
        if source["source_sha256"] != contract["source_sha256"]:
            raise MatrixError("BUNDLE_SOURCE")
    profiles = validate_profiles(contract["profiles"])
    selected = contract["selected_models"]
    if (not selected or len(selected) != len(set(selected)) or set(selected) != set(outcome["models"])
            or set(selected) - {p["key"] for p in profiles["models"]}
            or contract["source_sha256"] != outcome["source_sha256"]
            or manifest["status"] != outcome["status"]):
        raise MatrixError("BUNDLE_CONTRACT")
    for profile in profiles["models"]:
        if profile["key"] not in selected:
            continue
        result = outcome["models"][profile["key"]]
        if result["compatibility_status"] != "PASS":
            continue
        root = directory / profile["key"]
        def artifact(name):
            if profile["key"] + "/" + name not in manifest["files"]:
                raise MatrixError("BUNDLE_INCOMPLETE")
            return read_json(root / name)
        prepared, selection = artifact("prepare.json"), artifact("selection.json")
        condition, groups = None, {}
        for group in ("calibration", "base", "pr"):
            runs = [artifact(f"{group}-{i}.json") for i in range(1, 4)]
            for i, run in enumerate(runs, 1):
                condition = validate_run(run, profile, prepared, selection, contract["source_sha256"],
                                         f"{group}-{i}", condition)
            groups[group] = [run["training_seconds"] for run in runs]
        timing = evaluate_measurements(*(groups[group] for group in ("calibration", "base", "pr")))
        calibration = artifact("calibration.json")
        minutes = float(Decimal(str(sorted(groups["calibration"])[1])) / Decimal(60))
        if (calibration["minutes_per_epoch"] != minutes or calibration["condition_sha256"] != condition
                or artifact("timing.json") != timing or result["timing"] != timing
                or result["timing_status"] != timing["status"]):
            raise MatrixError("BUNDLE_MEASUREMENTS")
        for name, epochs in (("base", 1), ("pr", 3)):
            if artifact(f"measured-{name}.json") != hf_config(profile, epochs, minutes, float(decimal_cost(1, minutes) * 2)):
                raise MatrixError("BUNDLE_CONFIG")
        for name in ("report.md", "step-summary.md"):
            if profile["key"] + "/" + name not in manifest["files"]:
                raise MatrixError("BUNDLE_INCOMPLETE")
        report = (root / "report.md").read_text()
        checked = check_report_document(artifact("report.json"), report, minutes)
        if artifact("report-check.json") != checked or (root / "step-summary.md").read_text() != report:
            raise MatrixError("BUNDLE_REPORT")
        reproduce_report(root)
    if any(outcome[key] != expected for key, expected in aggregate_status(outcome["models"]).items()):
        raise MatrixError("BUNDLE_OUTCOME")
    print(f"Bundle integrity and available measurements checked: {len(selected)} profiles; "
          f"recorded outcome={outcome['status']}.")
    return outcome


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--models", nargs="+")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--check-bundle", type=Path)
    args = parser.parse_args(argv)
    if args.check_bundle is not None:
        if args.workspace is not None or args.models is not None or args.list:
            parser.error("Bundle checking is separate from model execution")
        try:
            verify_bundle(args.check_bundle)
        except (ValueError, KeyError, TypeError, OSError, MatrixError):
            print("Bundle validation failed.", file=sys.stderr)
            return 2
        return 0
    profiles = load_profiles()
    keys = args.models or [profile["key"] for profile in profiles["models"]]
    if len(keys) != len(set(keys)) or set(keys) - {p["key"] for p in profiles["models"]}:
        parser.error("Select unique reviewed profile keys")
    selected = [p for p in profiles["models"] if p["key"] in keys]
    if args.list:
        for profile in selected:
            print(f"{profile['key']}: {profile['model_id']}@{profile['revision']}")
        return 0
    if args.workspace is None:
        parser.error("--workspace is required for an opt-in run")
    workspace = None
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            raise MatrixError("TRAINING_NOT_ALLOWED_IN_CI")
        workspace = claim_workspace(args.workspace)
        snapshot = capture_snapshot()
        source = snapshot["source_sha256"]
        write_json(workspace / "source.json", snapshot)
        write_json(workspace / "run-contract.json", {"schema": 1, "source_sha256": source,
                    "profiles": profiles, "selected_models": [p["key"] for p in selected]})
        budget, results = {"spent": 0.0}, {}
        for profile in selected:
            try:
                result = run_model(workspace, profile, source, budget)
            except MatrixError as exc:
                result = {"compatibility_status": exc.status, "report_status": "NOT_RUN",
                          "timing_status": "NOT_RUN", "reason": exc.reason}
            except Exception:
                result = {"compatibility_status": "FAIL", "report_status": "NOT_RUN",
                          "timing_status": "NOT_RUN", "reason": "VALIDATION_FAILURE"}
            results[profile["key"]] = result
            directory = workspace / profile["key"]
            directory.mkdir(exist_ok=True)
            write_json(directory / "result.json", result)
            print(f"{profile['key']}: compatibility={result['compatibility_status']}, "
                  f"report={result['report_status']}, timing={result['timing_status']}", flush=True)
        if source_fingerprint() != source:
            raise MatrixError("SOURCE_CHANGED")
        outcome = {**aggregate_status(results),
                   "source_sha256": source, "training_process_seconds": budget["spent"], "models": results}
        write_json(workspace / "outcome.json", outcome)
        export_bundle(workspace, selected, outcome)
        print(f"Matrix: compatibility={outcome['compatibility_status']}, timing={outcome['timing_status']}; bundle created.")
        return 0 if outcome["status"] == "PASS" else 1
    except (Exception, KeyboardInterrupt):
        if workspace is not None and not (workspace / "outcome.json").exists():
            write_json(workspace / "outcome.json", {"status": "INCONCLUSIVE", "reason": "INTERRUPTED_OR_SETUP_FAILURE"})
        print("Matrix did not complete. Evidence is preserved; no automatic retry.", file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
