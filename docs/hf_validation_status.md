# DistilBERT validation evidence

Updated: 2026-11-07. GPU validation: **NOT RUN**. Publication: **HOLD**.

This record is separate from the canonical beta evidence in `qa_report.md`.
The validation tooling is based on cb86e5df199927410e0063768e137845a6811409.
No core cost formula, parser, Action input, or Action output is changed.
Tooling candidate: `c29e6dc30894ff18a17a0486f4ef37125a0fd0d9`. The consumer workflow
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
| Core and Action regression tests on the implementation | PASS locally: 43 core, 30 Action |
| Independent Decimal oracle and validation tooling tests | 37 PASS, 1 Linux-only test skipped on macOS; hosted result pending |
| Static six-minute report fixture and known-limitations checks | PASS, including byte-identical expected report and CLI Summary |
| SHA-pinned GitHub-hosted consumer PR, report-only | Pending |
| User WSL2 environment and locked dependencies | NOT RUN |
| Actual model download and 64-example training smoke | NOT RUN |
| Three calibration and six validation GPU executions | NOT RUN |
| Held-out classification metrics and safe evidence bundle | NOT RUN |

No actual training duration, accuracy, VRAM usage, or measured timing error is claimed yet.
Failures and inconclusive runs must remain in the evidence; do not replace calibration
after observing validation outcomes or silently reduce the batch size.

Local verification used Python 3.12.8. Existing release fixtures, missing-PyYAML
diagnostics, and outside-repository wheel installation also passed. The known-pattern
history/worktree scan reported no findings; it is not a complete confidentiality audit.

The new tests cover fixed Trainer arguments with mocks, actual CLI output, frozen
calibration, independent arithmetic, balanced subsets, evidence preservation, failed
bundles, subprocess timeout, and SIGTERM cleanup. Actual Linux parent-SIGKILL cleanup
is a hosted CI gate, not a macOS pass. Mock Trainer tests do not prove CUDA compatibility.

## User handoff

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
