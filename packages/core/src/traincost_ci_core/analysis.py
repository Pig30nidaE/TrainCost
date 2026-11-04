"""High-level core engine orchestration."""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from typing import Any, Mapping

from .diff import compare_configs
from .estimation import determine_confidence, estimate_cost
from .models import AnalysisResult, TrainingConfig
from .parsing import load_config_file, normalize_training_config
from .report import generate_markdown_report
from .safety import number, safe_text
from .rules import (
    DEFAULT_COST_INCREASE_THRESHOLD_PERCENT,
    build_recommendations,
    calculate_increase_percent,
    detect_warnings,
)


def analyze_config_files(
    base_path: str | Path,
    pr_path: str | Path,
    *,
    default_budget_limit_usd: float | None = None,
    gpu_hourly_prices: Mapping[str, float] | None = None,
    cost_increase_threshold_percent: float = DEFAULT_COST_INCREASE_THRESHOLD_PERCENT,
) -> AnalysisResult:
    """Analyze two config files without any GitHub API dependency."""

    base_config = load_config_file(base_path)
    pr_config = load_config_file(pr_path)
    return analyze_configs(
        base_config,
        pr_config,
        default_budget_limit_usd=default_budget_limit_usd,
        gpu_hourly_prices=gpu_hourly_prices,
        cost_increase_threshold_percent=cost_increase_threshold_percent,
    )


def analyze_config_dicts(
    base_config: Mapping[str, Any],
    pr_config: Mapping[str, Any],
    *,
    default_budget_limit_usd: float | None = None,
    gpu_hourly_prices: Mapping[str, float] | None = None,
    cost_increase_threshold_percent: float = DEFAULT_COST_INCREASE_THRESHOLD_PERCENT,
) -> AnalysisResult:
    """Analyze raw config mappings."""

    return analyze_configs(
        normalize_training_config(base_config),
        normalize_training_config(pr_config),
        default_budget_limit_usd=default_budget_limit_usd,
        gpu_hourly_prices=gpu_hourly_prices,
        cost_increase_threshold_percent=cost_increase_threshold_percent,
    )


def analyze_configs(
    base_config: TrainingConfig,
    pr_config: TrainingConfig,
    *,
    default_budget_limit_usd: float | None = None,
    gpu_hourly_prices: Mapping[str, float] | None = None,
    cost_increase_threshold_percent: float = DEFAULT_COST_INCREASE_THRESHOLD_PERCENT,
) -> AnalysisResult:
    """Analyze normalized configs and return the complete core output."""

    # This is also a public API: manually constructed dataclasses are untrusted.
    def validated(config):
        clean = normalize_training_config(config.field_values(), source_path=config.source_path)
        return replace(clean,
            sensitive_keys=tuple(sorted(set(clean.sensitive_keys) | {safe_text(k) for k in config.sensitive_keys})),
            field_sources={k: tuple(safe_text(p) for p in config.field_sources.get(k, (k,)))
                           for k, value in clean.field_values().items() if value is not None})
    base_config, pr_config = validated(base_config), validated(pr_config)
    cost_increase_threshold_percent = number(cost_increase_threshold_percent, "warn-increase-percent", allow_zero=True)
    if default_budget_limit_usd is not None:
        default_budget_limit_usd = number(default_budget_limit_usd, "budget-limit", allow_zero=True)
    if gpu_hourly_prices:
        gpu_hourly_prices = {name: number(value, "gpu price", allow_zero=True) for name, value in gpu_hourly_prices.items()}
    changes = compare_configs(base_config, pr_config)
    base_estimate = estimate_cost(base_config, gpu_hourly_prices=gpu_hourly_prices)
    pr_estimate = estimate_cost(pr_config, gpu_hourly_prices=gpu_hourly_prices)
    confidence = determine_confidence(base_estimate, pr_estimate)
    increase_percent = calculate_increase_percent(
        base_estimate.estimated_cost_usd,
        pr_estimate.estimated_cost_usd,
    )
    warnings = detect_warnings(
        base_config,
        pr_config,
        base_estimate,
        pr_estimate,
        changes,
        confidence,
        default_budget_limit_usd=default_budget_limit_usd,
        gpu_hourly_prices=gpu_hourly_prices,
        cost_increase_threshold_percent=cost_increase_threshold_percent,
    )
    recommendations = build_recommendations(warnings)

    result = AnalysisResult(
        base_config=base_config,
        pr_config=pr_config,
        base_estimate=base_estimate,
        pr_estimate=pr_estimate,
        changes=changes,
        increase_percent=increase_percent,
        warnings=warnings,
        recommendations=recommendations,
        confidence=confidence,
    )
    result.markdown_report = generate_markdown_report(result)
    return result
