"""Bounded, non-executing config parsing and canonical-field extraction."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .models import SUPPORTED_FIELDS, TrainingConfig
from .safety import (
    ConfigError, MAX_CONFIG_BYTES, MAX_CONFIG_DEPTH, MAX_CONFIG_NODES,
    SENSITIVE_KEY_PARTS, looks_sensitive, number, safe_text,
)

_STRING_FIELDS = {"model", "model_name", "precision", "gpu_type"}
_INTEGER_FIELDS = {"batch_size", "global_batch_size", "gpu_count", "dataset_size"}

# Known knobs that affect runtime but are not incorporated into the formula.
RUNTIME_CONDITION_KEYS = frozenset({
    "num_train_epochs", "per_device_train_batch_size", "gradient_accumulation_steps",
    "bf16", "fp16", "world_size", "max_steps", "devices", "num_nodes",
    "accelerator", "strategy", "deepspeed", "fsdp", "sharded_ddp", "ddp_backend",
    "auto_find_batch_size", "gradient_checkpointing", "max_seq_length", "max_length",
    "block_size", "sequence_length", "seq_length", "dataset", "dataset_name",
    "dataloader_num_workers", "packing", "group_by_length", "optim", "optimizer",
    "torch_compile", "load_in_8bit", "load_in_4bit", "quantization_config",
    "model_name_or_path", "model_revision", "revision", "dataset_revision",
    "max_train_samples", "tokenizer_name", "tokenizer_revision", "max_seq_len",
    "use_cpu", "no_cuda", "use_tpu", "tpu_num_cores",
})


def load_config_file(path: str | Path, *, adapter: str = "canonical") -> TrainingConfig:
    config_path = Path(path)
    with config_path.open("rb") as stream:
        data = stream.read(MAX_CONFIG_BYTES + 1)
    if len(data) > MAX_CONFIG_BYTES:
        raise ConfigError("Config exceeds the 1MB byte limit.")
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        raise ConfigError("Config must be UTF-8.") from None
    return normalize_training_config(parse_config_text(text, config_path.suffix), source_path=str(path), adapter=adapter)


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError("Duplicate mapping key.")
        result[key] = value
    return result


def parse_config_text(text: str, file_format: str) -> dict[str, Any]:
    if len(text.encode("utf-8")) > MAX_CONFIG_BYTES:
        raise ConfigError("Config exceeds the 1MB byte limit.")
    fmt = file_format.lower().lstrip(".")
    try:
        if fmt in {"yaml", "yml"}:
            parsed = parse_yaml_text(text)
        elif fmt == "json":
            parsed = json.loads(text, object_pairs_hook=_unique_pairs)
        elif fmt == "py":
            parsed = parse_python_config_text(text)
        else:
            raise ConfigError("Unsupported config format.")
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}.") from None
    except (RecursionError, MemoryError):
        raise ConfigError("Config exceeds parser resource limits.") from None
    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise ConfigError("Config must contain a mapping at the top level.")
    _check_structure(parsed)
    return parsed


def parse_yaml_text(text: str) -> dict[str, Any]:
    if len(text.encode("utf-8")) > MAX_CONFIG_BYTES:
        raise ConfigError("Config exceeds the 1MB byte limit.")
    try:
        import yaml
    except ModuleNotFoundError:
        raise ConfigError("YAML requires PyYAML==6.0.3; install the core package dependencies.") from None

    class UniqueSafeLoader(yaml.SafeLoader):
        def construct_object(self, node, deep=False):
            try:
                return super().construct_object(node, deep=deep)
            except ConfigError:
                raise
            except (ValueError, TypeError, LookupError, AttributeError, OverflowError):
                # Scalar constructors can expose raw values in non-YAMLError exceptions.
                mark = node.start_mark
                raise ConfigError(
                    f"Invalid YAML value at line {mark.line + 1}, column {mark.column + 1}."
                ) from None

        def compose_node(self, parent, index):
            self.config_depth = getattr(self, "config_depth", 0) + 1
            self.config_nodes = getattr(self, "config_nodes", 0) + 1
            if self.config_depth > MAX_CONFIG_DEPTH or self.config_nodes > MAX_CONFIG_NODES:
                raise ConfigError("YAML exceeds structure limits.")
            try:
                return super().compose_node(parent, index)
            finally:
                self.config_depth -= 1

        def construct_mapping(self, node, deep=False):
            keys = set()
            for key_node, _ in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    raise ConfigError("YAML merge keys are unsupported; provide explicit values.")
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, (str, int, float, bool, type(None))):
                    raise ConfigError("YAML mapping keys must be scalars.")
                if key in keys:
                    raise ConfigError(f"Duplicate YAML key at line {key_node.start_mark.line + 1}.")
                keys.add(key)
            return super().construct_mapping(node, deep=deep)

    try:
        parsed = yaml.load(text, Loader=UniqueSafeLoader)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ConfigError(f"Invalid YAML{location}.") from None
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ConfigError("YAML config must contain a mapping at the top level.")
    _check_structure(parsed)
    return parsed


def parse_python_config_text(text: str) -> dict[str, Any]:
    if len(text.encode("utf-8")) > MAX_CONFIG_BYTES:
        raise ConfigError("Config exceeds the 1MB byte limit.")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise ConfigError(f"Invalid Python config at line {exc.lineno}.") from None
    result = {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue  # Imports are never executed.
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            raise ConfigError(f"Only literal assignments are supported at line {node.lineno}.")
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not all(isinstance(target, ast.Name) for target in targets):
            raise ConfigError(f"Only named assignments are supported at line {node.lineno}.")
        try:
            for child in ast.walk(node.value):
                if isinstance(child, ast.Dict):
                    _unique_pairs((ast.literal_eval(k), None) for k in child.keys)
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError, AttributeError):
            raise ConfigError(f"Invalid or duplicate Python literal at line {node.lineno}.") from None
        for target in targets:
            if target.id in result:
                raise ConfigError(f"Duplicate Python assignment at line {node.lineno}.")
            result[target.id] = value
    _check_structure(result)
    return result


def _check_structure(value: Any) -> None:
    active = set()
    count = 0

    def visit(item, depth):
        nonlocal count
        count += 1
        if depth > MAX_CONFIG_DEPTH or count > MAX_CONFIG_NODES:
            raise ConfigError("Config exceeds structure limits.")
        if isinstance(item, (Mapping, list, tuple)):
            if id(item) in active:
                raise ConfigError("Cyclic config references are unsupported.")
            active.add(id(item))
            children = item.values() if isinstance(item, Mapping) else item
            for child in children:
                visit(child, depth + 1)
            active.remove(id(item))
    visit(value, 0)


def normalize_training_config(raw_config: Mapping[str, Any], *, source_path: str | None = None, adapter: str = "canonical") -> TrainingConfig:
    if adapter not in {"canonical", "huggingface"}:
        raise ConfigError("Unsupported config adapter.")
    if adapter == "huggingface":
        from .huggingface import normalize_huggingface_config
        return normalize_huggingface_config(raw_config, source_path=source_path)
    return _normalize_canonical(raw_config, source_path=source_path)


def _normalize_canonical(raw_config: Mapping[str, Any], *, source_path: str | None = None) -> TrainingConfig:
    if not isinstance(raw_config, Mapping):
        raise ConfigError("Config must be a mapping.")
    _check_structure(raw_config)
    extracted = {}
    sources: dict[str, list[str]] = {}
    sensitive = set()
    conditions: dict[str, list[str]] = {}

    def walk(item, prefix="", in_list=False):
        if isinstance(item, Mapping):
            for key, value in item.items():
                name = str(key).strip().lower()
                path = f"{prefix}.{safe_text(key)}" if prefix else safe_text(key)
                if name in RUNTIME_CONDITION_KEYS and not looks_sensitive(key) and not looks_sensitive(value):
                    # The digest supports comparisons without retaining raw setting values.
                    encoded = json.dumps(_fingerprint_value(value), ensure_ascii=True, separators=(",", ":"))
                    conditions.setdefault(name, []).append(hashlib.sha256(encoded.encode()).hexdigest())
                if any(part in name for part in SENSITIVE_KEY_PARTS) or looks_sensitive(key) or looks_sensitive(value):
                    sensitive.add(path)
                    continue
                if name in SUPPORTED_FIELDS:
                    if in_list:
                        raise ConfigError("Training fields inside lists are ambiguous; use one config per experiment.")
                    normalized = _coerce_field(name, value)
                    if name in extracted and extracted[name] != normalized:
                        raise ConfigError(f"Conflicting field {name} at {safe_text(path)}.")
                    extracted[name] = normalized
                    sources.setdefault(name, []).append(path)
                walk(value, path, in_list)
        elif isinstance(item, (list, tuple)):
            for index, child in enumerate(item):
                if looks_sensitive(child):
                    sensitive.add(f"{prefix}[{index}]")
                else:
                    walk(child, f"{prefix}[{index}]", True)

    walk(raw_config)
    if extracted.get("epochs") is not None and extracted.get("max_epochs") is not None:
        if extracted["epochs"] != extracted["max_epochs"]:
            raise ConfigError("Conflicting epochs and max_epochs.")
    return TrainingConfig(
        **extracted, raw_fields=dict(extracted),
        source_path=safe_text(source_path) if source_path else None,
        sensitive_keys=tuple(sorted(sensitive)),
        field_sources={key: tuple(paths) for key, paths in sources.items()},
        runtime_conditions={key: hashlib.sha256("".join(sorted(values)).encode()).hexdigest()
                            for key, values in conditions.items()},
    )


def _fingerprint_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return sorted(((str(key), _fingerprint_value(item)) for key, item in value.items()), key=lambda pair: pair[0])
    if isinstance(value, (list, tuple)):
        return [_fingerprint_value(item) for item in value]
    return [type(value).__name__, str(value)]


def _coerce_field(name, value):
    if value is None:
        return None
    if name in _STRING_FIELDS:
        if isinstance(value, (Mapping, list, tuple, bool)) or not isinstance(value, (str, int, float)):
            raise ConfigError(f"Invalid {name}: expected a scalar label.")
        if not str(value).strip():
            raise ConfigError(f"Invalid {name}: label must not be empty.")
        return str(value).strip()
    if name == "mixed_precision":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"true", "yes", "y", "1", "on", "enabled"}:
            return True
        if text in {"false", "no", "n", "0", "off", "disabled"}:
            return False
        raise ConfigError("Invalid mixed_precision: expected a boolean.")
    return number(value, name, integer=name in _INTEGER_FIELDS, allow_zero=name == "budget_limit_usd")
