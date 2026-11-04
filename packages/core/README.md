# TrainCost CI core

Deterministic parsing, normalization, comparison, estimation, risk rules, and Markdown generation.
Install the package with pip install ./packages/core. Python 3.11+ and PyYAML==6.0.3 are required.

Entry points: analyze_config_files, analyze_config_dicts, analyze_configs, load_config_file, estimate_cost.
TrainingConfig stores normalized canonical fields, safe sensitive-key paths, and field_sources.
Invalid configs raise value-free ConfigError, a ValueError subclass.
Fractional epochs are preserved; counts are positive integers.

No GitHub API, network call, backend, or training-code execution occurs in core.
See ../../docs/config_reference.md and ../../docs/architecture.md for contracts and decisions.
