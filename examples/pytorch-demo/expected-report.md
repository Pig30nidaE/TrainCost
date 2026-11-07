## TrainCost CI Report

Cost risk detected.

### Changed

- epochs: 5 -> 50
- batch_size: 64 -> 8
- precision: bf16 -> fp32
- mixed_precision: True -> False
- gpu_type: T4 -> A100
- gpu_count: 1 -> 2
- estimated_minutes_per_epoch: 1.5 -> 4

### Estimated cost

- Base branch: $0.04
- This PR: $21.33
- Increase: +48,662%
- GPU price: Base T4 at $0.35/hour (from the gpu-prices input); PR A100 at $3.20/hour (from the gpu-prices input)

### Warnings

- Budget limit exceeded: Estimated PR cost is $21.33, above the $5.00 budget. The run may spend more than the configured experiment budget. Reduce epochs, GPU count, runtime per epoch, or choose a lower-cost GPU.
- Estimated cost increased by more than 50%: Estimated cost changed from $0.04 to $21.33 \(\+48,662%\). Large cost increases are easy to miss in config review. Confirm that the larger training run is required before merge.
- Epoch count increased significantly: Epoch count changed from 5 to 50. Training cost usually scales linearly with epochs. Use fewer epochs, early stopping, or a staged run before full training.
- GPU type changed to a more expensive option: GPU type changed from T4 \($0.35/hour\) to A100 \($3.20/hour\). Higher hourly GPU prices raise total training cost even if runtime stays flat. Use the smaller GPU when it meets memory and throughput needs.
- GPU count increased: GPU count changed from 1 to 2. The estimate multiplies runtime by GPU count. Use fewer GPUs or shorten the run when multi-GPU training is not required.
- Mixed precision appears disabled: precision changed from bf16 to fp32; mixed\_precision changed from True to False. fp32 or disabled mixed precision can increase memory use and runtime. Use bf16/fp16 mixed precision when the model and hardware support it.
- Batch size is unusually small: Batch size is 8. Very small batches can reduce GPU utilization and extend runtime. Measure GPU utilization with a dry run and increase the batch size if GPU memory allows.

### Recommendations

- Run a short dry run before launching the full training job.
- Reduce the planned run or raise \`budget\_limit\_usd\` only if the spend is intentional.
- Run a short dry run and confirm the expected cost increase is acceptable.
- Confirm the higher epoch count is needed or run a smaller validation job first.
- Confirm the more expensive GPU is required for memory, speed, or availability.
- Confirm the additional GPUs improve throughput enough to justify the cost.
- Re-enable mixed precision if it is safe for this training job.
- Check GPU utilization and consider a larger batch that fits in memory.

### Confidence

- High.
- Reason: Epoch count, GPU type, GPU count, and estimated minutes per epoch were provided.
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
- PR config file: examples/pytorch-demo/configs/risky-config.yaml.
- PR applied: epochs=50, minutes/epoch=4, GPU count=2.
- PR model_name: resnet50-large; source: model\_name.
- PR epochs: 50; source: epochs.
- PR batch_size: 8; source: batch\_size.
- PR precision: fp32; source: precision.
- PR mixed_precision: False; source: mixed\_precision.
- PR gpu_type: A100; source: gpu\_type.
- PR gpu_count: 2; source: gpu\_count.
- PR estimated_minutes_per_epoch: 4; source: estimated\_minutes\_per\_epoch.
- PR budget_limit_usd: 5; source: budget\_limit\_usd.
- PR defaulted fields: none.
- Runtime per epoch is supplied or assumed; GPU scaling speedups are not modeled.
