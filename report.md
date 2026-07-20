## TrainCost CI Report

Cost risk detected.

### Changed

- epochs: 5 -> 50
- batch_size: 64 -> 8
- precision: bf16 -> fp32
- mixed_precision: True -> False
- gpu_type: T4 -> A100
- gpu_count: 1 -> 2
- estimated_minutes_per_epoch: 1.5 -> 4.0

### Estimated cost

- Base branch: $0.04
- This PR: $21.33
- Increase: +48,662%

### Warnings

- Budget limit exceeded: Estimated PR cost is $21.33, above the $5.00 budget. The run may spend more than the configured experiment budget. Reduce epochs, GPU count, runtime per epoch, or choose a lower-cost GPU.
- Estimated cost increased by more than 50%: Estimated cost changed from $0.04 to $21.33 (+48,662%). Large cost increases are easy to miss in config review. Confirm that the larger training run is required before merge.
- Epoch count increased significantly: Epoch count changed from 5 to 50. Training cost usually scales linearly with epochs. Use fewer epochs, early stopping, or a staged run before full training.
- GPU type changed to a more expensive option: GPU type changed from T4 ($0.35/hour) to A100 ($3.20/hour). Higher hourly GPU prices raise total training cost even if runtime stays flat. Use the smaller GPU when it meets memory and throughput needs.
- GPU count increased: GPU count changed from 1 to 2. The estimate multiplies runtime by GPU count. Use fewer GPUs or shorten the run when multi-GPU training is not required.
- Mixed precision appears disabled: precision changed from bf16 to fp32; mixed_precision changed from True to False. fp32 or disabled mixed precision can increase memory use and runtime. Use bf16/fp16 mixed precision when the model and hardware support it.
- Batch size is unusually small: Batch size is 8. Very small batches can reduce GPU utilization and extend runtime. Increase batch size, use gradient accumulation, or validate utilization with a dry run.

### Recommendations

- Run a short dry run before launching the full training job.
- Reduce the planned run or raise `budget_limit_usd` only if the spend is intentional.
- Run a short dry run and confirm the expected cost increase is acceptable.
- Confirm the higher epoch count is needed or run a smaller validation job first.
- Confirm the more expensive GPU is required for memory, speed, or availability.
- Confirm the additional GPUs improve throughput enough to justify the cost.
- Re-enable mixed precision if it is safe for this training job.
- Check GPU utilization and consider a larger effective batch size.

### Confidence

- High.
- Reason: Epoch count, GPU type, GPU count, and estimated minutes per epoch were provided.
