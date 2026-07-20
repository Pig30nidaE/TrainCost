# AGENTS.md

## Project Name

TrainCost CI

## Project Summary

TrainCost CI is a GitHub Action that reviews machine learning training changes in Pull Requests and warns when the change may increase GPU cost, exceed a budget limit, or introduce inefficient training settings.

This project should be positioned as:

> Infracost for ML experiments.

The goal is not to build a full GPU scheduler, Kubernetes platform, or experiment tracking SaaS. The first MVP should focus on PR-level cost review for ML training configuration changes.

## Core Problem

Small changes in ML training code or config can greatly increase GPU runtime and cloud cost. Many teams only discover this after the experiment has already run.

TrainCost CI should catch risky changes earlier by analyzing Pull Request diffs and posting a clear cost review comment.

## Target Users

Primary users:

1. Individual ML developers using paid GPUs.
2. Students and research labs sharing limited GPU resources.
3. Small AI/ML teams that use GitHub for code review.
4. Early-stage startups that need lightweight GPU budget guardrails.

Avoid designing for large enterprises first. Keep the MVP lightweight, installable, and easy to understand.

## Product Positioning

TrainCost CI is:

* A lightweight GitHub Action.
* A PR-level ML experiment cost review bot.
* A config diff based GPU cost risk detector.
* A budget guardrail for small ML teams.
* A developer-experience tool for MLOps and FinOps.

TrainCost CI is not:

* A Kubernetes scheduler.
* A replacement for Kubecost, OpenCost, W&B, Comet, or MLflow.
* A full cloud cost management platform.
* A model training optimizer.
* A guaranteed exact GPU cost predictor.

## MVP Scope

The first usable version must support:

1. Running as a GitHub Action on Pull Requests.
2. Detecting changed ML config files.
3. Parsing common training fields from YAML, JSON, and simple Python config files.
4. Comparing base branch config and PR branch config.
5. Estimating GPU runtime and cost using simple configurable rules.
6. Detecting risky changes.
7. Generating a Markdown report.
8. Posting or preparing a PR comment.
9. Providing a demo repository that clearly shows the value.

## Supported Config Fields

The MVP should try to extract the following fields when present:

* model
* model_name
* epochs
* max_epochs
* batch_size
* global_batch_size
* precision
* mixed_precision
* gpu_type
* gpu_count
* estimated_minutes_per_epoch
* dataset_size
* budget_limit_usd

Do not over-engineer parsing in the first version. Prefer reliable support for a few common formats over fragile support for everything.

## Initial Risk Rules

Implement simple rule-based analysis first.

Warn when:

1. Estimated cost exceeds budget limit.
2. Estimated cost increases by more than 50 percent compared with the base branch.
3. Epochs increase significantly.
4. GPU type changes to a more expensive GPU.
5. GPU count increases.
6. Precision is fp32 and mixed precision is not enabled.
7. Batch size is unusually small for a large model.
8. Required cost fields are missing and estimation confidence is low.

Every warning should include:

* What changed.
* Why it matters.
* How to reduce risk.

## Estimation Philosophy

Do not claim perfect cost prediction.

Use language such as:

* estimated cost
* risk signal
* likely increase
* confidence: low / medium / high
* based on provided config values

Avoid language such as:

* exact cost
* guaranteed savings
* optimal GPU
* precise runtime

The first version may use a simple formula:

estimated_total_minutes = epochs × estimated_minutes_per_epoch

estimated_gpu_hours = estimated_total_minutes / 60 × gpu_count

estimated_cost_usd = estimated_gpu_hours × gpu_hourly_price

If estimated_minutes_per_epoch is missing, use conservative defaults and mark confidence as low.

## Expected PR Comment Format

The generated report should be concise and useful.

Example:

TrainCost CI Report

Cost risk detected.

Changed:

* epochs: 5 → 50
* batch_size: 64 → 8
* precision: bf16 → fp32
* gpu_type: T4 → A100

Estimated cost:

* Base branch: $0.23
* This PR: $26.67
* Increase: +11,495%

Warnings:

* Budget limit exceeded: $26.67 > $5.00
* Mixed precision is disabled
* Batch size is small and may reduce GPU utilization
* Run a 10-minute dry run before full training

