"""Markdown report generation for TrainCost CI."""

from __future__ import annotations

from .models import AnalysisResult, CostEstimate
from .formatting import format_money, format_money_pair
from .safety import markdown


_PRICE_SOURCE_DESCRIPTIONS = {
    "gpu_prices_input": "from the gpu-prices input",
    "builtin_price_table": "illustrative built-in price; not a provider quote",
    "default_hourly_price": "fallback default; set gpu_type or gpu-prices for a better estimate",
}


def generate_markdown_report(result: AnalysisResult) -> str:
    """Render a concise Markdown report for PR review."""

    lines: list[str] = ["## TrainCost CI Report", ""]

    if result.confidence.level == "Low":
        lines.extend(["Low-confidence estimate.", ""])
    elif result.warnings:
        lines.extend(["Cost risk detected.", ""])
    else:
        lines.extend(["No major cost risk detected.", ""])

    lines.extend(["### Changed", ""])
    if result.changes:
        for change in result.changes:
            lines.append(f"- {change.field}: {markdown(_format_value(change.before))} -> {markdown(_format_value(change.after))}")
    else:
        lines.append("- No supported fields changed.")

    lines.extend(["", "### Estimated cost", ""])
    base_cost, pr_cost = format_money_pair(result.base_estimate.estimated_cost_usd, result.pr_estimate.estimated_cost_usd)
    lines.append(f"- Base branch: {base_cost}")
    lines.append(f"- This PR: {pr_cost}")
    if result.increase_percent is None:
        lines.append("- Increase: not available")
    else:
        lines.append(f"- Increase: {_format_percent(result.increase_percent)}")
    lines.append(_describe_gpu_pricing(result.base_estimate, result.pr_estimate))

    lines.extend(["", "### Warnings", ""])
    if result.warnings:
        for warning in result.warnings:
            lines.append(
                f"- {markdown(warning.title)}: {markdown(warning.what_changed)} "
                f"{markdown(warning.why_it_matters)} {markdown(warning.how_to_reduce_risk)}"
            )
    else:
        lines.append("- No major cost warnings.")

    lines.extend(["", "### Recommendations", ""])
    for recommendation in result.recommendations:
        lines.append(f"- {markdown(recommendation)}")

    lines.extend(["", "### Confidence", ""])
    lines.append(f"- {result.confidence.level}.")
    lines.append(f"- Reason: {result.confidence.reason}")
    lines.append("- Confidence describes input completeness, not billing accuracy or measured runtime.")
    lines.extend(["", "### Inputs and assumptions", ""])
    for label, config, estimate in (("Base", result.base_config, result.base_estimate), ("PR", result.pr_config, result.pr_estimate)):
        if config.source_path:
            lines.append(f"- {label} config file: {markdown(config.source_path)}.")
        lines.append(f"- {label} applied: epochs={estimate.epochs:g}, minutes/epoch={estimate.estimated_minutes_per_epoch:g}, GPU count={estimate.gpu_count}.")
        for field, paths in config.field_sources.items():
            value = config.field_values().get(field)
            if value is not None:
                lines.append(f"- {label} {field}: {markdown(_format_value(value))}; source: {markdown(', '.join(paths))}.")
        defaults = ', '.join(estimate.defaulted_fields) or "none"
        lines.append(f"- {label} defaulted fields: {defaults}.")
    lines.append("- Runtime per epoch is supplied or assumed; GPU scaling speedups are not modeled.")

    return "\n".join(lines) + "\n"


def _describe_gpu_pricing(base_estimate: CostEstimate, pr_estimate: CostEstimate) -> str:
    base_fragment = _gpu_price_fragment(base_estimate)
    pr_fragment = _gpu_price_fragment(pr_estimate)
    base_source = _PRICE_SOURCE_DESCRIPTIONS.get(base_estimate.price_source, base_estimate.price_source)
    pr_source = _PRICE_SOURCE_DESCRIPTIONS.get(pr_estimate.price_source, pr_estimate.price_source)
    return f"- GPU price: Base {base_fragment} ({base_source}); PR {pr_fragment} ({pr_source})"


def _gpu_price_fragment(estimate: CostEstimate) -> str:
    gpu_label = markdown(estimate.gpu_type or "unknown GPU")
    return f"{gpu_label} at {format_money(estimate.gpu_hourly_price)}/hour"


def _format_percent(value: float) -> str:
    sign = "+" if value >= 0 else ""
    if abs(value) >= 100:
        return f"{sign}{value:,.0f}%"
    return f"{sign}{value:,.1f}%"


def _format_value(value: object) -> str:
    if value is None:
        return "not set"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)
