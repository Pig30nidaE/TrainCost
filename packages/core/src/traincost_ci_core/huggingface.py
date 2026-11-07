"""Explicit, non-executing adapter for a bounded TrainingArguments subset."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
from typing import Any, Mapping

from .models import TrainingConfig
from .parsing import _coerce_field, _normalize_canonical
from .safety import ConfigError, SENSITIVE_KEY_PARTS, looks_sensitive, number


def normalize_huggingface_config(raw: Mapping[str, Any], *, source_path: str | None = None) -> TrainingConfig:
    if not isinstance(raw, Mapping):
        raise ConfigError("Config must be a mapping.")
    containers = [key for key in raw if isinstance(key, str) and key.lower() == "training_args"]
    if len(containers) > 1:
        raise ConfigError("Ambiguous training_args containers.")
    config = _normalize_canonical(raw, source_path=source_path)
    args_raw = raw[containers[0]] if containers else raw
    if not isinstance(args_raw, Mapping):
        raise ConfigError("training_args must be a mapping.")
    prefix = f"{containers[0]}." if containers else ""
    execution_keys = {"num_train_epochs", "per_device_train_batch_size", "gradient_accumulation_steps",
                      "bf16", "fp16", "world_size", "max_steps", "deepspeed", "fsdp",
                      "sharded_ddp", "ddp_backend", "tpu_num_cores", "strategy", "accelerator",
                      "auto_find_batch_size", "use_cpu", "no_cuda", "use_tpu"}
    root_sources = set()
    def comparable(name, value):
        if name in {"num_train_epochs", "per_device_train_batch_size", "gradient_accumulation_steps", "world_size"}:
            return number(value, name, integer=name != "num_train_epochs")
        if name in {"bf16", "fp16", "auto_find_batch_size", "use_cpu", "no_cuda", "use_tpu"}:
            return _coerce_field("mixed_precision", value)
        if name == "max_steps":
            try:
                converted = float(value)
                if isinstance(value, bool) or not math.isfinite(converted) or not converted.is_integer():
                    raise ValueError
                return converted
            except (ValueError, TypeError, OverflowError):
                raise ConfigError("Invalid max_steps.") from None
        return value
    args = {}
    for key, value in args_raw.items():
        name = str(key).lower()
        if name in args and name in execution_keys:
            if comparable(name, args[name]) != comparable(name, value):
                raise ConfigError(f"Conflicting {name} settings.")
        else:
            args[name] = value
    if prefix:
        for key, value in raw.items():
            name = str(key).lower()
            if name in execution_keys:
                if name in args and comparable(name, args[name]) != comparable(name, value):
                    raise ConfigError(f"Conflicting {name} settings.")
                if name not in args:
                    args[name] = value
                    root_sources.add(name)

    def check_locations(item, path=()):
        if isinstance(item, Mapping):
            for key, value in item.items():
                name = str(key).lower()
                if any(part in name for part in SENSITIVE_KEY_PARTS) or looks_sensitive(key) or looks_sensitive(value):
                    continue
                if name in execution_keys and path not in ((), ("training_args",)):
                    raise ConfigError(f"Unsupported nested Hugging Face setting: {name}.")
                check_locations(value, (*path, name))
        elif isinstance(item, (list, tuple)):
            for value in item:
                check_locations(value, (*path, "[]"))
    check_locations(raw)
    training_keys = {"num_train_epochs", "per_device_train_batch_size", "gradient_accumulation_steps",
                     "bf16", "fp16", "max_steps", "epochs", "max_epochs", "batch_size",
                     "global_batch_size", "estimated_minutes_per_epoch"}
    if not (training_keys & set(args)):
        raise ConfigError("Hugging Face adapter requires explicit training arguments; model-only configs are unsupported.")

    for key in ("deepspeed", "fsdp", "sharded_ddp", "ddp_backend", "tpu_num_cores"):
        if key in args and args[key] not in (None, False, "", "none", [], {}):
            raise ConfigError(f"Unsupported distributed setting: {key}.")
    for key in ("strategy", "accelerator"):
        value = args.get(key)
        if isinstance(value, str) and any(engine in value.lower() for engine in ("deepspeed", "fsdp", "tpu", "xla")):
            raise ConfigError(f"Unsupported distributed setting: {key}.")
    if "auto_find_batch_size" in args and _coerce_field("mixed_precision", args["auto_find_batch_size"]):
        raise ConfigError("Automatic batch sizing is unsupported.")
    for key in ("use_cpu", "no_cuda", "use_tpu"):
        if key in args and _coerce_field("mixed_precision", args[key]):
            raise ConfigError(f"CPU-only and TPU execution is unsupported: {key}.")
    if "max_steps" in args and args["max_steps"] is not None:
        value = args["max_steps"]
        if isinstance(value, bool):
            raise ConfigError("Invalid max_steps.")
        try:
            steps = float(value)
            if not math.isfinite(steps) or not steps.is_integer():
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            raise ConfigError("Invalid max_steps.") from None
        if steps > 0:
            raise ConfigError("Positive max_steps overrides epochs; step-based runtime is unsupported.")

    values = config.field_values()
    sources = dict(config.field_sources)

    def set_alias(target: str, value: object, alias: str) -> None:
        normalized = _coerce_field(target, value)
        existing = values.get(target)
        if existing is not None and existing != normalized:
            raise ConfigError(f"Conflicting {target} and {alias}.")
        values[target] = normalized
        sources[target] = (*sources.get(target, ()), ("" if alias in root_sources else prefix) + alias)

    if args.get("num_train_epochs") is not None:
        set_alias("epochs", args["num_train_epochs"], "num_train_epochs")
        if values["max_epochs"] is not None and values["epochs"] != values["max_epochs"]:
            raise ConfigError("Conflicting max_epochs and num_train_epochs.")
    if args.get("per_device_train_batch_size") is not None:
        set_alias("batch_size", args["per_device_train_batch_size"], "per_device_train_batch_size")
    if args.get("world_size") is not None:
        set_alias("gpu_count", args["world_size"], "world_size")
    accumulation = number(args.get("gradient_accumulation_steps", 1), "gradient_accumulation_steps", integer=True)
    if values["batch_size"] is not None and values["gpu_count"] is not None:
        effective = values["batch_size"] * accumulation * values["gpu_count"]
        effective = number(effective, "global_batch_size", integer=True)
        if values["global_batch_size"] is not None and values["global_batch_size"] != effective:
            raise ConfigError("Conflicting global batch size and Hugging Face batch settings.")
        values["global_batch_size"] = effective
        sources["global_batch_size"] = ("derived from micro batch, accumulation, and gpu_count",)
    elif values["global_batch_size"] is not None and values["batch_size"] is not None:
        raise ConfigError("Cannot reconcile global batch size without an explicit GPU count.")

    flags = {key: _coerce_field("mixed_precision", args[key]) for key in ("bf16", "fp16") if args.get(key) is not None}
    enabled = [key for key, enabled in flags.items() if enabled]
    if len(enabled) > 1:
        raise ConfigError("Conflicting bf16 and fp16 settings.")
    precision = (values["precision"] or "").lower().replace("torch.", "")
    if (precision in {"bf16", "bfloat16"} and flags.get("bf16") is False
            or precision in {"fp16", "float16"} and flags.get("fp16") is False):
        raise ConfigError("Conflicting precision and mixed-precision flags.")
    if enabled or len(flags) == 2:
        set_alias("mixed_precision", bool(enabled), enabled[0] if enabled else next(iter(flags)))
        if enabled:
            set_alias("precision", enabled[0], enabled[0])

    conditions = dict(config.runtime_conditions)
    for key in ("num_train_epochs", "per_device_train_batch_size", "gradient_accumulation_steps",
                "bf16", "fp16", "world_size", "max_steps", "auto_find_batch_size"):
        if key in args and args[key] is not None:
            normalized = comparable(key, args[key])
            conditions[key] = hashlib.sha256(json.dumps(normalized).encode()).hexdigest()
    conditions["gradient_accumulation_steps"] = hashlib.sha256(json.dumps(accumulation).encode()).hexdigest()
    return replace(config, **values, raw_fields=dict(values), field_sources=sources,
                   config_adapter="huggingface", runtime_conditions=conditions)
