# TrainCost CI Demo Script

## Demo Goal

Show that TrainCost CI catches a risky ML training config change in a pull request before the expensive training job runs.

The demo should be understandable without knowing the implementation. The story is:

> A developer changes `config.yaml` from a cheap experiment to a much larger run. TrainCost CI compares the base branch and PR config, estimates the likely cost increase, and leaves a clear PR comment.

## Repository Setup

Use `examples/pytorch-demo` as the demo repository.

The demo should contain:

- a baseline config fixture
- a risky pull request config fixture
- a GitHub Actions workflow that runs TrainCost CI on pull requests
- an expected Markdown report

No real PyTorch training job is required for the MVP demo. The value is the PR cost review.

In this repository, the local dry-run fixtures are:

- `examples/pytorch-demo/config.yaml` - canonical live PR path, initially containing the base config
- `examples/pytorch-demo/configs/base-config.yaml`
- `examples/pytorch-demo/configs/risky-config.yaml`
- `examples/pytorch-demo/expected-report.md`

For a live pull request demo, keep the base config at `examples/pytorch-demo/config.yaml` on the base branch, then replace that same file with the risky config contents on the PR branch.

## Base Branch Config

The base branch represents a cheap test run:

```yaml
model_name: resnet50-large
epochs: 5
batch_size: 64
precision: bf16
mixed_precision: true
gpu_type: T4
gpu_count: 1
estimated_minutes_per_epoch: 1.5
budget_limit_usd: 5.00
```

Estimated cost:

```text
5 epochs * 1.5 minutes = 7.5 minutes
7.5 / 60 * 1 GPU = 0.125 GPU-hours
0.125 GPU-hours * $0.35 per T4 GPU-hour = $0.04
```

## Pull Request Config

The pull request represents an expensive training run:

```yaml
model_name: resnet50-large
epochs: 50
batch_size: 8
precision: fp32
mixed_precision: false
gpu_type: A100
gpu_count: 2
estimated_minutes_per_epoch: 4
budget_limit_usd: 5.00
```

Estimated cost:

```text
50 epochs * 4 minutes = 200 minutes
200 / 60 * 2 GPUs = 6.67 GPU-hours
6.67 GPU-hours * $3.20 per A100 GPU-hour = $21.33
```

## Pull Request Story

1. Create a branch named `expensive-training-config`.
2. Replace `examples/pytorch-demo/config.yaml` with the values from `examples/pytorch-demo/configs/risky-config.yaml`.
3. Open a pull request.
4. GitHub Actions runs TrainCost CI.
5. TrainCost CI detects that `config.yaml` changed.
6. TrainCost CI compares base and PR values.
7. TrainCost CI posts or prepares a Markdown report.

## Expected PR Comment

```markdown
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
```

## Narration

Suggested demo narration:

1. "This repository starts with a cheap training config: 5 epochs on one T4."
2. "The pull request changes the run to 50 epochs on two A100 GPUs, disables mixed precision, and lowers batch size."
3. "TrainCost CI runs during code review, before the training job runs."
4. "The comment does not claim an exact bill. It gives a risk signal based on the provided config."
5. "The reviewer can now ask whether the expensive run is intentional or request a smaller dry run first."

## Demo Success Criteria

The demo succeeds when a viewer can see:

- the exact config fields that changed
- the estimated base cost
- the estimated PR cost
- the cost increase percentage
- budget and efficiency warnings
- recommendations that help reduce risk

## Out of Scope for the Demo

Do not include:

- a dashboard
- Kubernetes setup
- cloud account setup
- MLflow, W&B, Comet, OpenCost, or Kubecost integration
- real GPU job execution
- claims that the estimate is exact
