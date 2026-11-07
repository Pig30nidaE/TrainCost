"""Reject executable or external-path metadata before invoking Transformers."""
from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path

FORBIDDEN = frozenset({"auto_map", "custom_pipelines", "trust_remote_code", "custom_generate",
                       "attn_implementation", "chat_template", "processor_class",
                       "feature_extractor_type", "image_processor_type"})
DISTILBERT_METADATA = {
    "config.json": "69c94b0222d5d1f4b0ad027ca7416cdafb98378cbbb8305d0bf47c9365c60c83",
    "tokenizer_config.json": "a025160ef0431f1a392f6f050c1310f4c5d9fb6f275932dbccba73c4d214bf10",
}


def read_metadata(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate metadata key")
            value[key] = item
        return value

    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000:
            raise ValueError("Invalid model metadata file")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite metadata")))
    except (OSError, ValueError, RecursionError):
        raise ValueError("Invalid model metadata") from None
    if not isinstance(value, dict):
        raise ValueError("Model metadata must be an object")
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > 32 or count > 10_000:
            raise ValueError("Model metadata exceeds structural limits")
        if isinstance(item, dict):
            for key, child in item.items():
                if (key in FORBIDDEN or key.startswith("_attn_implementation")
                        or key.endswith(("_file", "_files"))):
                    raise ValueError("Unsupported model metadata capability")
                pending.append((child, depth + 1))
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, float) and not math.isfinite(item):
            raise ValueError("Nonfinite model metadata")
    return value


def validate_local_model(directory, expected_model_type, *, hashes):
    directory = Path(directory)
    if any(path.is_symlink() for path in (directory, *directory.parents)):
        raise ValueError("Model metadata cannot use symlink paths")
    if set(hashes) != {"config.json", "tokenizer_config.json"}:
        raise ValueError("Reviewed metadata hashes are required")
    for name, expected in hashes.items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000:
            raise ValueError("Invalid model metadata file")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Model metadata differs from reviewed profile")
    config = read_metadata(directory / "config.json")
    read_metadata(directory / "tokenizer_config.json")
    if config.get("model_type") != expected_model_type:
        raise ValueError("Unexpected model architecture metadata")
