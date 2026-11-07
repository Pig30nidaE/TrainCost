# TrainCost CI core

Deterministic parsing, normalization, comparison, estimation, risk rules, Markdown and versioned JSON.
Install the package with pip install ./packages/core. Python 3.11+ and PyYAML==6.0.3 are required.
The local CLI targets Linux and macOS. On Windows, use WSL2 Ubuntu; native Windows
output handling is not validated and can reject paths.

Entry points: analyze_config_files, analyze_config_dicts, analyze_configs, load_config_file, estimate_cost.
The installed `traincost-ci` command and `python -m traincost_ci_core` compare local
base/head files and write Markdown and JSON. For example:

```bash
traincost-ci --base-config base.yaml --head-config pr.yaml \
  --gpu-prices 'T4=0.35' --report-path report.md --json-path report.json
```

The default adapter is canonical. Use `--adapter huggingface` or the Python APIs'
`adapter="huggingface"` keyword for the explicit epoch-based TrainingArguments
subset. Positive max_steps and ambiguous or unsupported execution settings are
rejected. No Transformers dependency is required.

Known unmodeled runtime settings produce warnings without their values. If a
runtime-affecting input changes while minutes per epoch remains the same, the report
flags the estimate as potentially stale. Confidence reflects input completeness,
not observed runtime or billing accuracy. Markdown preserves positive subcent
amounts; the JSON document keeps unrounded numeric estimates.

TrainingConfig stores normalized canonical fields, safe sensitive-key paths, and field_sources.
Invalid configs raise value-free ConfigError, a ValueError subclass.
Fractional epochs are preserved; counts are positive integers.

No GitHub API, network call, backend, or training-code execution occurs in core.
See [config reference](../../docs/config_reference.md), [JSON contract](../../docs/json_report.md),
and [architecture](../../docs/architecture.md) for contracts and decisions.
