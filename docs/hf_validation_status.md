# DistilBERT validation evidence

Updated: 2026-11-07. RTX 3060/CUDA validation: **DEFERRED, NOT RUN**. Publication: **HOLD**.

The user deferred Windows testing and approved a separate Mac smoke. Real MPS
fine-tuning and report arithmetic passed on the M1 Mac mini; its one-run-per-condition
time extrapolation overestimated by 42.965% initially and 7.496% on a verification
rerun after evidence-control fixes. Neither was an independent calibration study.
See [Mac evidence](macos_validation.md).
The gates below concern the original CUDA experiment, not the Mac smoke.

This record is separate from the canonical beta evidence in `qa_report.md`.
The validation tooling is based on cb86e5df199927410e0063768e137845a6811409.
No core cost formula, parser, Action input, or Action output is changed.
Tooling candidate: `243ed0889473180b50fdbc704ede5fd116d3527a`. The consumer workflow
pins this commit; later evidence/workflow-only commits do not alter the experiment.

## Scope and interpretation

The opt-in example uses DistilBERT and IMDb on one user-operated RTX 3060 12GB under
Windows + WSL2 Ubuntu. A canonical config drives both the demo Trainer and TrainCost.
Native Hugging Face settings are not inferred. The demo restricts the run to fixed FP32,
batch 8, one GPU, no gradient accumulation, and an epoch-based schedule.

Three one-epoch calibration executions precede six separate validation executions:
one and three epochs, three repetitions each. Timing covers synchronized `train()`;
download, model loading, tokenization, evaluation, and saving are not training time.
The same GPU and execution conditions must be used throughout. A frozen condition
fingerprint prevents reuse after relevant settings or environment changes.

Time acceptance is an absolute relative error of at most 20% against each validation
group median and repetitions within 15% of their group median. These are predefined
single-experiment criteria, not a product-wide accuracy guarantee. Calibration and
validation samples are distinct executions, not distinct data-distribution evaluations.

USD uses the explicit hypothetical rate `RTX3060=1.00`. Observed wall hours multiplied
by one GPU are not GPU utilization, electricity consumption, or billed cloud hours.
`High` confidence in TrainCost continues to mean input completeness only.

## Evidence gates

| Gate | State |
| --- | --- |
| Core and Action regression tests on the implementation | PASS: 43 core, 30 Action, Python 3.11-3.14 hosted CI |
| Independent Decimal oracle and validation tooling tests | PASS: 39 hosted Linux tests; locally 38 passed and 1 Linux-only test skipped |
| Static six-minute report fixture and known-limitations checks | PASS, including byte-identical expected report and CLI Summary |
| SHA-pinned GitHub-hosted consumer PR, report-only | PASS: report assertions and outputs; see run evidence below |
| Rendered GitHub Step Summary compared to report | Pending operator inspection; local CLI Summary byte comparison passed |
| User WSL2 environment and locked dependencies | NOT RUN |
| Actual model download and 64-example training smoke | NOT RUN |
| Three calibration and six validation GPU executions | NOT RUN |
| Held-out classification metrics and safe evidence bundle | NOT RUN |

No RTX 3060 training duration, accuracy, VRAM usage, or measured timing error is claimed yet.
Failures and inconclusive runs must remain in the evidence; do not replace calibration
after observing validation outcomes or silently reduce the batch size.

Local verification used Python 3.12.8. Existing release fixtures, missing-PyYAML
diagnostics, and outside-repository wheel installation also passed. The known-pattern
history/worktree scan reported no findings; it is not a complete confidentiality audit.

The new tests cover fixed Trainer arguments with mocks, actual CLI output, frozen
calibration, independent arithmetic, balanced subsets, evidence preservation, failed
bundles, subprocess timeout, and SIGTERM cleanup. Actual Linux parent-SIGKILL cleanup
passed in hosted Linux CI, not on macOS. Mock Trainer tests do not prove CUDA compatibility.

