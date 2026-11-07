"""Independent arithmetic and measurement checks for the HF demo.

The supplied price is an illustrative assumption, not a provider quote or bill.
This module intentionally has no TrainCost core dependency.
"""

from decimal import Decimal, InvalidOperation
from numbers import Real
from statistics import median


def _positive_decimal(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive finite number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{name} must be a positive finite number") from None
    if not result.is_finite() or result <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return result


def decimal_cost(epochs, minutes, gpu_count=1, price="1.00"):
    """Return the assumed USD cost without rounding the calculation."""
    epochs = _positive_decimal(epochs, "epochs")
    minutes = _positive_decimal(minutes, "minutes")
    gpu_count = _positive_decimal(gpu_count, "gpu_count")
    if gpu_count != gpu_count.to_integral_value():
        raise ValueError("gpu_count must be a positive integer")
    if isinstance(price, bool):
        raise ValueError("price must be a non-negative finite number")
    try:
        price = Decimal(str(price))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("price must be a non-negative finite number") from None
    if not price.is_finite() or price < 0:
        raise ValueError("price must be a non-negative finite number")
    return epochs * minutes * gpu_count * price / Decimal(60)


def _measurements(values, name):
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must contain exactly three measurements")
    try:
        values = list(values)
    except TypeError:
        raise ValueError(f"{name} must contain exactly three measurements") from None
    if len(values) != 3:
        raise ValueError(f"{name} must contain exactly three measurements")
    if any(isinstance(value, bool) or not isinstance(value, (Real, Decimal)) for value in values):
        raise ValueError(f"{name} must contain numeric measurements")
    return [_positive_decimal(value, name) for value in values]


def evaluate_measurements(calibration_seconds, base_seconds, pr_seconds):
    """Check three independent samples per group against fixed demo thresholds.

    The calibration median is fixed before evaluating separate base and PR runs.
    Return JSON-serializable values in seconds; timeout handling is external.
    """
    groups = {
        "calibration": _measurements(calibration_seconds, "calibration_seconds"),
        "base": _measurements(base_seconds, "base_seconds"),
        "pr": _measurements(pr_seconds, "pr_seconds"),
    }
    medians = {name: median(values) for name, values in groups.items()}
    predictions = {"base": medians["calibration"], "pr": 3 * medians["calibration"]}
    repeatable = {
        name: all(abs(value - medians[name]) <= Decimal("0.15") * medians[name] for value in values)
        for name, values in groups.items()
    }
    relative_errors = {
        name: abs(predictions[name] - medians[name]) / medians[name]
        for name in predictions
    }
    return {
        "status": "PASS" if all(repeatable.values()) and all(v <= Decimal("0.20") for v in relative_errors.values()) else "FAIL",
        "calibration_median_seconds": float(medians["calibration"]),
        "predicted_seconds": {name: float(value) for name, value in predictions.items()},
        "observed_median_seconds": {name: float(medians[name]) for name in predictions},
        "relative_errors": {name: float(value) for name, value in relative_errors.items()},
        "repeatable": repeatable,
    }
