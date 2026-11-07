## TrainCost CI Report

Cost risk detected.

### Changed

- epochs: 1 -> 3

### Estimated cost

- Base branch: $0.0016408060416668174
- This PR: $0.004922418125000452
- Increase: +200%
- GPU price: Base APPLE\_M1\_MPS at $1.00/hour (from the gpu-prices input); PR APPLE\_M1\_MPS at $1.00/hour (from the gpu-prices input)

### Warnings

- Budget limit exceeded: Estimated PR cost is $0.004922418125000452, above the $0.003281612083333635 budget. The run may spend more than the configured experiment budget. Reduce epochs, GPU count, runtime per epoch, or choose a lower-cost GPU.
- Estimated cost increased by more than 50%: Estimated cost changed from $0.0016408060416668174 to $0.004922418125000452 \(\+200%\). Large cost increases are easy to miss in config review. Confirm that the larger training run is required before merge.
- Epoch count increased significantly: Epoch count changed from 1 to 3. Training cost usually scales linearly with epochs. Use fewer epochs, early stopping, or a staged run before full training.
- Mixed precision appears disabled: precision is fp32; mixed\_precision is disabled. fp32 or disabled mixed precision can increase memory use and runtime. Use bf16/fp16 mixed precision when the model and hardware support it.
- Training settings are not modeled: Detected settings: dataloader\_num\_workers, optim. These settings may affect training runtime but are not included in the cost formula. Measure runtime with these settings and update estimated\_minutes\_per\_epoch.

### Recommendations

- Run a short dry run before launching the full training job.
- Reduce the planned run or raise \`budget\_limit\_usd\` only if the spend is intentional.
- Run a short dry run and confirm the expected cost increase is acceptable.
- Confirm the higher epoch count is needed or run a smaller validation job first.
- Re-enable mixed precision if it is safe for this training job.
- Review unsupported settings and provide a measured runtime per epoch.

### Confidence

- High.
- Reason: Epoch count, GPU type, GPU count, and estimated minutes per epoch were provided. Some training settings are not modeled by this estimate.
- Confidence describes input completeness, not billing accuracy or measured runtime.

### Inputs and assumptions

- Base config file: measured-base.json.
- Base applied: epochs=1, minutes/epoch=0.0984484, GPU count=1.
- Base model_name: distilbert/distilbert-base-uncased; source: model\_name.
- Base epochs: 1; source: training\_args.num\_train\_epochs.
- Base batch_size: 8; source: training\_args.per\_device\_train\_batch\_size.
- Base global_batch_size: 8; source: derived from micro batch, accumulation, and gpu\_count.
- Base precision: fp32; source: precision.
- Base mixed_precision: False; source: training\_args.bf16.
- Base gpu_type: APPLE\_M1\_MPS; source: gpu\_type.
- Base gpu_count: 1; source: gpu\_count.
- Base estimated_minutes_per_epoch: 0.0984484; source: estimated\_minutes\_per\_epoch.
- Base dataset_size: 64; source: dataset\_size.
- Base budget_limit_usd: 0.00328161; source: budget\_limit\_usd.
- Base defaulted fields: none.
- PR config file: measured-pr.json.
- PR applied: epochs=3, minutes/epoch=0.0984484, GPU count=1.
- PR model_name: distilbert/distilbert-base-uncased; source: model\_name.
- PR epochs: 3; source: training\_args.num\_train\_epochs.
- PR batch_size: 8; source: training\_args.per\_device\_train\_batch\_size.
- PR global_batch_size: 8; source: derived from micro batch, accumulation, and gpu\_count.
- PR precision: fp32; source: precision.
- PR mixed_precision: False; source: training\_args.bf16.
- PR gpu_type: APPLE\_M1\_MPS; source: gpu\_type.
- PR gpu_count: 1; source: gpu\_count.
- PR estimated_minutes_per_epoch: 0.0984484; source: estimated\_minutes\_per\_epoch.
- PR dataset_size: 64; source: dataset\_size.
- PR budget_limit_usd: 0.00328161; source: budget\_limit\_usd.
- PR defaulted fields: none.
- Runtime per epoch is supplied or assumed; GPU scaling speedups are not modeled.
