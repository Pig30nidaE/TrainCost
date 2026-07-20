# TrainCost CI

TrainCost CI is a lightweight GitHub Action that reviews ML training config changes in pull requests and reports estimated GPU cost risk.

It is positioned as **Infracost for ML experiments**: a PR-level cost review bot for training configuration changes, not a GPU scheduler or experiment tracking platform.

## Problem

Small changes to ML training config can turn a cheap experiment into an expensive run:

- `epochs` increases from 5 to 50.
- `gpu_type` changes from `T4` to `A100`.
- `gpu_count` doubles.
- mixed precision is disabled.
- batch size drops enough to reduce GPU utilization.

Teams often discover the cost only after the job has already run. TrainCost CI is meant to catch those changes during code review and provide a clear risk signal before merge.

## Example PR Comment

```markdown
## TrainCost CI Report

Cost risk detected.

### Changed

- epochs: 5 -> 50
- batch_size: 64 -> 8
- precision: bf16 -> fp32
- gpu_type: T4 -> A100
- gpu_count: 1 -> 2

### Estimated cost

- Base branch: $0.04
- This PR: $21.33
- Increase: +48,662%

### Warnings

- Budget limit exceeded: estimated $21.33 > $5.00.
- Estimated cost increased by more than 50% compared with the base branch.
- GPU type changed to a more expensive option.
- GPU count increased from 1 to 2.
- Mixed precision appears disabled; fp32 may increase runtime and memory use.
- Batch size is small and may reduce GPU utilization.

### Recommendations

- Run a short dry run before launching the full training job.
- Confirm that the larger GPU and higher epoch count are required.
- Re-enable mixed precision if the model supports it.
- Set or lower `budget_limit_usd` for this experiment.

### Confidence

Medium.

Reason: `estimated_minutes_per_epoch` was provided, but actual runtime and GPU utilization are unknown.
```

The report is an estimate, not an exact bill. It uses config values and simple rules to highlight risk.

## Quick Start

Add a workflow such as:


```yaml
name: TrainCost CI

on:
  pull_request:
    paths:
      - "**/*.yaml"
      - "**/*.yml"
      - "**/*.json"
      - "**/*.py"

jobs:
  traincost:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Review ML training cost
        uses: Pig30nidaE/TrainCost@v0.1.0
        with:
          config-path: "config.yaml"
          gpu-prices: "T4=0.35,A10G=1.2,A100=3.20"
          budget-limit: "5.00"
          comment-mode: "false"
          report-path: "report.md"
```

This example uses report-only mode and therefore needs only `contents: read`. Add `pull-requests: write` when enabling `comment-mode: "true"`.

Add cost-related fields to a training config:

```yaml
model_name: resnet50
epochs: 5
batch_size: 64
precision: bf16
mixed_precision: true
gpu_type: T4
gpu_count: 1
estimated_minutes_per_epoch: 1.5
budget_limit_usd: 5.00
```

When a pull request changes the config, TrainCost CI compares the base branch and PR values, estimates the cost impact, and generates a Markdown report for review.

See [docs/github_action_usage.md](docs/github_action_usage.md) for the full input reference and comment-mode behavior.

## Supported Config Fields

The MVP should extract these fields when present:

- `model`
- `model_name`
- `epochs`
- `max_epochs`
- `batch_size`
- `global_batch_size`
- `precision`
- `mixed_precision`
- `gpu_type`
- `gpu_count`
- `estimated_minutes_per_epoch`
- `dataset_size`
- `budget_limit_usd`

The first version will focus on YAML, JSON, and simple Python config files. It should prefer reliable parsing of common config shapes over broad but fragile framework support.

## MVP Scope

The first usable version is limited to:

- Running as a GitHub Action on pull requests.
- Detecting changed ML training config files.
- Comparing base branch config and PR branch config.
- Estimating GPU runtime and cost with simple formulas.
- Detecting budget and efficiency risks.
- Generating a concise Markdown PR report.

Cost estimation uses this basic model:

```text
estimated_total_minutes = epochs * estimated_minutes_per_epoch
estimated_gpu_hours = estimated_total_minutes / 60 * gpu_count
estimated_cost_usd = estimated_gpu_hours * gpu_hourly_price
```

If required fields are missing, the report should still be useful and mark confidence as low.

## Limitations

- Estimates are approximate and based on config values.
- TrainCost CI does not measure real GPU utilization.
- TrainCost CI does not know the exact cloud bill for a run.
- Missing or stale `estimated_minutes_per_epoch` values reduce confidence.
- The MVP is rule-based and deterministic; it does not use AI to predict runtime.
- The MVP is not a scheduler, optimizer, dashboard, or experiment tracker.
- The MVP does not integrate with Kubernetes, MLflow, W&B, Comet, OpenCost, or Kubecost.

## Roadmap

1. Define the MVP product scope, demo, and acceptance checklist.
2. Implement the Python core package for parsing, comparison, estimation, risk rules, and Markdown report generation.
3. Add focused tests for YAML, JSON, simple Python config parsing, estimation, risk rules, confidence, and report output.
4. Implement the GitHub Action wrapper for pull request diffs and report output.
5. Build the PyTorch demo scenario showing an expensive config change caught in a PR.
6. Polish installation docs, example output, and GitHub Marketplace readiness after the PR workflow works.
