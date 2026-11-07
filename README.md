# TrainCost CI

[![CI](https://github.com/Pig30nidaE/TrainCost/actions/workflows/ci.yml/badge.svg)](https://github.com/Pig30nidaE/TrainCost/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Review ML training cost risk before a pull request is merged.
TrainCost CI compares training configs, estimates GPU-hours and cost, and explains its inputs and assumptions.
Think **Infracost for ML experiments**.

**Status: v0.2.0-beta.1 candidate, not published.** The existing v0.1.0 tag does not include these safeguards.
The old measured ML lock has known advisories. Its replacement passes the complete
dependency audit; fresh training verification is pending. Do not treat successful
historical model runs as approval of another environment. See the
[dependency security record](docs/ml_dependency_security.md).
This beta focuses on reports and GitHub Step Summary. PR commenting is experimental.
The candidate adds an explicit Hugging Face adapter, stale-runtime warnings,
subcent amounts, an installed CLI, and versioned JSON.
[Candidate PR #13](https://github.com/Pig30nidaE/TrainCost/pull/13) includes the
multi-model upgrade. Its measured source commit `01ddafc` passed
[Python 3.11-3.14 CI](https://github.com/Pig30nidaE/TrainCost/actions/runs/42396945740).
These links require repository access. The older consumer PR #12 tests an earlier
candidate and does not establish consumer behavior for this revision.
Independent cross-repository and real fork validation remain release gates because
the user retained the current Action access restriction. See the
[PM status](docs/pm_status.md) for remaining gates.
The [commit-bound model study](docs/hf_committed_study.md) completed 27 real runs
with all training, report, and timing checks passing. The prior study's timing
failures remain recorded; neither study establishes general runtime accuracy.

## See the three outcomes

| Scenario | Result | Evidence |
| --- | --- | --- |
| More epochs, larger GPUs, less efficient settings | $0.04 to $21.33, +48,662%, risk warnings | [Full report](examples/pytorch-demo/expected-report.md) |
| GPU and runtime information missing | Low confidence, explicit assumed inputs | [Full report](examples/pytorch-demo/expected-missing-report.md) |
| Invalid epoch count | No estimated cost, error status, exit 2 | [Full report](examples/pytorch-demo/expected-invalid-report.md) |

![Risk report excerpt rendered from the actual fixture](docs/assets/risk-report.png)

These are deterministic config examples, not measured training runs.
[All report images and reproduction steps](docs/demo_script.md) cover the three scenarios.

## Opt-in model validation

The [real-model matrix](examples/hf-model-matrix/README.md) adds profile-driven
DistilBERT, BERT, and ALBERT sequence-classification verification on Apple Silicon.
It checks actual Trainer arguments against the HF adapter, runs independent
calibration and held-out repetitions, and keeps report correctness separate from
time-extrapolation accuracy. This is a bounded text-classification study, not
support for all Hugging Face tasks. [Measured results](docs/hf_committed_study.md).

The [DistilBERT validation example](examples/huggingface-demo/README.md) connects one canonical
config to a real text-classification training run on a user-operated RTX 3060 12GB under WSL2.
Its separate runner measures calibration and held-out executions; the GitHub Action still only
reviews config changes and never trains models. The demo runner is separate from the bounded
Hugging Face config adapter described below.
USD values use an explicit hypothetical rate, not an electricity bill or cloud invoice.
[Validation status](docs/hf_validation_status.md) distinguishes tooling checks from GPU evidence.

## Run locally

The local CLI targets Linux and macOS with Python 3.11 or later. On Windows, use
WSL2 Ubuntu; native Windows output handling is not validated and can reject paths.
From the repository root:

~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install ./packages/core
.venv/bin/python scripts/verify_release.py
.venv/bin/traincost-ci \
  --base-config examples/pytorch-demo/configs/base-config.yaml \
  --head-config examples/pytorch-demo/configs/risky-config.yaml \
  --gpu-prices "T4=0.35,A10G=1.2,A100=3.20" \
  --budget-limit 5 --report-path /tmp/traincost-report.md \
  --json-path /tmp/traincost-report.json
~~~

Analysis runs locally. It does not execute training code or send config contents to an external service.
Dependency installation downloads PyYAML; experimental comment mode sends the sanitized report to GitHub.

## Use in GitHub Actions

The [external consumer template](examples/external-consumer/README.md) uses a
separate consumer repository and requires a reviewed upgrade commit SHA. The source
is still private and currently disallows cross-repository Action access. The template
does not work until that gate is resolved; no existing tag contains the upgrade.

The following example is for testing inside this repository, not external installation:

~~~yaml
name: Review training cost
on: pull_request
permissions:
  contents: read
jobs:
  traincost:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: ./
        id: cost
        with:
          config-path: "examples/pytorch-demo/config.yaml"
          gpu-prices: "T4=0.35,A100=3.20"
          budget-limit: "5"
          comment-mode: "false"
~~~

The action writes report-path, report-json-path, comment-posted, and analysis-status outputs, and appends Markdown to Step Summary.
Cost risk does not fail the job. Invalid inputs or an entirely failed analysis return exit 2.
For an added config, the Action compares the new file to explicit illustrative base assumptions;
that base estimate is not a measurement of a previous run.
Choose report paths that do not contain data you need to keep; existing regular output
files may be replaced. [Output path safety](docs/github_action_usage.md#report-path-safety)
describes rejected destinations and diagnostic fallbacks.
For broad config globs such as `**/*.json`, set both report paths under
`${{ runner.temp }}` outside the checkout so existing reports do not match the glob.
[Full input, output, and status reference](docs/github_action_usage.md).

## What is detected

TrainCost reads these exact keys from YAML, JSON, and literal Python assignments:

model, model_name, epochs, max_epochs, batch_size, global_batch_size, precision, mixed_precision,
gpu_type, gpu_count, estimated_minutes_per_epoch, dataset_size, budget_limit_usd.

Nested canonical keys are supported with source paths. Conflicting values and training fields inside lists are rejected.
Canonical mode does not translate framework aliases. Known unmodeled training
settings produce a warning instead of a clean report. Opt into `config-adapter:
huggingface` in the Action or `--adapter huggingface` in the installed CLI for a
bounded TrainingArguments subset. Positive max_steps, ambiguous batching and
unsupported distributed engines are rejected. GPU hardware discovery, Python
execution and Hydra resolution remain unsupported.
[Supported formats and validation rules](docs/config_reference.md).

## What the estimate means

~~~text
GPU-hours = epochs * estimated_minutes_per_epoch / 60 * gpu_count
cost = GPU-hours * hourly_price
~~~

Use your provider's rate per GPU-hour through gpu-prices. Built-in prices are illustrative examples, not current market rates.
Missing fields use visible defaults and Low confidence. An unknown GPU price uses $1/GPU-hour and Medium confidence.
Confidence describes input completeness, not actual billing accuracy.
Changes to model, data, batch, precision, GPUs or known execution settings with the
same minutes per epoch produce a stale-runtime warning. A new numeric time input is
not proof of remeasurement; this tool cannot verify its provenance automatically.
Runtime is held fixed when GPU count changes; multi-GPU speedups, utilization, storage, and network charges are not modeled.
Combined totals cover analyzed configs, not a forecast that every config will be run.
Markdown displays positive subcent amounts without rounding them to zero; JSON retains
unrounded numeric estimates. A warning is not budget enforcement.

## Engineering evidence

- [Architecture and trust boundaries](docs/architecture.md)
- [Regression tests and release gates](docs/testing_strategy.md)
- [Current QA evidence](docs/qa_report.md)
- [Portfolio walkthrough](docs/portfolio.md)
- [PM status and remaining publication steps](docs/pm_status.md)
- [Beta release notes](docs/release_notes_v0.2.0.md)
- [JSON report and installed CLI](docs/json_report.md)
- [Labeled upstream-derived HF corpus](examples/hf-config-corpus/README.md)
- [Contribution guide](CONTRIBUTING.md) and [security reporting](SECURITY.md)

Project code is MIT licensed. The [upstream model metadata fixtures](examples/huggingface-demo/tests/fixtures/model-metadata/README.md)
retain their Apache-2.0 license and attribution. No dashboard, backend, cloud
account, or paid GPU is required for config review.
