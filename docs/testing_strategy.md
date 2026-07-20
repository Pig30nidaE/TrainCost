# TrainCost CI Testing Strategy

## Goals

The MVP test suite should prove that TrainCost CI can parse common ML config files, compare base and PR values, estimate GPU cost with transparent rules, generate a useful Markdown report, and fail gracefully when PR context or config data is incomplete.

The suite should also protect the product boundary: reports must use estimate/risk language, must not claim exact GPU cost prediction, and must not print secret values.

## Test Layers

### Core Unit Tests

Location: `packages/core/tests/test_core_engine.py`

Coverage areas:

- YAML, JSON, and simple Python config parsing.
- Invalid YAML handling.
- Supported field normalization and coercion.
- Missing fields and low-confidence estimates.
- Cost estimation formula.
- Budget exceeded warnings.
- Cost increase warnings.
- GPU type upgrade warnings.
- GPU count increase warnings.
- Precision regression warnings.
- Small batch size warnings.
- Sensitive-looking config key detection without rendering sensitive values.
- Markdown report structure and estimate-only wording.

Run:

```bash
python3 -m unittest discover packages/core/tests
```

### GitHub Action Unit Tests

Location: `packages/github-action/tests/test_traincost_action.py`

Coverage areas:

- Action input parsing.
- Local dry-run report output.
- No changed config file behavior.
- Missing config behavior.
- Base config unavailable behavior.
- Invalid YAML behavior.
- Multiple changed config file aggregation.
- PR comment failure handling without printing GitHub tokens.

Run:

```bash
python3 -m unittest discover packages/github-action/tests
```

## Manual QA Checklist

Before calling an MVP change complete:

- Run both unit test commands above.
- Review generated report wording for estimate/risk language.
- Confirm README and docs avoid exact-cost claims.
- Confirm logs do not print environment variables, GitHub tokens, cloud credentials, or config secret values.
- Confirm no dashboard, Kubernetes, MLflow, W&B, Comet, OpenCost, or Kubecost scope was added.

## Current Known Gaps

- Comment posting has unit coverage for failure/token safety, but still needs a live pull request smoke test before release.
- Changed-file detection relies on local `git diff` behavior and should be exercised in a real GitHub Actions workflow.
- The dependency-free YAML parser intentionally supports only common mappings and scalar values; complex YAML should be treated as unsupported rather than expanded in the MVP.
