# TrainCost CI MVP Product Spec

## Positioning

TrainCost CI is **Infracost for ML experiments**.

It is a lightweight GitHub Action that reviews machine learning training configuration changes in pull requests and produces a cost risk report before expensive experiments run.

TrainCost CI should help small ML teams, students, research labs, and individual developers answer one question during code review:

> Did this PR make training meaningfully more expensive or less efficient?

## Product Goals

The MVP should:

1. Run inside GitHub Actions on pull requests.
2. Detect changed ML training config files.
3. Extract common training and cost fields from YAML, JSON, and simple Python config files.
4. Compare the base branch config with the PR branch config.
5. Estimate GPU cost using a transparent formula.
6. Detect budget and efficiency risks using deterministic rules.
7. Generate a concise Markdown report suitable for a PR comment.
8. Work without a backend server or external code upload.

## Non-Goals

The MVP must not become:

- A Kubernetes scheduler.
- A GPU provisioning system.
- A full cloud cost management platform.
- A training optimizer.
- An experiment tracking product.
- A dashboard-first product.
- A replacement for MLflow, W&B, Comet, OpenCost, Kubecost, or Infracost.
- A system that claims exact GPU cost prediction.

## Target Users

Primary users:

1. Individual ML developers using paid GPUs.
2. Students and research labs sharing limited GPU budgets.
3. Small AI/ML teams using GitHub pull requests for review.
4. Early-stage startups that need lightweight budget guardrails.

The first version should be understandable and useful without enterprise setup.

## Core Workflow

1. A pull request changes an ML training config file.
2. The GitHub Action runs on the PR.
3. TrainCost CI identifies changed config files from the PR diff.
4. For each relevant config, TrainCost CI loads the base branch version and the PR branch version.
5. The core engine extracts supported fields from both versions.
6. The core engine estimates base cost and PR cost.
7. The risk engine detects warnings such as budget exceeded, cost increase, GPU upgrade, and precision regression.
8. TrainCost CI generates a Markdown report.
9. The GitHub Action posts or prepares the report as PR review output.

## Supported Inputs

The GitHub Action should support:

- `config-path`: path or glob pattern for config files to inspect.
- `gpu-prices`: optional comma-separated GPU hourly price overrides.
- `budget-limit`: optional default budget limit when the config does not define one.
- `comment-mode`: whether to write only a report or also post/update a PR comment.
- `report-path`: path for the generated Markdown report.

The core package should support these config file types first:

- YAML: `.yaml`, `.yml`
- JSON: `.json`
- Simple Python config files: `.py` files with literal assignments or simple dictionaries

## Supported Fields

The MVP should attempt to extract:

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

Aliases should be kept conservative. For example, `max_epochs` can be treated as the epoch count when `epochs` is absent.

## Estimation Model

The MVP should use a transparent formula:

```text
estimated_total_minutes = epochs * estimated_minutes_per_epoch
estimated_gpu_hours = estimated_total_minutes / 60 * gpu_count
estimated_cost_usd = estimated_gpu_hours * gpu_hourly_price
```

The report must use language such as:

- estimated cost
- likely increase
- risk signal
- confidence: low / medium / high
- based on provided config values

The report must avoid language such as:

- exact cost
- guaranteed savings
- optimal GPU
- precise runtime

## Confidence Rules

Use confidence to communicate estimate quality:

- High: epoch count, GPU type, GPU count, and estimated minutes per epoch are present.
- Medium: most required fields are present, but runtime or price assumptions are partly defaulted.
- Low: important fields are missing and conservative defaults were used.

Low confidence should not suppress the report. Missing fields are themselves useful review signals.

## Initial Risk Rules

Warn when:

1. Estimated PR cost exceeds `budget_limit_usd`.
2. Estimated PR cost increases by more than 50% compared with the base branch.
3. `epochs` or `max_epochs` increases significantly.
4. `gpu_type` changes to a more expensive GPU type.
5. `gpu_count` increases.
6. `precision` is `fp32` and mixed precision is not enabled.
7. Batch size is unusually small for a large model.
8. Required cost fields are missing and confidence is low.

Each warning should explain:

- What changed.
- Why it matters.
- How to reduce risk.

## Markdown Report Requirements

The report should include:

1. Status: cost risk detected, no major cost risk detected, or low-confidence estimate.
2. Changed fields.
3. Estimated base branch cost.
4. Estimated PR branch cost.
5. Percentage increase or decrease when available.
6. Warnings.
7. Recommendations.
8. Confidence and reason.

The report should be short enough to read during code review.

## Proposed Repository Boundaries

`packages/core` owns deterministic analysis:

- config parsing
- normalized training config model
- base vs PR comparison
- GPU cost estimation
- risk rules
- Markdown report generation

`packages/github-action` owns GitHub-specific behavior:

- pull request context
- changed file detection
- loading base and head versions
- invoking the core package
- writing report output
- posting or preparing the PR comment

`examples/pytorch-demo` owns the demo:

- baseline config
- risky PR config
- expected report output
- simple README explaining the scenario

## Security and Privacy

TrainCost CI should run locally in the GitHub Actions runner.

The MVP must not:

- send repository source code to external services
- require cloud provider credentials
- require API keys beyond the GitHub token needed for PR comments
- print secrets or environment variables in logs

If config files appear to contain secrets, TrainCost CI should ignore the sensitive value and warn that secrets should not be stored in training config.

## Acceptance Criteria

The MVP is complete when:

1. A user can install the GitHub Action in a demo repo.
2. A pull request changing `config.yaml` triggers TrainCost CI.
3. The action compares base and PR config values.
4. The core engine estimates base and PR cost.
5. The risk engine detects budget, cost increase, GPU, precision, and missing-field risks.
6. The action generates a readable Markdown report.
7. The demo clearly shows a cheap run becoming expensive and being caught before merge.
8. The README includes installation, example output, supported fields, limitations, and roadmap.
