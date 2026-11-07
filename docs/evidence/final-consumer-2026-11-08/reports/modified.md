## TrainCost CI Report

Config: `examples/huggingface-demo/config.json`.

Cost risk detected.

### Changed

- epochs: 1 -> 3

### Estimated cost

- Merge-base estimate: $0.10
- PR-head estimate: $0.30
- Increase: +200%
- GPU price: Base RTX3060 at $1.00/hour (from the gpu-prices input); PR RTX3060 at $1.00/hour (from the gpu-prices input)

### Warnings

- Budget limit exceeded: Estimated PR cost is $0.30, above the $0.20 budget. The run may spend more than the configured experiment budget. Reduce epochs, GPU count, runtime per epoch, or choose a lower-cost GPU.
- Estimated cost increased by more than 50%: Estimated cost changed from $0.10 to $0.30 \(\+200%\). Large cost increases are easy to miss in config review. Confirm that the larger training run is required before merge.
- Epoch count increased significantly: Epoch count changed from 1 to 3. Training cost usually scales linearly with epochs. Use fewer epochs, early stopping, or a staged run before full training.
- Mixed precision appears disabled: precision is fp32; mixed\_precision is disabled. fp32 or disabled mixed precision can increase memory use and runtime. Use bf16/fp16 mixed precision when the model and hardware support it.

### Recommendations

- Run a short dry run before launching the full training job.
- Reduce the planned run or raise \`budget\_limit\_usd\` only if the spend is intentional.
- Run a short dry run and confirm the expected cost increase is acceptable.
- Confirm the higher epoch count is needed or run a smaller validation job first.
- Re-enable mixed precision if it is safe for this training job.

### Confidence

- High.
- Reason: Epoch count, GPU type, GPU count, and estimated minutes per epoch were provided.
- Confidence describes input completeness, not billing accuracy or measured runtime.

### Inputs and assumptions

- Base config file: examples/huggingface-demo/config.json.
- Base applied: epochs=1, minutes/epoch=6, GPU count=1.
- Base model_name: distilbert/distilbert-base-uncased; source: model\_name.
- Base epochs: 1; source: epochs.
- Base batch_size: 8; source: batch\_size.
- Base precision: fp32; source: precision.
- Base mixed_precision: False; source: mixed\_precision.
- Base gpu_type: RTX3060; source: gpu\_type.
- Base gpu_count: 1; source: gpu\_count.
- Base estimated_minutes_per_epoch: 6; source: estimated\_minutes\_per\_epoch.
- Base dataset_size: 1024; source: dataset\_size.
- Base budget_limit_usd: 0.2; source: budget\_limit\_usd.
- Base defaulted fields: none.
- PR config file: examples/huggingface-demo/config.json.
- PR applied: epochs=3, minutes/epoch=6, GPU count=1.
- PR model_name: distilbert/distilbert-base-uncased; source: model\_name.
- PR epochs: 3; source: epochs.
- PR batch_size: 8; source: batch\_size.
- PR precision: fp32; source: precision.
- PR mixed_precision: False; source: mixed\_precision.
- PR gpu_type: RTX3060; source: gpu\_type.
- PR gpu_count: 1; source: gpu\_count.
- PR estimated_minutes_per_epoch: 6; source: estimated\_minutes\_per\_epoch.
- PR dataset_size: 1024; source: dataset\_size.
- PR budget_limit_usd: 0.2; source: budget\_limit\_usd.
- PR defaulted fields: none.
- Runtime per epoch is supplied or assumed; GPU scaling speedups are not modeled.

### Action notes

- Comparison baseline: merge base bb0b5b974e7e702a9232ea3434dfb62da30b3c70.
