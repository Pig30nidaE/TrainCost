# GitHub Action Usage

TrainCost CI runs in pull requests, compares a base-branch training config with the PR version, and writes a Markdown cost-risk report.

## Example Workflow

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
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run TrainCost CI
        uses: OWNER/traincost-ci@v1
        with:
          config-path: "config.yaml"
          gpu-prices: "T4=0.35,A10G=1.2,A100=3.20"
          budget-limit: "5"
          comment-mode: "false"
          report-path: "report.md"
```

`OWNER/traincost-ci@v1` is a placeholder. Replace it with the published TrainCost CI action owner and release ref before using the workflow in another repository.

Use `comment-mode: "false"` for dry runs. The action only writes `report.md` and does not post to the pull request.

Use `comment-mode: "true"` when you want TrainCost CI to post or update a PR comment. This requires `pull-requests: write`. If GitHub does not provide write permission, such as some fork pull requests, the action still writes the report and exits successfully.

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `config-path` | `config.yaml` | Config path or glob to compare. Supported files are YAML, JSON, and simple Python literal configs. |
| `gpu-prices` | empty | Comma-separated GPU hourly prices, for example `T4=0.5,A10G=1.2,A100=3.5`. Built-in defaults are used when a GPU type is known and not overridden. |
| `budget-limit` | empty | Default budget limit in USD when the config does not define `budget_limit_usd`. |
| `comment-mode` | `false` | Set to `true` to post or update a pull request comment. |
| `report-path` | `report.md` | Path where the generated Markdown report is saved. |

## Report Generation

On a pull request, the action reads the base config with `git show <base_sha>:<config-path>` and the PR config from the head SHA, falling back to the checked-out worktree when needed.

The core engine then:

- parses supported training fields,
- estimates base and PR GPU cost,
- detects deterministic cost and efficiency warnings,
- renders Markdown,
- writes the result to `report-path`.

If no readable config is found, the action writes a graceful report explaining that analysis was skipped.

## Local Dry Run

You can run the action entrypoint without GitHub by providing explicit base and head config files:

```bash
python3 packages/github-action/traincost_action.py \
  --base-config examples/pytorch-demo/configs/base-config.yaml \
  --head-config examples/pytorch-demo/configs/risky-config.yaml \
  --gpu-prices "T4=0.35,A10G=1.2,A100=3.20" \
  --budget-limit "5" \
  --comment-mode "false" \
  --report-path "report.md"
```

The command writes `report.md` and performs no network calls.

## Comment Mode Status

Comment mode uses the GitHub issue comments API through the GitHub-provided token. It searches for a hidden `traincost-ci-report` marker and updates the existing comment when present; otherwise it creates a new comment.

Current limitations:

- Comment posting has not been exercised against a live pull request in this repository yet.
- The action reads the first 100 PR comments when looking for an existing report.
- Fork pull requests may not have permission to write comments, depending on repository settings.
