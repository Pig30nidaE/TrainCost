"""GPU cost estimation for TrainCost CI."""

from __future__ import annotations

import re
from typing import Mapping

from .models import Confidence, CostEstimate, TrainingConfig


DEFAULT_GPU_HOURLY_PRICES: dict[str, float] = {
    "t4": 0.35,
    "l4": 0.80,
    "a10": 1.20,
    "a10g": 1.00,
    "v100": 3.06,
    "a100": 4.10,
    "a10040gb": 4.10,
    "a10080gb": 5.12,
    "h100": 10.00,
    "h200": 14.00,
}
DEFAULT_EPOCHS = 1
DEFAULT_GPU_COUNT = 1
DEFAULT_ESTIMATED_MINUTES_PER_EPOCH = 30.0
DEFAULT_GPU_HOURLY_PRICE = 1.0


def estimate_cost(
    config: TrainingConfig,
    *,
    gpu_hourly_prices: Mapping[str, float] | None = None,
    default_epochs: int = DEFAULT_EPOCHS,
    default_gpu_count: int = DEFAULT_GPU_COUNT,
    default_estimated_minutes_per_epoch: float = DEFAULT_ESTIMATED_MINUTES_PER_EPOCH,
    default_gpu_hourly_price: float = DEFAULT_GPU_HOURLY_PRICE,
) -> CostEstimate:
    """Estimate training cost using the transparent MVP formula."""

    missing_fields: list[str] = []
    defaulted_fields: list[str] = []

    epochs = config.effective_epochs
    if epochs is None:
        epochs = default_epochs
        missing_fields.append("epochs")
        defaulted_fields.append("epochs")

    minutes_per_epoch = config.estimated_minutes_per_epoch
    if minutes_per_epoch is None:
        minutes_per_epoch = default_estimated_minutes_per_epoch
        missing_fields.append("estimated_minutes_per_epoch")
        defaulted_fields.append("estimated_minutes_per_epoch")

    gpu_count = config.gpu_count
    if gpu_count is None:
        gpu_count = default_gpu_count
        missing_fields.append("gpu_count")
        defaulted_fields.append("gpu_count")

    price = lookup_gpu_hourly_price(config.gpu_type, gpu_hourly_prices)
    price_source = "known_gpu_type"
    if price is None:
        price = default_gpu_hourly_price
        price_source = "default_gpu_hourly_price"
        defaulted_fields.append("gpu_hourly_price")
        if config.gpu_type is None:
            missing_fields.append("gpu_type")

    estimated_total_minutes = epochs * minutes_per_epoch
    estimated_gpu_hours = estimated_total_minutes / 60 * gpu_count
    estimated_cost_usd = estimated_gpu_hours * price

    return CostEstimate(
        epochs=epochs,
        estimated_minutes_per_epoch=minutes_per_epoch,
        gpu_count=gpu_count,
        gpu_type=config.gpu_type,
        gpu_hourly_price=price,
        estimated_total_minutes=estimated_total_minutes,
        estimated_gpu_hours=estimated_gpu_hours,
        estimated_cost_usd=estimated_cost_usd,
        missing_fields=tuple(dict.fromkeys(missing_fields)),
        defaulted_fields=tuple(dict.fromkeys(defaulted_fields)),
        price_source=price_source,
    )


def lookup_gpu_hourly_price(
    gpu_type: str | None,
    gpu_hourly_prices: Mapping[str, float] | None = None,
) -> float | None:
    """Return a configured hourly price for a GPU type when known."""

    if not gpu_type:
        return None
    prices = dict(DEFAULT_GPU_HOURLY_PRICES)
    if gpu_hourly_prices:
        prices.update({_normalize_gpu_key(key): value for key, value in gpu_hourly_prices.items()})
    return prices.get(_normalize_gpu_key(gpu_type))


def determine_confidence(base_estimate: CostEstimate, pr_estimate: CostEstimate) -> Confidence:
    """Determine estimate confidence from missing/defaulted estimation inputs."""

    missing_fields = tuple(
        dict.fromkeys(base_estimate.missing_fields + pr_estimate.missing_fields)
    )
    defaulted_fields = tuple(
        dict.fromkeys(base_estimate.defaulted_fields + pr_estimate.defaulted_fields)
    )

    if missing_fields:
        return Confidence(
            level="Low",
            reason=(
                "Important cost fields are missing, so conservative defaults were used: "
                + ", ".join(missing_fields)
                + "."
            ),
            missing_fields=missing_fields,
            defaulted_fields=defaulted_fields,
        )
    if "gpu_hourly_price" in defaulted_fields:
        return Confidence(
            level="Medium",
            reason="GPU type was provided but no built-in price was found, so a default hourly price was used.",
            defaulted_fields=defaulted_fields,
        )
    return Confidence(
        level="High",
        reason="Epoch count, GPU type, GPU count, and estimated minutes per epoch were provided.",
    )


def _normalize_gpu_key(gpu_type: str) -> str:
    return re.sub(r"[^a-z0-9]", "", gpu_type.lower())
