# Config reference

One file describes one training experiment. Exact canonical keys are matched case-insensitively.
Nested mapping paths are retained in the report. No framework runtime or configuration library is executed.

| Fields | Accepted values |
| --- | --- |
| epochs, max_epochs | Positive finite numbers, including partial epochs such as 2.9 |
| batch_size, global_batch_size, gpu_count, dataset_size | Positive finite integers; fractions are rejected |
| estimated_minutes_per_epoch | Positive finite number |
| budget_limit_usd | Finite number greater than or equal to zero |
| model, model_name, gpu_type, precision | Non-empty scalar labels; mappings and lists are rejected |
| mixed_precision | Boolean, or true/false, yes/no, y/n, on/off, enabled/disabled, 1/0 |

Missing or null fields remain missing. Invalid values are not replaced with defaults.
Both epoch aliases must agree when present. global_batch_size takes precedence over batch_size because they describe different quantities.
Duplicate canonical fields may occur at multiple paths only when their normalized values agree.
Training fields inside lists are rejected to avoid mixing experiments. Harmless metadata lists are accepted.

## Formats

- YAML uses PyYAML==6.0.3 SafeLoader with duplicate-key, depth, node-count, and cycle checks. Merge keys are rejected.
- JSON requires an object, rejects duplicate keys, and validates numerical field values after parsing.
- Python accepts named literal assignments and literal dictionaries. Imports are ignored and never executed.
  Expressions, function calls, attribute assignments, and repeated names are rejected.

Files are limited to 1,000,000 UTF-8 bytes. Config depth is limited to 25 and traversed nodes to 10,000.
Git blobs are size-checked before loading. Parsing diagnostics contain no raw input lines.

## Missing inputs and prices

Missing cost inputs use epochs=1, GPU count=1, minutes/epoch=30, and unknown GPU price=$1/hour.
Every default is listed. These assumptions can understate or overstate cost.
Unknown GPU labels are not mapped to cloud instances. Price overrides use a normalized label match.
Built-in labels: T4, L4, A10, A10G, V100, A100, A100 40GB, A100 80GB, H100, H200.
The table contains illustrative rates without provider or region provenance.

## Security boundary

Sensitive-key subtrees and values matching known credential patterns are excluded before normalization.
This is defense in depth, not a complete secret scanner. Never commit credentials.
Output values are escaped for Markdown. Errors omit input values even when syntax is invalid.

## Unsupported automatic detection

num_train_epochs, per_device_train_batch_size, devices, num_nodes, bf16, and fp16 are not translated in this beta.
Hydra interpolation, Python evaluation, cloud instance lookup, automatic GPU probing, and runtime prediction are unsupported.
Use canonical fields or prepare one resolved, literal config per experiment.
