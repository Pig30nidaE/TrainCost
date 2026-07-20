"""Config loading and normalization for TrainCost CI."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .models import SUPPORTED_FIELDS, TrainingConfig


_STRING_FIELDS = {"model", "model_name", "precision", "gpu_type"}
_INT_FIELDS = {
    "epochs",
    "max_epochs",
    "batch_size",
    "global_batch_size",
    "gpu_count",
    "dataset_size",
}
_FLOAT_FIELDS = {"estimated_minutes_per_epoch", "budget_limit_usd"}
_BOOL_FIELDS = {"mixed_precision"}
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_key",
    "secret",
    "password",
    "passwd",
    "token",
    "credential",
)


def load_config_file(path: str | Path) -> TrainingConfig:
    """Load a YAML or JSON config file and return a normalized config."""

    config_path = Path(path)
    raw = parse_config_text(
        config_path.read_text(encoding="utf-8"),
        file_format=config_path.suffix.lower(),
    )
    return normalize_training_config(raw, source_path=str(config_path))


def parse_config_text(text: str, file_format: str) -> dict[str, Any]:
    """Parse config text for the supported MVP formats."""

    normalized_format = file_format.lower().lstrip(".")
    if normalized_format in {"yaml", "yml"}:
        return parse_yaml_text(text)
    if normalized_format == "json":
        parsed = json.loads(text)
        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise ValueError("JSON config must contain an object at the top level.")
        return parsed
    if normalized_format == "py":
        return parse_python_config_text(text)
    raise ValueError(f"Unsupported config format: {file_format}")


def parse_python_config_text(text: str) -> dict[str, Any]:
    """Parse simple Python config files without executing code."""

    tree = ast.parse(text)
    parsed: dict[str, Any] = {}

    for node in tree.body:
        if isinstance(node, ast.Assign):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    parsed[target.id] = value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            try:
                parsed[node.target.id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue

    return parsed


def parse_yaml_text(text: str) -> dict[str, Any]:
    """Parse YAML config text.

    PyYAML is used when available. The fallback intentionally supports only
    common config YAML: nested mappings with scalar values.
    """

    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return _parse_simple_yaml(text)

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML config: {exc}") from exc
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError("YAML config must contain a mapping at the top level.")
    return parsed


def normalize_training_config(
    raw_config: Mapping[str, Any],
    *,
    source_path: str | None = None,
) -> TrainingConfig:
    """Extract supported fields from a raw config mapping."""

    extracted: dict[str, Any] = {}
    for key, value in _walk_mapping(raw_config):
        normalized_key = str(key).strip().lower()
        if normalized_key in SUPPORTED_FIELDS and normalized_key not in extracted:
            extracted[normalized_key] = value

    coerced = {
        field_name: _coerce_field(field_name, extracted.get(field_name))
        for field_name in SUPPORTED_FIELDS
    }
    return TrainingConfig(
        **coerced,
        raw_fields=extracted,
        source_path=source_path,
        sensitive_keys=tuple(sorted(_find_sensitive_keys(raw_config))),
    )


def _walk_mapping(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key), child
            yield from _walk_mapping(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_mapping(child)


def _coerce_field(field_name: str, value: Any) -> Any:
    if value is None:
        return None
    if field_name in _STRING_FIELDS:
        if isinstance(value, (Mapping, list)):
            return None
        return str(value).strip()
    if field_name in _INT_FIELDS:
        return _coerce_int(value)
    if field_name in _FLOAT_FIELDS:
        return _coerce_float(value)
    if field_name in _BOOL_FIELDS:
        return _coerce_bool(value)
    return value


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1", "on", "enabled"}:
            return True
        if lowered in {"false", "no", "n", "0", "off", "disabled"}:
            return False
    return None


def _find_sensitive_keys(value: Any, prefix: str = "") -> set[str]:
    matches: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            lowered = key_text.lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                matches.add(path)
            matches.update(_find_sensitive_keys(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.update(_find_sensitive_keys(child, f"{prefix}[{index}]"))
    return matches


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in text.splitlines():
        line_without_comments = _strip_yaml_comment(raw_line.rstrip())
        if not line_without_comments.strip():
            continue
        if line_without_comments.strip() in {"---", "..."}:
            continue

        indent = len(line_without_comments) - len(line_without_comments.lstrip(" "))
        stripped = line_without_comments.strip()
        if stripped.startswith("- "):
            continue
        if ":" not in stripped:
            continue

        while stack and indent <= stack[-1][0]:
            stack.pop()

        key_text, value_text = stripped.split(":", 1)
        key = _strip_quotes(key_text.strip())
        parent = stack[-1][1]

        if value_text.strip() == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_yaml_scalar(value_text.strip())

    return root


def _strip_yaml_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
            continue
        if char == "#" and quote is None:
            return line[:index].rstrip()
    return line


def _parse_yaml_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"null", "none", "~"}:
        return None
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False

    quoted = _strip_quotes(value)
    if quoted != value:
        return quoted

    if value.startswith("[") or value.startswith("{"):
        for parser in (json.loads, ast.literal_eval):
            try:
                return parser(value)
            except (ValueError, SyntaxError, json.JSONDecodeError):
                continue
        raise ValueError(f"Invalid YAML scalar value: {value!r}")

    try:
        return int(value.replace(",", ""))
    except ValueError:
        pass
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return value


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
