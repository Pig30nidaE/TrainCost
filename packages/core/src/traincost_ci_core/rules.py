"""Deterministic risk rules for TrainCost CI."""

from __future__ import annotations

import re
import math
from typing import Mapping

from .estimation import lookup_gpu_hourly_price
from .formatting import format_money, format_money_pair
from .models import Confidence, CostEstimate, FieldChange, RiskWarning, TrainingConfig
from .safety import ConfigError


DEFAULT_COST_INCREASE_THRESHOLD_PERCENT = 50.0


def calculate_increase_percent(base_cost: float, pr_cost: float) -> float | None:
    """Return percentage cost change from base to PR when meaningful."""

    if base_cost <= 0:
        return None
    increase = ((pr_cost - base_cost) / base_cost) * 100
    if not math.isfinite(increase):
        raise ConfigError("Cost increase arithmetic overflow.")
    return increase


def detect_warnings(
    base_config: TrainingConfig,
    pr_config: TrainingConfig,
    base_estimate: CostEstimate,
    pr_estimate: CostEstimate,
    changes: tuple[FieldChange, ...],
    confidence: Confidence,
    *,
    default_budget_limit_usd: float | None = None,
    gpu_hourly_prices: Mapping[str, float] | None = None,
    cost_increase_threshold_percent: float = DEFAULT_COST_INCREASE_THRESHOLD_PERCENT,
) -> tuple[RiskWarning, ...]:
    """Run all MVP risk rules."""

    warnings: list[RiskWarning] = []
    change_lookup = {change.field: change for change in changes}
    increase_percent = calculate_increase_percent(
        base_estimate.estimated_cost_usd,
        pr_estimate.estimated_cost_usd,
    )

    budget_limit = pr_config.budget_limit_usd
    if budget_limit is None:
        budget_limit = default_budget_limit_usd
    if budget_limit is not None and pr_estimate.estimated_cost_usd > budget_limit:
        cost_display, budget_display = format_money_pair(pr_estimate.estimated_cost_usd, budget_limit)
        warnings.append(
            RiskWarning(
                code="budget_exceeded",
                title="Budget limit exceeded",
                what_changed=(
                    f"Estimated PR cost is {cost_display}, "
                    f"above the {budget_display} budget."
                ),
                why_it_matters="The run may spend more than the configured experiment budget.",
                how_to_reduce_risk="Reduce epochs, GPU count, runtime per epoch, or choose a lower-cost GPU.",
                recommendation="Reduce the planned run or raise `budget_limit_usd` only if the spend is intentional.",
            )
        )

    if increase_percent is not None and increase_percent > cost_increase_threshold_percent:
        warnings.append(
            RiskWarning(
                code="cost_increase",
                title=f"Estimated cost increased by more than {cost_increase_threshold_percent:g}%",
                what_changed=(
                    f"Estimated cost changed from {format_money_pair(base_estimate.estimated_cost_usd, pr_estimate.estimated_cost_usd)[0]} "
                    f"to {format_money_pair(base_estimate.estimated_cost_usd, pr_estimate.estimated_cost_usd)[1]} "
                    f"({_format_percent(increase_percent)})."
                ),
                why_it_matters="Large cost increases are easy to miss in config review.",
                how_to_reduce_risk="Confirm that the larger training run is required before merge.",
                recommendation="Run a short dry run and confirm the expected cost increase is acceptable.",
            )
        )

    base_epochs = base_config.effective_epochs
    pr_epochs = pr_config.effective_epochs
    if (
        base_epochs is not None
        and pr_epochs is not None
        and pr_epochs > base_epochs
        and (pr_epochs - base_epochs >= 5 or pr_epochs >= base_epochs * 1.5)
    ):
        warnings.append(
            RiskWarning(
                code="epochs_increased",
                title="Epoch count increased significantly",
                what_changed=f"Epoch count changed from {base_epochs:g} to {pr_epochs:g}.",
                why_it_matters="Training cost usually scales linearly with epochs.",
                how_to_reduce_risk="Use fewer epochs, early stopping, or a staged run before full training.",
                recommendation="Confirm the higher epoch count is needed or run a smaller validation job first.",
            )
        )

    base_gpu_price = lookup_gpu_hourly_price(base_config.gpu_type, gpu_hourly_prices)
    pr_gpu_price = lookup_gpu_hourly_price(pr_config.gpu_type, gpu_hourly_prices)
    if (
        base_config.gpu_type
        and pr_config.gpu_type
        and base_gpu_price is not None
        and pr_gpu_price is not None
        and pr_gpu_price > base_gpu_price
    ):
        warnings.append(
            RiskWarning(
                code="gpu_type_more_expensive",
                title="GPU type changed to a more expensive option",
                what_changed=(
                    f"GPU type changed from {base_config.gpu_type} "
                    f"({format_money_pair(base_gpu_price, pr_gpu_price)[0]}/hour) to {pr_config.gpu_type} "
                    f"({format_money_pair(base_gpu_price, pr_gpu_price)[1]}/hour)."
                ),
                why_it_matters="Higher hourly GPU prices raise total training cost even if runtime stays flat.",
                how_to_reduce_risk="Use the smaller GPU when it meets memory and throughput needs.",
                recommendation="Confirm the more expensive GPU is required for memory, speed, or availability.",
            )
        )

    if (
        base_config.gpu_count is not None
        and pr_config.gpu_count is not None
        and pr_config.gpu_count > base_config.gpu_count
    ):
        warnings.append(
            RiskWarning(
                code="gpu_count_increased",
                title="GPU count increased",
                what_changed=f"GPU count changed from {base_config.gpu_count} to {pr_config.gpu_count}.",
                why_it_matters="The estimate multiplies runtime by GPU count.",
                how_to_reduce_risk="Use fewer GPUs or shorten the run when multi-GPU training is not required.",
                recommendation="Confirm the additional GPUs improve throughput enough to justify the cost.",
            )
        )

    precision_change = change_lookup.get("precision")
    mixed_precision_change = change_lookup.get("mixed_precision")
    if pr_config.mixed_precision is False or (
        pr_config.mixed_precision is None and _uses_fp32(pr_config.precision)
    ):
        changed_bits: list[str] = []
        if precision_change is not None:
            changed_bits.append(
                f"precision changed from {_format_value(precision_change.before)} "
                f"to {_format_value(precision_change.after)}"
            )
        elif pr_config.precision is not None:
            changed_bits.append(f"precision is {pr_config.precision}")
        if mixed_precision_change is not None:
            changed_bits.append(
                f"mixed_precision changed from {_format_value(mixed_precision_change.before)} "
                f"to {_format_value(mixed_precision_change.after)}"
            )
        elif pr_config.mixed_precision is False:
            changed_bits.append("mixed_precision is disabled")

        warnings.append(
            RiskWarning(
                code="precision_risk",
                title="Mixed precision appears disabled",
                what_changed="; ".join(changed_bits) + ".",
                why_it_matters="fp32 or disabled mixed precision can increase memory use and runtime.",
                how_to_reduce_risk="Use bf16/fp16 mixed precision when the model and hardware support it.",
                recommendation="Re-enable mixed precision if it is safe for this training job.",
            )
        )

    per_device_batch = pr_config.config_adapter == "huggingface" and pr_config.batch_size is not None
    batch_size = pr_config.batch_size if per_device_batch else pr_config.effective_batch_size
    if batch_size is not None and (batch_size <= 4 or (batch_size <= 8 and _is_large_model(pr_config))):
        warnings.append(
            RiskWarning(
                code="small_batch_size",
                title="Batch size is unusually small",
                what_changed=f"{'Per-device batch size' if per_device_batch else 'Batch size'} is {batch_size}.",
                why_it_matters="Very small batches can reduce GPU utilization and extend runtime.",
                how_to_reduce_risk="Measure GPU utilization with a dry run and increase the batch size if GPU memory allows.",
                recommendation="Check GPU utilization and consider a larger batch that fits in memory.",
            )
        )

    hf_supported = {"num_train_epochs", "per_device_train_batch_size", "gradient_accumulation_steps", "bf16", "fp16", "world_size", "max_steps", "auto_find_batch_size", "use_cpu", "no_cuda", "use_tpu", "tpu_num_cores"}
    unsupported = set()
    for config in (base_config, pr_config):
        unsupported.update(set(config.runtime_conditions) - (hf_supported if config.config_adapter == "huggingface" else set()))
    if unsupported:
        warnings.append(RiskWarning(
            code="unsupported_training_settings", title="Training settings are not modeled",
            what_changed="Detected settings: " + ", ".join(sorted(unsupported)) + ".",
            why_it_matters="These settings may affect training runtime but are not included in the cost formula.",
            how_to_reduce_risk="Measure runtime with these settings and update estimated_minutes_per_epoch.",
            recommendation="Review unsupported settings and provide a measured runtime per epoch.",
        ))

    changed_runtime = {change.field for change in changes if change.field in {
        "model", "model_name", "batch_size", "global_batch_size", "precision", "mixed_precision",
        "gpu_type", "gpu_count", "dataset_size",
    }}
    changed_runtime.update(key for key in set(base_config.runtime_conditions) | set(pr_config.runtime_conditions)
                           if base_config.runtime_conditions.get(key) != pr_config.runtime_conditions.get(key)
                           and not (base_config.config_adapter == pr_config.config_adapter == "huggingface"
                                    and key in {"num_train_epochs", "max_steps", "world_size",
                                                "per_device_train_batch_size", "bf16", "fp16",
                                                "auto_find_batch_size", "use_cpu", "no_cuda", "use_tpu", "tpu_num_cores"}))
    if (changed_runtime and base_config.estimated_minutes_per_epoch is not None
            and base_config.estimated_minutes_per_epoch == pr_config.estimated_minutes_per_epoch):
        warnings.append(RiskWarning(
            code="stale_runtime_assumption", title="Runtime assumption may be stale",
            what_changed="Runtime-affecting settings changed: " + ", ".join(sorted(changed_runtime)) + "; minutes per epoch stayed the same.",
            why_it_matters="The supplied runtime may no longer represent the changed training conditions.",
            how_to_reduce_risk="Measure runtime under the new conditions and update estimated_minutes_per_epoch.",
            recommendation="Re-measure minutes per epoch after runtime-affecting changes.",
        ))

    if confidence.level == "Low":
        warnings.append(
            RiskWarning(
                code="low_confidence_missing_fields",
                title="Missing fields reduce estimate confidence",
                what_changed="Missing fields: " + ", ".join(confidence.missing_fields) + ".",
                why_it_matters="The estimate uses illustrative defaults that may understate or overstate actual cost.",
                how_to_reduce_risk="Add epochs, gpu_type, gpu_count, and estimated_minutes_per_epoch to the config.",
                recommendation="Add missing cost fields so future TrainCost CI reports are more useful.",
            )
        )

    sensitive_keys = sorted(set(base_config.sensitive_keys) | set(pr_config.sensitive_keys))
    if sensitive_keys:
        warnings.append(
            RiskWarning(
                code="sensitive_config_value",
                title="Sensitive-looking config key detected",
                what_changed="Sensitive-looking values were excluded at: " + ", ".join(sensitive_keys) + ".",
                why_it_matters="Training configs can be printed in CI logs and reviewed in pull requests.",
                how_to_reduce_risk="Move secrets to GitHub Actions secrets or another secret manager.",
                recommendation="Remove sensitive values from training config files.",
            )
        )

    return tuple(warnings)


