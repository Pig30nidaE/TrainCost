# JSON report contract

The CLI and GitHub Action produce a Markdown report and a separate JSON document.
Use JSON for automation. Do not parse Markdown to obtain cost values or warning codes.
The contract is versioned independently of package releases.

## Generate a report locally

Use Python 3.11 or later on Linux or macOS. On Windows, use WSL2 Ubuntu; native
Windows output handling is not validated and can reject paths. From a checkout,
install the core into a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install ./packages/core
.venv/bin/traincost-ci \
  --base-config examples/pytorch-demo/configs/base-config.yaml \
  --head-config examples/pytorch-demo/configs/risky-config.yaml \
  --gpu-prices 'T4=0.35,A100=3.20' \
  --report-path /tmp/traincost-report.md \
  --json-path /tmp/traincost-report.json
```

`python -m traincost_ci_core` offers the same command. Use `--adapter huggingface`
for the explicitly supported TrainingArguments subset. The default is `canonical`.
Neither mode imports Transformers, downloads a model, or executes training code.

Warnings return exit code 0. Invalid configurations return 2 and produce diagnostic
documents when both output paths are usable. Invalid command syntax or unsafe output
paths return 2 without writing CLI reports.

## Choose output paths

Choose distinct Markdown and JSON paths that do not name either input config. Both
paths are checked before report files are replaced. Directories, symbolic-link
destinations or parents, hard-linked files, and paths that collide with each other
or a protected input are rejected. Parent symlinks are rejected even outside the
checkout, except for the standard macOS `/tmp` and `/var` aliases. Absolute paths
outside the checkout are allowed. Existing regular, singly linked output files can
be replaced, so do not point reports at files you need to keep.

Each report is staged and replaced separately. The two replacements are not a
single transaction: a later I/O failure can leave only one report updated. A
failed preflight does not replace either report. The Action uses the same writer and
also rejects an existing checkout output that matches a config glob. See the
[Action reference](github_action_usage.md#report-path-safety) for diagnostic fallbacks.

## Version 1.0

The [JSON Schema](schemas/report-v1.schema.json) defines the complete structure.

| Field | Meaning |
| --- | --- |
| `schema_version` | `1.0` for this contract |
| `analysis_status` | `complete`, `partial`, `skipped`, or `error` |
| `analyses` | Successful per-file analyses, including path, base/PR config and estimates, changes, confidence, warnings, and recommendations |
| `diagnostics` | Safe file-selection and error messages, without raw config values |
| `summary` | Number of analyzed/excluded configs and sum of analyzed estimates only |

Each warning includes a stable `code`. Its explanatory wording can change between
releases. Compare codes rather than titles. New codes can be added; consumers should
preserve or display unknown codes rather than interpret them as no risk.

Numerical amounts are unrounded USD values serialized as JSON numbers, not money
strings. For example, `0.001` and `0.003` remain distinct. These are estimates, not
exact billing amounts. Applications needing decimal arithmetic should parse JSON
numbers with a decimal parser rather than infer precision from Markdown.

Error and skipped documents have no analyses and have null cost totals, not zero.
Partial documents include successful files only. `excluded_count` identifies omitted
configs and `summary.scope` is always `analyzed_configs_only`. A sum does not imply
that all configurations are scheduled to run.

`complete` means the selected files were processed. It does not mean every setting
was modeled, estimates are accurate, or the run is safe. Check warnings, confidence,
and assumptions. Runtime conditions can become stale even when required input fields
are complete. Raw mappings, secret values, environment variables, and tokens are not
part of this contract.

The Action exposes `report-json-path`. Its `config-adapter` input corresponds to the
local CLI's `--adapter`. Report-only mode does not post a PR comment.

Before publication, consumers must pin a reviewed implementation SHA. No new tag or
public package release is implied by this document. Existing v0.1.0 lacks this JSON
contract and the HF adapter.