Confidence:

* Medium
* Reason: estimated_minutes_per_epoch was provided, but actual GPU utilization is unknown.

## Suggested Repository Architecture

Prefer this structure unless there is a strong reason to change it:

packages/core/

* Cost estimation logic
* Config parsing
* Diff comparison
* Risk rule engine
* Markdown report generation

packages/github-action/

* GitHub Action entrypoint
* Pull Request file detection
* Base branch / head branch comparison
* Comment posting or report output

packages/dashboard/

* Optional later feature
* Not required for MVP

examples/pytorch-demo/

* Minimal PyTorch-like training repo
* Example config files
* Example PR scenario

docs/

* Product spec
* Architecture notes
* Testing strategy
* Demo script

## Engineering Principles

1. Keep the first version small and shippable.
2. Prefer deterministic logic over premature AI features.
3. Write tests for parsing, estimation, and rule detection.
4. Separate core logic from GitHub-specific logic.
5. Make the tool usable without a backend server.
6. Do not require users to upload source code to an external API.
7. Keep all sensitive analysis local to the GitHub Action runner.
8. Fail gracefully when config fields are missing.
9. Produce a useful report even when confidence is low.
10. Make the demo impressive and easy to understand.

## Security and Privacy Rules

Do not send repository code to external services.

Do not require API keys except for GitHub-provided tokens or optional integrations.

Never print secrets, environment variables, GitHub tokens, or cloud credentials in logs.

If a config file contains suspicious sensitive values, ignore the value and warn that secrets should not be stored in training config.

## Testing Requirements

For any meaningful code change, add or update tests.

Minimum test areas:

1. YAML config parsing.
2. JSON config parsing.
3. Python config parsing when supported.
4. Cost estimation formula.
5. Budget exceeded warning.
6. Cost increase warning.
7. Precision warning.
8. Missing field / low confidence behavior.
9. Markdown report generation.
10. GitHub Action dry-run output.

Before considering a task complete, run the relevant tests and report the result.

## MVP Done Definition

The MVP is done when:

1. A user can install the GitHub Action in a demo repo.
2. A Pull Request changing config.yaml triggers the action.
3. The action compares base and PR config.
4. The action generates a readable Markdown cost report.
5. The report shows estimated base cost, PR cost, increase percentage, warnings, and recommendations.
6. The demo clearly shows a risky ML training change being caught before merge.
7. README includes installation, example output, and a demo GIF or screenshot placeholder.

## Do Not Do Yet

Do not build a full dashboard before the GitHub Action works.

Do not add Kubernetes integration in the first MVP.

Do not add MLflow, W&B, or OpenCost integration until the core PR workflow works.

Do not implement complex model-specific runtime prediction in the first version.

Do not spend time supporting every ML framework.

Do not over-focus on UI before the PR comment experience is excellent.

## Preferred Tech Stack

Use TypeScript or Python for the GitHub Action, but keep the core logic easy to test.

Recommended options:

Option A:

* TypeScript GitHub Action
* Node.js package for parser and report generation
* Jest or Vitest for tests

Option B:

* Python CLI core
* Composite GitHub Action
* Pytest for tests

Choose one stack and keep it consistent.

For this project, prefer Python if the first goal is fast ML-config parsing and experimentation. Prefer TypeScript if the first goal is polished GitHub Action distribution.

## Communication Style

When making changes, summarize:

1. What changed.
2. Why it changed.
3. How it was tested.
4. What remains risky or incomplete.

Avoid vague summaries. Be specific.

## Commit Style

Use clear commit messages:

* feat: add YAML config parser
* feat: estimate GPU training cost
* feat: generate PR markdown report
* test: add cost estimation cases
* docs: add quick start guide
* fix: handle missing budget limit

## Roadmap

Phase 1:

* GitHub Action MVP
* Config parser
* Cost estimation
* PR report
* Demo repo

Phase 2:

* MLflow baseline integration
* Historical runtime estimation
* Better model-size heuristics
* GitHub Marketplace polish

Phase 3:

* Optional dashboard
* W&B / Comet integration
* OpenCost / Kubernetes integration
* Slack notifications
