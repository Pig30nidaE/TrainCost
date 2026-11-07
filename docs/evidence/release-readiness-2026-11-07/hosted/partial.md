## TrainCost CI Report

Config: `examples/release-consumer/added.json`.

Low-confidence estimate.

### Changed

- model_name: not set -> distilbert/distilbert-base-uncased
- epochs: not set -> 3
- batch_size: not set -> 8
- global_batch_size: not set -> 8
- precision: not set -> bf16
- mixed_precision: not set -> True
- gpu_type: not set -> RTX3060
- gpu_count: not set -> 1
- estimated_minutes_per_epoch: not set -> 6
- budget_limit_usd: not set -> 0.2

### Estimated cost

- Base branch: $0.50
- This PR: $0.30
- Increase: -40.0%
- GPU price: Base unknown GPU at $1.00/hour (fallback default; set gpu_type or gpu-prices for a better estimate); PR RTX3060 at $1.00/hour (from the gpu-prices input)

### Warnings

- Budget limit exceeded: Estimated PR cost is $0.30, above the $0.20 budget. The run may spend more than the configured experiment budget. Reduce epochs, GPU count, runtime per epoch, or choose a lower-cost GPU.
- Missing fields reduce estimate confidence: Missing fields: epochs, estimated\_minutes\_per\_epoch, gpu\_count, gpu\_type. The estimate uses illustrative defaults that may understate or overstate actual cost. Add epochs, gpu\_type, gpu\_count, and estimated\_minutes\_per\_epoch to the config.

### Recommendations

- Run a short dry run before launching the full training job.
- Reduce the planned run or raise \`budget\_limit\_usd\` only if the spend is intentional.
- Add missing cost fields so future TrainCost CI reports are more useful.

### Confidence

- Low.
- Reason: Important cost fields are missing, so illustrative defaults were used: epochs, estimated_minutes_per_epoch, gpu_count, gpu_type.
- Confidence describes input completeness, not billing accuracy or measured runtime.

### Inputs and assumptions

- Base applied: epochs=1, minutes/epoch=30, GPU count=1.
- Base defaulted fields: epochs, estimated_minutes_per_epoch, gpu_count, gpu_hourly_price.
- PR config file: examples/release-consumer/added.json.
- PR applied: epochs=3, minutes/epoch=6, GPU count=1.
- PR model_name: distilbert/distilbert-base-uncased; source: model\_name.
- PR epochs: 3; source: num\_train\_epochs.
- PR batch_size: 8; source: per\_device\_train\_batch\_size.
- PR global_batch_size: 8; source: derived from micro batch, accumulation, and gpu\_count.
- PR precision: bf16; source: bf16.
- PR mixed_precision: True; source: bf16.
- PR gpu_type: RTX3060; source: gpu\_type.
- PR gpu_count: 1; source: gpu\_count.
- PR estimated_minutes_per_epoch: 6; source: estimated\_minutes\_per\_epoch.
- PR budget_limit_usd: 0.2; source: budget\_limit\_usd.
- PR defaulted fields: none.
- Runtime per epoch is supplied or assumed; GPU scaling speedups are not modeled.

### Action notes

- Added config: examples/release-consumer/added.json; no base file exists, so base defaults are illustrative.
- Skipped examples/release-consumer/invalid.json: Positive max\_steps overrides epochs; step-based runtime is unsupported.
- Excluded configs: 1. Costs cover analyzed configs only.
