# TrainCost CI GitHub Action

This package contains the composite GitHub Action wrapper for the TrainCost CI core engine.

The action:

- reads the base and PR versions of a training config,
- runs deterministic cost analysis from `packages/core`,
- writes a Markdown report,
- optionally posts or updates a pull request comment.

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `config-path` | `config.yaml` | Config path or glob to compare. |
| `gpu-prices` | empty | Comma-separated hourly GPU prices, such as `T4=0.5,A10G=1.2,A100=3.5`. |
| `budget-limit` | empty | Default budget limit in USD when the config does not include `budget_limit_usd`. |
| `comment-mode` | `false` | Set to `true` to post or update a PR comment. |
| `report-path` | `report.md` | Markdown report output path. |

## Local Repository Usage

```yaml
- name: Run TrainCost CI
  uses: ./packages/github-action
  with:
    config-path: "config.yaml"
    gpu-prices: "T4=0.5,A10G=1.2,A100=3.5"
    budget-limit: "10"
    comment-mode: "false"
    report-path: "report.md"
```

For released usage from another repository, use the root action:

```yaml
- name: Run TrainCost CI
  uses: Pig30nidaE/TrainCost@v0.1.0
  with:
    config-path: "config.yaml"
    gpu-prices: "T4=0.5,A10G=1.2,A100=3.5"
    budget-limit: "10"
    comment-mode: "false"
    report-path: "report.md"
```

`comment-mode: "false"` is the dry-run mode. It only writes the report file.

`comment-mode: "true"` uses the GitHub-provided token to create or update a PR comment when the workflow has `pull-requests: write`.
