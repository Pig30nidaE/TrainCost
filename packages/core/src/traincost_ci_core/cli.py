"""Installed local CLI. It never executes training code or contacts GitHub."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from .analysis import analyze_config_files
from .output_safety import OutputPathError, validate_report_paths, write_report_files
from .safety import ConfigError, looks_sensitive, markdown, number
from .serialization import analysis_to_dict, make_document


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ConfigError("Invalid command arguments; use --help for supported options.")


def parse_prices(value: str) -> dict[str, float]:
    prices, names = {}, set()
    for part in value.split(","):
        if not part.strip():
            continue
        name, separator, amount = part.partition("=")
        normalized = re.sub(r"[^a-z0-9]", "", name.lower())
        if not separator or not normalized or normalized in names or looks_sensitive(name):
            raise ConfigError("Invalid gpu-prices; use unique NAME=PRICE entries.")
        names.add(normalized)
        prices[name.strip()] = number(amount, "gpu price", allow_zero=True)
    return prices


def main(argv=None) -> int:
    parser = SafeArgumentParser(description="Compare local ML configs without running training code.")
    parser.add_argument("--base-config", required=True)
    parser.add_argument("--head-config", required=True)
    parser.add_argument("--adapter", default="canonical")
    parser.add_argument("--gpu-prices", default="")
    parser.add_argument("--budget-limit")
    parser.add_argument("--warn-increase-percent", default="50")
    parser.add_argument("--report-path", default="report.md")
    parser.add_argument("--json-path", default="")
    try:
        args = parser.parse_args(argv)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    report_path, json_path = Path("report.md"), Path("report.json")
    input_paths = (args.base_config, args.head_config)
    try:
        if not args.report_path.strip():
            raise OutputPathError("Invalid output path.")
        candidate_report = Path(args.report_path)
        try:
            candidate_json = Path(args.json_path) if args.json_path else candidate_report.with_suffix(".json")
        except ValueError:
            raise OutputPathError("Invalid output path.") from None
        validate_report_paths(candidate_report, candidate_json, protected_paths=input_paths, workspace_root=Path.cwd())
        report_path, json_path = candidate_report, candidate_json
        if args.adapter not in {"canonical", "huggingface"}:
            raise ConfigError("adapter must be canonical or huggingface.")
        budget = None if args.budget_limit is None else number(args.budget_limit, "budget-limit", allow_zero=True)
        result = analyze_config_files(args.base_config, args.head_config,
            adapter=args.adapter, gpu_hourly_prices=parse_prices(args.gpu_prices),
            default_budget_limit_usd=budget,
            cost_increase_threshold_percent=number(args.warn_increase_percent, "warn-increase-percent", allow_zero=True))
        document = make_document("complete", [{"path": args.head_config, **analysis_to_dict(result)}])
        report = result.markdown_report
    except OutputPathError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ConfigError as exc:
        document = make_document("error", diagnostics=[str(exc)])
        report = "## TrainCost CI Report\n\nNo cost estimate was produced.\n\n- " + markdown(str(exc)) + "\n"
    except (OSError, UnicodeError, ValueError, RecursionError):
        document = make_document("error", diagnostics=["Analysis failed: unreadable or invalid input."])
        report = "## TrainCost CI Report\n\nNo cost estimate was produced.\n\n- Unreadable or invalid input.\n"
    try:
        encoded = json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        write_report_files(report_path, json_path, report, encoded, protected_paths=input_paths, workspace_root=Path.cwd())
    except (OSError, ValueError):
        print("TrainCost CI could not write its report outputs.", file=sys.stderr)
        return 2
    print(f"TrainCost CI analysis-status: {document['analysis_status']}")
    return 2 if document["analysis_status"] == "error" else 0
