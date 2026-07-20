"""Base vs PR config comparison."""

from __future__ import annotations

from .models import SUPPORTED_FIELDS, FieldChange, TrainingConfig


def compare_configs(base_config: TrainingConfig, pr_config: TrainingConfig) -> tuple[FieldChange, ...]:
    """Return supported field changes between normalized configs."""

    changes: list[FieldChange] = []
    for field_name in SUPPORTED_FIELDS:
        before = getattr(base_config, field_name)
        after = getattr(pr_config, field_name)
        if before != after:
            changes.append(FieldChange(field_name, before, after))
    return tuple(changes)
