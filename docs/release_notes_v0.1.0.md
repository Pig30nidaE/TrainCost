# TrainCost CI v0.1.0

TrainCost CI v0.1.0 is the first release for PR-level ML training cost review: Infracost for ML experiments.

## Highlights

- Parse common training fields from YAML, JSON, and simple Python literal configs.
- Compare base-branch and pull-request config values with deterministic cost estimation.
- Warn about budget overruns, large cost or epoch increases, more expensive GPU types, higher GPU counts, disabled mixed precision, small batches, and low-confidence inputs.
- Generate a concise Markdown report with estimated base and PR costs, percentage change, recommendations, and confidence.
- Run as a composite GitHub Action with report-only mode and optional PR comment creation or update.

## GitHub Action Usage

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0

- name: Run TrainCost CI
  uses: Pig30nidaE/TrainCost@v0.1.0
  with:
    config-path: "config.yaml"
    gpu-prices: "T4=0.35,A10G=1.2,A100=3.20"
    budget-limit: "5"
    comment-mode: "false"
    report-path: "report.md"
```

Report-only mode requires `contents: read`. PR commenting additionally requires `pull-requests: write`.

## Known Limitations

- Cost values are estimates based on config inputs and configured GPU prices, not exact cloud bills.
- Live GitHub validation covers `comment-mode: false`; live PR comment posting remains unverified.
- The dependency-free YAML fallback supports common mappings and scalar values, not the full YAML language.
