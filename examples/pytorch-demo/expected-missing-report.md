## TrainCost CI Report

Low-confidence estimate.

### Changed

- model_name: resnet50-large -> resnet50
- precision: bf16 -> not set
- mixed_precision: True -> not set
- gpu_type: T4 -> not set
- gpu_count: 1 -> not set
- estimated_minutes_per_epoch: 1.5 -> not set
- budget_limit_usd: 5 -> not set

### Estimated cost

- Base branch: $0.04
- This PR: $2.50
- Increase: +5,614%
- GPU price: Base T4 at $0.35/hour (from the gpu-prices input); PR unknown GPU at $1.00/hour (fallback default; set gpu_type or gpu-prices for a better estimate)

### Warnings

- Estimated cost increased by more than 50%: Estimated cost changed from $0.04 to $2.50 \(\+5,614%\). Large cost increases are easy to miss in config review. Confirm that the larger training run is required before merge.
- Missing fields reduce estimate confidence: Missing fields: estimated\_minutes\_per\_epoch, gpu\_count, gpu\_type. The estimate uses illustrative defaults that may understate or overstate actual cost. Add epochs, gpu\_type, gpu\_count, and estimated\_minutes\_per\_epoch to the config.

### Recommendations

- Run a short dry run before launching the full training job.
- Run a short dry run and confirm the expected cost increase is acceptable.
- Add missing cost fields so future TrainCost CI reports are more useful.

### Confidence

- Low.
- Reason: Important cost fields are missing, so illustrative defaults were used: estimated_minutes_per_epoch, gpu_count, gpu_type.
- Confidence describes input completeness, not billing accuracy or measured runtime.

### Inputs and assumptions

- Base config file: examples/pytorch-demo/configs/base-config.yaml.
- Base applied: epochs=5, minutes/epoch=1.5, GPU count=1.
- Base model_name: resnet50-large; source: model\_name.
- Base epochs: 5; source: epochs.
- Base batch_size: 64; source: batch\_size.
- Base precision: bf16; source: precision.
- Base mixed_precision: True; source: mixed\_precision.
- Base gpu_type: T4; source: gpu\_type.
- Base gpu_count: 1; source: gpu\_count.
- Base estimated_minutes_per_epoch: 1.5; source: estimated\_minutes\_per\_epoch.
- Base budget_limit_usd: 5; source: budget\_limit\_usd.
- Base defaulted fields: none.
- PR config file: examples/pytorch-demo/configs/missing-config.yaml.
- PR applied: epochs=5, minutes/epoch=30, GPU count=1.
- PR model_name: resnet50; source: model\_name.
- PR epochs: 5; source: epochs.
- PR batch_size: 64; source: batch\_size.
- PR defaulted fields: estimated_minutes_per_epoch, gpu_count, gpu_hourly_price.
- Runtime per epoch is supplied or assumed; GPU scaling speedups are not modeled.
