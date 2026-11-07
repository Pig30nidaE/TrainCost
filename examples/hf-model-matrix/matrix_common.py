"""Bounded profiles and shared contracts for local real-model verification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEMO = ROOT / "examples/huggingface-demo"


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate evidence key")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_profiles(data, *, require_metadata=False):
    if (not isinstance(data, dict) or set(data) != {"schema", "dataset", "protocol", "models"}
            or type(data["schema"]) is not int or data["schema"] != 1):
        raise ValueError("Invalid matrix schema")
    dataset = data["dataset"]
    if dataset != {"id": "stanfordnlp/imdb", "revision": "e6281661ce1c48d982bc483cf8a173c1bbeb5d31",
                   "license": "other", "train_file": "plain_text/train-00000-of-00001.parquet",
                   "test_file": "plain_text/test-00000-of-00001.parquet"}:
        raise ValueError("Unreviewed dataset contract")
    expected = {"train_size": 64, "test_size": 64, "max_length": 128, "seed": 42,
                "calibration_runs": 3, "evaluation_runs": 3, "run_timeout_seconds": 600,
                "total_train_seconds": 3600, "prepare_timeout_seconds": 1200,
                "price_usd_per_unit_hour": 1.0}
    if data["protocol"] != expected or any(type(data["protocol"][key]) is not type(value) for key, value in expected.items()):
        raise ValueError("Unreviewed measurement protocol")
    if not isinstance(data["models"], list) or not 1 <= len(data["models"]) <= 8:
        raise ValueError("Expected one to eight model profiles")
    seen = set()
    allowed = {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
               "vocab.txt", "vocab.json", "merges.txt", "spiece.model", "special_tokens_map.json"}
    required = {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json"}
    for profile in data["models"]:
        fields = {"key", "model_id", "revision", "model_type", "license", "files"}
        if (not isinstance(profile, dict) or set(profile) not in (fields, fields | {"metadata_sha256"})
                or (require_metadata and "metadata_sha256" not in profile)):
            raise ValueError("Invalid model profile")
        if "metadata_sha256" in profile:
            hashes = profile["metadata_sha256"]
            if (not isinstance(hashes, dict) or set(hashes) != {"config.json", "tokenizer_config.json"}
                    or any(not isinstance(h, str) or not re.fullmatch(r"[a-f0-9]{64}", h) for h in hashes.values())):
                raise ValueError("Invalid reviewed metadata hashes")
        for key in ("key", "model_type"):
            if not isinstance(profile[key], str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", profile[key]):
                raise ValueError("Invalid model key/type")
        if not isinstance(profile["model_id"], str) or not re.fullmatch(r"[\w-]+/[\w.-]+", profile["model_id"], re.ASCII):
            raise ValueError("Invalid Hub model ID")
        if not isinstance(profile["revision"], str) or not re.fullmatch(r"[a-f0-9]{40}", profile["revision"]):
            raise ValueError("Model revision must be an immutable commit")
        if profile["key"] in seen or profile["license"] not in {"apache-2.0", "mit", "bsd-3-clause"}:
            raise ValueError("Duplicate profile or unreviewed license")
        seen.add(profile["key"])
        files = profile["files"]
        if (not isinstance(files, list) or any(not isinstance(name, str) for name in files)
                or len(files) != len(set(files)) or not required <= set(files) <= allowed):
            raise ValueError("Unsafe or incomplete model file allowlist")
    return data


def load_profiles():
    return validate_profiles(read_json(HERE / "profiles.json"), require_metadata=True)


def profile_for(key):
    for profile in load_profiles()["models"]:
        if profile["key"] == key:
            return profile
    raise ValueError("Unknown model profile")


def training_settings(epochs):
    if type(epochs) is not int or epochs not in (1, 3):
        raise ValueError("Expected one or three epochs")
    return {"num_train_epochs": epochs, "max_steps": -1, "per_device_train_batch_size": 8,
            "per_device_eval_batch_size": 8, "gradient_accumulation_steps": 1,
            "learning_rate": 2e-5, "lr_scheduler_type": "constant", "warmup_steps": 0,
            "optim": "adamw_torch", "fp16": False, "bf16": False, "tf32": False,
            "seed": 42, "data_seed": 42, "save_strategy": "no", "eval_strategy": "no",
            "logging_strategy": "steps", "logging_steps": 1, "logging_nan_inf_filter": False,
            "report_to": "none", "push_to_hub": False, "disable_tqdm": True,
            "dataloader_num_workers": 0, "dataloader_pin_memory": False, "use_cpu": False}


def hf_config(profile, epochs, minutes, budget):
    return {"model_name": profile["model_id"], "dataset_size": 64,
            "gpu_type": "APPLE_M1_MPS", "gpu_count": 1, "precision": "fp32",
            "estimated_minutes_per_epoch": minutes, "budget_limit_usd": budget,
            "training_args": training_settings(epochs)}


SOURCE_FIXED = frozenset({
    "examples/hf-model-matrix/profiles.json", "scripts/verify_hf_matrix.py",
    "scripts/verify_hf_macos.py", "packages/github-action/traincost_action.py",
    *("examples/huggingface-demo/" + name for name in
      ("common.py", "worker.py", "run_validation.py", "oracle.py", "macos-requirements.lock")),
})
SOURCE_DIRS = frozenset({"examples/hf-model-matrix", "packages/core/src/traincost_ci_core"})
# Keep old policies unchanged so later file moves do not invalidate recorded studies.
SOURCE_POLICY_VERSION = 2
SOURCE_POLICIES = {1: (SOURCE_FIXED, SOURCE_DIRS),
                   2: (SOURCE_FIXED | {"examples/huggingface-demo/model_safety.py"}, SOURCE_DIRS)}


def execution_paths(names, version=SOURCE_POLICY_VERSION):
    if type(version) is not int or version not in SOURCE_POLICIES:
        raise ValueError("Unknown execution inventory version")
    fixed, directories = SOURCE_POLICIES[version]
    names = set(names)
    if not fixed <= names:
        raise ValueError("Execution source is incomplete")
    return sorted(fixed | {name for name in names if name.endswith(".py")
                          and any(name.startswith(directory + "/") for directory in directories)
                          and not {"tests", "__pycache__"}.intersection(Path(name).parts)})


def source_manifest():
    fixed, directories = SOURCE_POLICIES[SOURCE_POLICY_VERSION]
    paths = [ROOT / name for name in fixed]
    for directory in directories:
        entries = list((ROOT / directory).rglob("*"))
        if any(path.is_symlink() for path in entries):
            raise ValueError("Execution source cannot contain symlinks")
        paths.extend(path for path in entries if path.is_file() and path.suffix == ".py")
    if any(path.is_symlink() or any(p.is_symlink() for p in path.parents) for path in paths):
        raise ValueError("Execution source cannot contain symlinks")
    return {name: file_digest(ROOT / name)
            for name in execution_paths(path.relative_to(ROOT).as_posix() for path in paths)}


def source_fingerprint():
    return digest(source_manifest())