## Hosted evidence

- Implementation: [draft PR #9](https://github.com/Pig30nidaE/TrainCost/pull/9), stacked on unmerged PR #7.
- Implementation CI: [run 42266617122](https://github.com/Pig30nidaE/TrainCost/actions/runs/42266617122), five jobs passed.
- Consumer: [draft PR #10](https://github.com/Pig30nidaE/TrainCost/pull/10), only the canonical epoch changes from 1 to 3 relative to its base.
- Consumer report: [run 42266667741](https://github.com/Pig30nidaE/TrainCost/actions/runs/42266667741), [verification job](https://github.com/Pig30nidaE/TrainCost/actions/runs/42266667741/job/128060278282), passed.
- Consumer CI: [run 42266667714](https://github.com/Pig30nidaE/TrainCost/actions/runs/42266667714), passed.

| Observed field | Value |
| --- | --- |
| Event | `pull_request` |
| Base SHA at execution | `002dadc1e60a73254d79800afaabd1de80761a6f` |
| Consumer head SHA | `b8fe979d0964d519c73f78265fe3361de715ff99` |
| Downloaded Action SHA | `243ed0889473180b50fdbc704ede5fd116d3527a` |
| Runner | GitHub-hosted Ubuntu, `ubuntu26/20261101.64` image |
| `report-path` | `/home/runner/work/TrainCost/TrainCost/report.md` |
| `analysis-status` | `complete` |
| `comment-posted` | `false` |
| Cost display | `$0.10` to `$0.30`, `+200%` |
| Warnings asserted | Budget exceeded, cost increase, epoch increase, mixed precision disabled |
| Permissions and checkout | `contents: read`, full history, no persisted checkout credentials; no failures |

No credential-shaped values were found in the reviewed consumer log. GitHub runner
metadata, paths, and the deliberately verified outputs are visible; this is not a
claim that logs contain no environment-derived values or arbitrary confidential text.
The rendered Step Summary is not exposed by the job-log API used here. Inspect it
in GitHub as described in [the consumer guide](hf_consumer_verification.md).

The code candidate is ready for operator preflight, not a successful GPU experiment
or a release approval. Later documentation-only commits may record these results
without changing the candidate or retroactively changing the recorded base SHA.

## User handoff

Windows execution is deferred at the user's request. The instructions below remain
available for a later explicit resume; the Mac smoke does not advance the CUDA gates.

Follow [the example instructions](../examples/huggingface-demo/README.md) from a reviewed
commit, in a dedicated environment and workspace. Run each stage in order and return
the allowlisted evidence bundle. Never attach model weights, dataset text, cached
credentials, raw environment dumps, or a directory-wide archive.

IMDb is marked `other` in its dataset card; do not label its data Apache-2.0 or include
the source reviews in project releases. Remote model code and external reporting are disabled.
The user PC is not registered as a self-hosted GitHub runner.

Implementation and consumer PRs remain unmerged. Release tags, GitHub Releases,
and repository visibility changes require separate approval.

## Dependency reproducibility

The example lock targets Python 3.12, Linux x86-64, and the official PyTorch 2.9.1
CUDA 12.6 wheel. It pins 63 distributions and their hashes. The lock was resolved
and checked with an installation dry run; this is not proof of an actual WSL2
installation, CUDA compatibility, or successful training.

Regenerate only as a reviewed dependency change, with `uv` 0.9.7:

```bash
uv pip compile examples/huggingface-demo/requirements.in \
  --python-version 3.12 --python-platform x86_64-manylinux_2_28 \
  --generate-hashes --no-build --no-header --no-annotate --no-strip-markers \
  --emit-index-url --output-file examples/huggingface-demo/requirements.lock
```

The PyTorch URL is explicit rather than using an additional package index. Model
and dataset downloads remain separate, operator-initiated preparation steps.
