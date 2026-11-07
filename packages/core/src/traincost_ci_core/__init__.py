"""Core engine for TrainCost CI's deterministic ML training cost review."""

__version__ = "0.2.0b1"

from .analysis import analyze_config_dicts, analyze_config_files, analyze_configs
from .diff import compare_configs
from .estimation import (
    DEFAULT_GPU_HOURLY_PRICES,
    estimate_cost,
    lookup_gpu_hourly_price,
)
from .models import (
    SUPPORTED_FIELDS,
    AnalysisResult,
    Confidence,
    CostEstimate,
    FieldChange,
    RiskWarning,
    TrainingConfig,
)
from .formatting import format_money, format_money_pair
from .parsing import (
    load_config_file,
    normalize_training_config,
    parse_config_text,
    parse_python_config_text,
    parse_yaml_text,
)
from .report import generate_markdown_report
from .rules import (
    DEFAULT_COST_INCREASE_THRESHOLD_PERCENT,
    build_recommendations,
    calculate_increase_percent,
    detect_warnings,
)

__all__ = [
    "AnalysisResult",
    "Confidence",
    "CostEstimate",
    "DEFAULT_COST_INCREASE_THRESHOLD_PERCENT",
    "DEFAULT_GPU_HOURLY_PRICES",
    "FieldChange",
    "RiskWarning",
    "SUPPORTED_FIELDS",
    "TrainingConfig",
    "analyze_config_dicts",
    "analyze_config_files",
    "analyze_configs",
    "build_recommendations",
    "calculate_increase_percent",
    "compare_configs",
    "detect_warnings",
    "estimate_cost",
    "format_money",
    "format_money_pair",
    "generate_markdown_report",
    "load_config_file",
    "lookup_gpu_hourly_price",
    "normalize_training_config",
    "parse_config_text",
    "parse_python_config_text",
    "parse_yaml_text",
]
