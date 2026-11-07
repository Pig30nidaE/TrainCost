"""Small, dependency-free contract shared by the demo processes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = "distilbert/distilbert-base-uncased"
EXPECTED_KEYS = {"model_name", "epochs", "batch_size", "precision", "mixed_precision",
                 "gpu_type", "gpu_count", "dataset_size", "estimated_minutes_per_epoch",
                 "budget_limit_usd"}


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_config(config, epochs=None):
    if not isinstance(config, dict) or set(config) != EXPECTED_KEYS:
        raise ValueError("unsupported config fields")
    fixed = {"model_name": MODEL, "batch_size": 8, "precision": "fp32", "mixed_precision": False,
             "gpu_type": "RTX3060", "gpu_count": 1, "dataset_size": 1024}
    if any(type(config[k]) is not type(v) or config[k] != v for k, v in fixed.items()):
        raise ValueError("unsupported training settings")
    if type(config["epochs"]) is not int or config["epochs"] not in (1, 3):
        raise ValueError("unsupported epochs")
    if epochs is not None and config["epochs"] != epochs:
        raise ValueError("unexpected epochs")
    import math
    for key in ("estimated_minutes_per_epoch", "budget_limit_usd"):
        value = config[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("invalid numeric config")
    return config


def input_contract():
    base = validate_config(read_json(HERE / "fixtures/base.json"), 1)
    risky = validate_config(read_json(HERE / "fixtures/risky.json"), 3)
    live = validate_config(read_json(HERE / "config.json"))
    if live not in (base, risky) or {**base, "epochs": 3} != risky:
        raise ValueError("fixture/config mismatch")
    if base["estimated_minutes_per_epoch"] != 6 or base["budget_limit_usd"] != .2:
        raise ValueError("unexpected static fixture")
    manifest = read_json(HERE / "manifest.json")
    expected = {"schema": 1, "model": MODEL,
        "model_revision": "12040accade4e8a0f71eabdb258fecc2e7e948be",
        "dataset": "stanfordnlp/imdb", "dataset_revision": "e6281661ce1c48d982bc483cf8a173c1bbeb5d31",
        "seed": 42, "train_size": 1024, "test_size": 256, "smoke_size": 64,
        "batch_size": 8, "max_length": 128, "learning_rate": .00002,
        "price_usd_per_gpu_hour": "1.00", "per_run_timeout_seconds": 600,
        "total_training_budget_seconds": 3600}
    if manifest != expected:
        raise ValueError("unexpected manifest")
    return base, risky, manifest


def source_fingerprint():
    paths = [HERE / name for name in ("run_validation.py", "worker.py", "common.py", "oracle.py", "model_safety.py",
             "manifest.json", "requirements.in", "requirements.lock")]
    paths += sorted((ROOT / "packages/core/src/traincost_ci_core").glob("*.py"))
    paths.append(ROOT / "packages/github-action/traincost_action.py")
    config = dict(input_contract()[0])
    del config["epochs"]
    return digest({"files": {str(p.relative_to(ROOT)): file_digest(p) for p in paths}, "config": config})
