"""Markdown report generation for TrainCost CI."""

from __future__ import annotations

from .models import AnalysisResult


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
            lines.append(f"- {change.field}: {_format_value(change.before)} -> {_format_value(change.after)}")
    else:
        lines.append("- No supported fields changed.")

    lines.extend(["", "### Estimated cost", ""])
    lines.append(f"- Base branch: {_format_money(result.base_estimate.estimated_cost_usd)}")
    lines.append(f"- This PR: {_format_money(result.pr_estimate.estimated_cost_usd)}")
    if result.increase_percent is None:
        lines.append("- Increase: not available")
    else:
        lines.append(f"- Increase: {_format_percent(result.increase_percent)}")

    lines.extend(["", "### Warnings", ""])
    if result.warnings:
        for warning in result.warnings:
            lines.append(
                f"- {warning.title}: {warning.what_changed} "
                f"{warning.why_it_matters} {warning.how_to_reduce_risk}"
            )
    else:
        lines.append("- No major cost warnings.")

    lines.extend(["", "### Recommendations", ""])
    for recommendation in result.recommendations:
        lines.append(f"- {recommendation}")

    lines.extend(["", "### Confidence", ""])
    lines.append(f"- {result.confidence.level}.")
    lines.append(f"- Reason: {result.confidence.reason}")

    return "\n".join(lines) + "\n"


def _format_money(value: float) -> str:
    return f"${value:,.2f}"


def _format_percent(value: float) -> str:
    sign = "+" if value >= 0 else ""
    if abs(value) >= 100:
        return f"{sign}{value:,.0f}%"
    return f"{sign}{value:,.1f}%"


def _format_value(value: object) -> str:
    if value is None:
        return "not set"
    return str(value)
