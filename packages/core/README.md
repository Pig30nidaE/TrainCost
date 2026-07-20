# TrainCost CI Core

Python package for TrainCost CI's deterministic analysis logic.

This package owns:

- YAML and JSON training config parsing.
- Supported field normalization.
- Base vs PR config comparison.
- GPU cost estimation.
- Rule-based risk warning detection.
- Markdown report generation.

Primary entry points:

- `analyze_config_files(base_path, pr_path)`
- `analyze_config_dicts(base_config, pr_config)`
- `load_config_file(path)`
- `estimate_cost(config)`

The MVP intentionally does not depend on GitHub APIs, a backend server, or model-specific runtime prediction. YAML support is dependency-free and scoped to common config mappings.
