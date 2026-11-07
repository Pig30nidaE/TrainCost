"""GPU cost estimation for TrainCost CI."""

from __future__ import annotations

import re
import math
from typing import Mapping

from .models import Confidence, CostEstimate, TrainingConfig
from .safety import ConfigError, number


# Illustrative USD/GPU-hour values, not provider quotes or market averages.
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
    default_epochs: float = DEFAULT_EPOCHS,
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

    price, price_source = _lookup_price_and_source(config.gpu_type, gpu_hourly_prices)
    if price is None:
        price = default_gpu_hourly_price
        price_source = "default_hourly_price"
        defaulted_fields.append("gpu_hourly_price")
        if config.gpu_type is None:
            missing_fields.append("gpu_type")

    epochs = number(epochs, "epochs")
    minutes_per_epoch = number(minutes_per_epoch, "estimated_minutes_per_epoch")
    gpu_count = number(gpu_count, "gpu_count", integer=True)
    price = number(price, "gpu_hourly_price", allow_zero=True)
    estimated_total_minutes = epochs * minutes_per_epoch
    estimated_gpu_hours = estimated_total_minutes / 60 * gpu_count
    estimated_cost_usd = estimated_gpu_hours * price
    if not all(math.isfinite(v) for v in (estimated_total_minutes, estimated_gpu_hours, estimated_cost_usd)):
        raise ConfigError("Estimated cost arithmetic overflow; reduce numeric inputs.")

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

    return _lookup_price_and_source(gpu_type, gpu_hourly_prices)[0]


def _lookup_price_and_source(
    gpu_type: str | None,
    gpu_hourly_prices: Mapping[str, float] | None,
) -> tuple[float | None, str]:
    """Return (price, source) where source records where the price came from."""

    if not gpu_type:
        return None, "default_hourly_price"
    key = _normalize_gpu_key(gpu_type)
    if gpu_hourly_prices:
        overrides = {_normalize_gpu_key(name): number(value, "gpu price", allow_zero=True) for name, value in gpu_hourly_prices.items()}
        if key in overrides:
            return overrides[key], "gpu_prices_input"
    if key in DEFAULT_GPU_HOURLY_PRICES:
        return DEFAULT_GPU_HOURLY_PRICES[key], "builtin_price_table"
    return None, "default_hourly_price"


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
                "Important cost fields are missing, so illustrative defaults were used: "
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
