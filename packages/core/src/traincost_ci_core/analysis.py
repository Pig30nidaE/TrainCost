"""High-level core engine orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .diff import compare_configs
from .estimation import determine_confidence, estimate_cost
from .models import AnalysisResult, TrainingConfig
from .parsing import load_config_file, normalize_training_config
from .report import generate_markdown_report
from .rules import build_recommendations, calculate_increase_percent, detect_warnings


def analyze_config_files(
    base_path: str | Path,
    pr_path: str | Path,
    *,
    default_budget_limit_usd: float | None = None,
    gpu_hourly_prices: Mapping[str, float] | None = None,
) -> AnalysisResult:
    """Analyze two config files without any GitHub API dependency."""

    base_config = load_config_file(base_path)
    pr_config = load_config_file(pr_path)
    return analyze_configs(
        base_config,
        pr_config,
        default_budget_limit_usd=default_budget_limit_usd,
        gpu_hourly_prices=gpu_hourly_prices,
    )


def analyze_config_dicts(
    base_config: Mapping[str, Any],
    pr_config: Mapping[str, Any],
    *,
    default_budget_limit_usd: float | None = None,
    gpu_hourly_prices: Mapping[str, float] | None = None,
) -> AnalysisResult:
    """Analyze raw config mappings."""

    return analyze_configs(
        normalize_training_config(base_config),
        normalize_training_config(pr_config),
        default_budget_limit_usd=default_budget_limit_usd,
        gpu_hourly_prices=gpu_hourly_prices,
    )


def analyze_configs(
    base_config: TrainingConfig,
    pr_config: TrainingConfig,
    *,
    default_budget_limit_usd: float | None = None,
    gpu_hourly_prices: Mapping[str, float] | None = None,
) -> AnalysisResult:
    """Analyze normalized configs and return the complete core output."""

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
