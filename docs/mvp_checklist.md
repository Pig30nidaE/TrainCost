# TrainCost CI MVP Checklist

## Product Definition

- [x] Position TrainCost CI as Infracost for ML experiments.
- [x] Limit the MVP to PR-level ML training config review.
- [x] Define supported fields for the first version.
- [x] Define initial cost estimation formula.
- [x] Define initial risk rules.
- [x] Define the demo scenario.
- [x] Document intentional non-goals.

## Core Package

- [ ] Parse YAML training configs.
- [ ] Parse JSON training configs.
- [ ] Parse simple Python training configs.
- [ ] Normalize supported fields into one internal config model.
- [ ] Compare base branch and PR branch config values.
- [ ] Estimate total minutes, GPU-hours, and cost.
- [ ] Apply configurable GPU hourly prices.
- [ ] Detect budget exceeded risk.
- [ ] Detect cost increase over 50%.
- [ ] Detect significant epoch increases.
- [ ] Detect GPU type changes to more expensive GPU types.
- [ ] Detect GPU count increases.
- [ ] Detect fp32 without mixed precision.
- [ ] Detect unusually small batch size risk.
- [ ] Detect missing required fields and low-confidence estimates.
- [ ] Generate a concise Markdown report.

## GitHub Action

- [ ] Run on `pull_request` events.
- [ ] Detect changed files matching configured config globs.
- [ ] Load base branch and PR branch versions of changed config files.
- [ ] Invoke the core package for each relevant config change.
- [ ] Write the Markdown report to an output file.
- [ ] Expose the report path as an action output.
- [ ] Post or prepare a PR comment.
- [ ] Fail gracefully when no supported config files changed.
- [ ] Avoid printing secrets, tokens, or environment variables.

## Demo

- [ ] Add `examples/pytorch-demo/config.yaml` with the cheap baseline config.
- [ ] Add a documented risky PR config change.
- [ ] Add an example workflow invoking TrainCost CI.
- [ ] Add expected report output.
- [ ] Add a screenshot or GIF placeholder in the README after the action works.

## Tests

- [ ] YAML config parsing.
- [ ] JSON config parsing.
- [ ] Python config parsing.
- [ ] Cost estimation formula.
- [ ] Budget exceeded warning.
- [ ] Cost increase warning.
- [ ] GPU type and GPU count warnings.
- [ ] Precision warning.
- [ ] Missing field and low-confidence behavior.
- [ ] Markdown report generation.
- [ ] GitHub Action dry-run output.

## Documentation

- [x] README includes one-line description.
- [x] README includes problem statement.
- [x] README includes example PR comment.
- [x] README includes Quick Start.
- [x] README includes supported config fields.
- [x] README includes limitations.
- [x] README includes roadmap.
- [x] Product spec defines MVP goals and non-goals.
- [x] Demo script describes the cheap-to-expensive config change.
- [x] MVP checklist tracks implementation readiness.

## Done Definition

The MVP is done when:

1. A user can install TrainCost CI in a demo repo.
2. A pull request changing `config.yaml` triggers the action.
3. The action compares base and PR config values.
4. The report shows estimated base cost, PR cost, increase percentage, warnings, and recommendations.
5. The report is clear that costs are estimates and confidence may be low.
6. The demo clearly shows an expensive training change being caught before merge.

## Explicitly Out of Scope

These are intentionally not part of the MVP:

- Dashboard product requirements.
- Kubernetes integration.
- GPU scheduling.
- Cloud billing ingestion.
- MLflow integration.
- W&B integration.
- Comet integration.
- OpenCost or Kubecost integration.
- AI-based runtime prediction.
- Claims of exact GPU cost prediction.
