"""Versioned, value-safe JSON representation shared by the CLI and Action."""

from __future__ import annotations

import math
from typing import Any, Iterable

from .models import AnalysisResult, SUPPORTED_FIELDS
from .safety import ConfigError, safe_text

SCHEMA_VERSION = "1.0"
ANALYSIS_STATUSES = frozenset({"complete", "partial", "skipped", "error"})
ESTIMATE_FIELDS = (
    "epochs", "estimated_minutes_per_epoch", "gpu_count", "gpu_type",
    "gpu_hourly_price", "estimated_total_minutes", "estimated_gpu_hours",
    "estimated_cost_usd", "missing_fields", "defaulted_fields", "price_source",
)
WARNING_FIELDS = (
    "code", "title", "what_changed", "why_it_matters", "how_to_reduce_risk",
    "recommendation",
)


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return safe_text(value)
    if isinstance(value, (int, float)):
        try:
            if not math.isfinite(value):
                raise ValueError
        except (ValueError, OverflowError):
            raise ConfigError("Cannot serialize a non-finite analysis value.") from None
        return value
    if isinstance(value, (tuple, list)):
        return [_safe(item) for item in value]
    if isinstance(value, dict):
        return {safe_text(key): _safe(item) for key, item in value.items()}
    raise ConfigError("Cannot serialize an unsupported analysis value.")


def analysis_to_dict(result: AnalysisResult) -> dict[str, Any]:
    """Serialize named public fields only, never raw configuration mappings."""
    def side(config, estimate):
        return {
            "adapter": config.config_adapter,
            "config": {name: getattr(config, name) for name in SUPPORTED_FIELDS},
            "source_path": config.source_path,
            "field_sources": {name: list(paths) for name, paths in config.field_sources.items()
                              if name in SUPPORTED_FIELDS},
            "estimate": {name: getattr(estimate, name) for name in ESTIMATE_FIELDS},
        }

    return _safe({
        "base": side(result.base_config, result.base_estimate),
        "pr": side(result.pr_config, result.pr_estimate),
        "changes": [{"field": change.field, "before": change.before, "after": change.after}
                    for change in result.changes],
        "increase_percent": result.increase_percent,
        "warnings": [{name: getattr(warning, name) for name in WARNING_FIELDS}
                     for warning in result.warnings],
        "recommendations": list(result.recommendations),
        "confidence": {name: getattr(result.confidence, name) for name in
                       ("level", "reason", "missing_fields", "defaulted_fields")},
    })


def make_document(status: str, analyses: Iterable[dict[str, Any]] = (), *,
                  diagnostics: Iterable[str] = (), excluded_count: int = 0) -> dict[str, Any]:
    """Build an envelope whose totals describe analyzed configurations only."""
    if status not in ANALYSIS_STATUSES:
        raise ConfigError("Invalid analysis status.")
    if isinstance(excluded_count, bool) or not isinstance(excluded_count, int) or excluded_count < 0:
        raise ConfigError("Invalid excluded config count.")
    entries = list(analyses)
    if status in {"error", "skipped"} and entries:
        raise ConfigError("Error or skipped analysis cannot include estimates.")
    base = sum(item["base"]["estimate"]["estimated_cost_usd"] for item in entries) if entries else None
    head = sum(item["pr"]["estimate"]["estimated_cost_usd"] for item in entries) if entries else None
    return _safe({
        "schema_version": SCHEMA_VERSION,
        "analysis_status": status,
        "analyses": entries,
        "diagnostics": list(diagnostics),
        "summary": {
            "analyzed_count": len(entries), "excluded_count": excluded_count,
            "base_cost_usd": base, "pr_cost_usd": head,
            "scope": "analyzed_configs_only",
        },
    })
