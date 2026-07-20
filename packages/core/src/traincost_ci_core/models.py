"""Shared data models for TrainCost CI core analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


SUPPORTED_FIELDS = (
    "model",
    "model_name",
    "epochs",
    "max_epochs",
    "batch_size",
    "global_batch_size",
    "precision",
    "mixed_precision",
    "gpu_type",
    "gpu_count",
    "estimated_minutes_per_epoch",
    "dataset_size",
    "budget_limit_usd",
)


@dataclass(frozen=True)
class TrainingConfig:
    """Normalized subset of training config fields used by the MVP engine."""

    model: str | None = None
    model_name: str | None = None
    epochs: int | None = None
    max_epochs: int | None = None
    batch_size: int | None = None
    global_batch_size: int | None = None
    precision: str | None = None
    mixed_precision: bool | None = None
    gpu_type: str | None = None
    gpu_count: int | None = None
    estimated_minutes_per_epoch: float | None = None
    dataset_size: int | None = None
    budget_limit_usd: float | None = None
    raw_fields: Mapping[str, Any] = field(default_factory=dict)
    source_path: str | None = None
    sensitive_keys: tuple[str, ...] = ()

    @property
    def effective_epochs(self) -> int | None:
        """Return the epoch count used for cost estimation."""

        return self.epochs if self.epochs is not None else self.max_epochs

    @property
    def effective_batch_size(self) -> int | None:
        """Return the batch size most relevant to utilization checks."""

        if self.global_batch_size is not None:
            return self.global_batch_size
        return self.batch_size

    @property
    def display_model_name(self) -> str | None:
        """Return the most useful configured model label."""

        return self.model_name or self.model

    def field_values(self) -> dict[str, Any]:
        """Return normalized supported field values, excluding metadata."""

        return {name: getattr(self, name) for name in SUPPORTED_FIELDS}


@dataclass(frozen=True)
class CostEstimate:
    """Estimated GPU training cost from normalized config values."""

    epochs: int
    estimated_minutes_per_epoch: float
    gpu_count: int
    gpu_type: str | None
    gpu_hourly_price: float
    estimated_total_minutes: float
    estimated_gpu_hours: float
    estimated_cost_usd: float
    missing_fields: tuple[str, ...] = ()
    defaulted_fields: tuple[str, ...] = ()
    price_source: str = "default"


@dataclass(frozen=True)
class FieldChange:
    """A supported config field whose normalized value changed."""

    field: str
    before: Any
    after: Any


@dataclass(frozen=True)
class Confidence:
    """Human-facing estimate confidence metadata."""

    level: str
    reason: str
    missing_fields: tuple[str, ...] = ()
    defaulted_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class RiskWarning:
    """A deterministic risk signal raised by the rule engine."""

    code: str
    title: str
    what_changed: str
    why_it_matters: str
    how_to_reduce_risk: str
    recommendation: str


@dataclass
class AnalysisResult:
    """Complete core analysis output for one base/PR config comparison."""

    base_config: TrainingConfig
    pr_config: TrainingConfig
    base_estimate: CostEstimate
    pr_estimate: CostEstimate
    changes: tuple[FieldChange, ...]
    increase_percent: float | None
    warnings: tuple[RiskWarning, ...]
    recommendations: tuple[str, ...]
    confidence: Confidence
    markdown_report: str = ""