def build_recommendations(warnings: tuple[RiskWarning, ...]) -> tuple[str, ...]:
    """Return concise recommendations derived from warnings."""

    if not warnings:
        return (
            "No major cost action needed based on the provided config values.",
            "Keep `budget_limit_usd` and runtime estimates current as experiments change.",
        )

    recommendations = ["Run a short dry run before launching the full training job."]
    for warning in warnings:
        if warning.recommendation not in recommendations:
            recommendations.append(warning.recommendation)
    return tuple(recommendations)


def _uses_fp32(precision: str | None) -> bool:
    if precision is None:
        return False
    normalized = precision.strip().lower().replace("torch.", "")
    return normalized in {"fp32", "float32", "32", "32bit", "full"} or "fp32" in normalized


def _is_large_model(config: TrainingConfig) -> bool:
    model_name = (config.display_model_name or "").lower()
    large_markers = ("large", "xl", "huge", "giant", "gpt", "llama", "mixtral")
    if any(marker in model_name for marker in large_markers):
        return True
    # Parameter counts in the name, such as 7b, 13b, 1.5b, or 70B.
    param_match = re.search(r"(\d+(?:\.\d+)?)\s*b\b", model_name)
    if param_match and float(param_match.group(1)) >= 7:
        return True
    return config.dataset_size is not None and config.dataset_size >= 1_000_000


def _format_percent(value: float) -> str:
    sign = "+" if value >= 0 else ""
    if abs(value) >= 100:
        return f"{sign}{value:,.0f}%"
    return f"{sign}{value:,.1f}%"


def _format_value(value: object) -> str:
    if value is None:
        return "not set"
    return str(value)
