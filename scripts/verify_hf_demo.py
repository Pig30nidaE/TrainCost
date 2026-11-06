#!/usr/bin/env python3
"""Offline static validation of the Hugging Face demo, without training."""

from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "huggingface-demo"
sys.path.insert(0, str(ROOT / "packages" / "core" / "src"))
from traincost_ci_core import analyze_config_dicts  # noqa: E402

spec = importlib.util.spec_from_file_location("hf_demo_oracle", DEMO / "oracle.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    base = read_json(DEMO / "fixtures" / "base.json")
    head = read_json(DEMO / "fixtures" / "risky.json")
    live = read_json(DEMO / "config.json")
    manifest = read_json(DEMO / "manifest.json")
    expected = {
        "model_name": "distilbert/distilbert-base-uncased", "epochs": 1,
        "batch_size": 8, "precision": "fp32", "mixed_precision": False,
        "gpu_type": "RTX3060", "gpu_count": 1, "dataset_size": 1024,
        "estimated_minutes_per_epoch": 6, "budget_limit_usd": 0.2,
    }
    require(base == expected, "base config does not match the fixed demo contract")
    require(head == {**base, "epochs": 3}, "PR fixture must only increase epochs to 3")
    require(live in (base, head), "live config must match the base or PR fixture")
    require(manifest["model"] == base["model_name"] and manifest["dataset"] == "stanfordnlp/imdb", "model/dataset manifest mismatch")
    for key in ("model_revision", "dataset_revision"):
        require(bool(re.fullmatch(r"[0-9a-f]{40}", manifest[key])), f"{key} must be a pinned commit SHA")
    for key, value in {"seed": 42, "train_size": 1024, "test_size": 256,
                       "batch_size": 8, "max_length": 128, "learning_rate": 0.00002}.items():
        require(manifest[key] == value, f"manifest {key} differs from demo contract")
    require(Decimal(manifest["price_usd_per_gpu_hour"]) == Decimal("1.00"), "incorrect example price")

    result = analyze_config_dicts(base, head, gpu_hourly_prices={"RTX3060": 1.0})
    expected_base = oracle.decimal_cost(1, 6)
    expected_head = oracle.decimal_cost(3, 6)
    require(expected_base == Decimal("0.10") and expected_head == Decimal("0.30"), "independent oracle arithmetic failed")
    require(abs(result.base_estimate.estimated_cost_usd - float(expected_base)) < 1e-12, "base cost does not match independent oracle")
    require(abs(result.pr_estimate.estimated_cost_usd - float(expected_head)) < 1e-12, "PR cost does not match independent oracle")
    require(abs(result.increase_percent - 200) < 1e-10, "incorrect percentage increase")
    warnings = {warning.code for warning in result.warnings}
    require({"budget_exceeded", "cost_increase", "epochs_increased", "precision_risk"} <= warnings, "expected warning is missing")
    require([(change.field, change.before, change.after) for change in result.changes] == [("epochs", 1.0, 3.0)], "incorrect supported changes")
    for fragment in ("Estimated cost", "Base branch: $0.10", "This PR: $0.30", "Increase: +200%",
                     "Budget limit exceeded", "Mixed precision appears disabled", "Confidence",
                     "not billing accuracy or measured runtime", "source: epochs"):
        require(fragment in result.markdown_report, f"report is missing {fragment!r}")
    require("exact cost" not in result.markdown_report.lower(), "report overclaims exact costs")
    print("PASS: canonical config, independent cost oracle, warnings, provenance and report")

    native = {**base, "max_steps": 10000, "num_train_epochs": 20,
              "per_device_train_batch_size": 1, "gradient_accumulation_steps": 32,
              "bf16": True, "fp16": False, "world_size": 8}
    ignored = analyze_config_dicts(base, native, gpu_hourly_prices={"RTX3060": 1.0})
    unchanged = analyze_config_dicts(base, base, gpu_hourly_prices={"RTX3060": 1.0})
    require(not ignored.changes and {w.code for w in ignored.warnings} == {w.code for w in unchanged.warnings},
            "native-field limitation behavior changed; re-review demo claims")
    for change in ({"dataset_size": 10240}, {"batch_size": 16}, {"precision": "bf16", "mixed_precision": True}):
        stale = analyze_config_dicts(base, {**base, **change}, gpu_hourly_prices={"RTX3060": 1.0})
        require(stale.pr_estimate.estimated_cost_usd == stale.base_estimate.estimated_cost_usd,
                "stale runtime limitation behavior changed; re-review demo claims")
    metadata = {"model_type": "distilbert", "architectures": ["DistilBertModel"], "torch_dtype": "float32"}
    metadata_result = analyze_config_dicts(metadata, metadata)
    require(metadata_result.confidence.level == "Low" and metadata_result.pr_config.model_name is None,
            "model metadata limitation behavior changed; re-review demo claims")
    print("KNOWN_LIMITATION: native HF fields and model metadata are not translated; data, batch, or precision changes can leave the runtime assumption stale")
    print("NOT RUN: model download, training, GPU measurement, or actual provider billing")


if __name__ == "__main__":
    main()
