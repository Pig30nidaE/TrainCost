# Commit-bound real-model study

Date: 2026-11-08. Measured source commit:
`01ddafcda9a2545460f067dbb7c154f9661c2b97`, in
[PR #13](https://github.com/Pig30nidaE/TrainCost/pull/13).

Security follow-up: the [ML dependency audit](evidence/hf-matrix-2026-11-08/ml-dependency-audit.json)
found known advisories in the measured optional training environment. These
measurements remain historical evidence, not approval to publish that lock.
The [replacement environment](hf_security_upgrade_study.md) has its own completed
27-run study. Do not relabel the results below as measurements of that new lock.

DistilBERT, BERT, and ALBERT each completed nine real MPS fine-tuning runs. All
training-contract checks, Action reports, and the predefined timing gates passed.
This supports the reviewed sequence-classification profiles on this Mac, not all
Hugging Face tasks, CUDA behavior, or production prediction accuracy.

## Protocol and provenance

The [protocol](evidence/hf-matrix-2026-11-08/protocol.md) was committed before any
download or measurement. Model/data revisions, 64-row balanced train/test subsets,
FP32, batch 8, length 128, calibration, and acceptance thresholds are unchanged
from the [historical study](hf_model_matrix.md). All 27 runs used fresh processes
and original pretrained weights. There were no automatic retries or excluded runs.
No agent-initiated tests, builds, or installs ran during measurement. This was
still an interactive M1 Mac mini with 16GB memory, not an isolated benchmark host.

The environment remained macOS arm64, Python 3.12.8, PyTorch 2.9.1, Transformers
4.57.6, Accelerate 1.15.0, datasets 4.8.5, and Safetensors 0.8.0. Installation used
the hash-pinned macOS lock. Total training-process wall time was 393.76 seconds,
including process startup and evaluation; downloads/preparation are excluded.

[source.json](evidence/hf-matrix-2026-11-08/bundle/source.json) records the commit,
versioned source inventory, and hashes of all 27 execution-source files. Before
running, the controller checked these against immutable Git blobs. The aggregate
source hash is `200c2b8c073e292d0ee7fbd5ef0022691909e52fdbd9f97bc541b063b945f155`.
The same fingerprint was checked again after execution. The evidence verifier
reconstructs this source inventory from Git without executing historical code.

## Measurements

| Model | Runs | Base median | PR median | PR estimate | PR absolute relative error | Timing |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| DistilBERT | 9 | 4.117 s | 11.992 s | 14.231 s | 18.67% | PASS |
| BERT | 9 | 8.059 s | 23.499 s | 22.961 s | 2.29% | PASS |
| ALBERT | 9 | 6.199 s | 17.423 s | 17.619 s | 1.12% | PASS |

Each group's observations were within 15% of its median. Both base and PR median
errors were within 20% of the frozen calibration-based estimates. DistilBERT is
close to the error boundary. The prior study failed repeatability for DistilBERT
and BERT; those observations remain registered and replayed. The new pass does
not erase that evidence or establish an accuracy guarantee for another workload.

Every run used MPS, matched actual Trainer settings, changed encoder weights, and
passed finite loss/gradient checks. Reports used the explicit hypothetical
`APPLE_M1_MPS=1` hourly rate, not electricity or billed cloud cost. The local Action
returned `analysis-status=complete` and `comment-posted=false` for each model.
Markdown equaled Step Summary; JSON costs and display values matched independent
Decimal calculations. Each one-to-three-epoch comparison showed a 200% increase.

## Recheck the evidence

The [bundle](evidence/hf-matrix-2026-11-08/bundle/manifest.json) contains all runs,
settings, hashes, reports, and metrics. It contains no weights, raw reviews, tokens,
or subprocess logs. Its manifest SHA-256 is
`b114208b5db9c05b0cf704fb8f32c7e16591f84ce0f97112da53a9962bf5f177`.

From a full checkout with the documented development dependencies:

```bash
python scripts/verify_hf_evidence.py
```

This replays both studies, including the historical timing FAIL and missing-source
limitation. It does not download models, train them, or independently attest that
the recorded execution occurred. Fresh training is an explicit opt-in command in
the [matrix guide](../examples/hf-model-matrix/README.md).

The measured commit passed all six jobs in
[hosted CI](https://github.com/Pig30nidaE/TrainCost/actions/runs/42396945740): Python
3.11-3.14, isolated composite Action, and runtime/build dependency audit. That run
predates registration of this new evidence, so its CI result does not cover later
documentation or evidence-registration edits.

The project remains private with Action access `none`. Cross-repository installation,
real fork permissions, and publication approval remain separate release gates.
No release, tag, merge, or access-policy change follows from this measurement.

## Hosted consumer follow-up

Evidence-registration candidate `d6fd314b6528bc077b1a755f4427b4b56987da89` passed
[all six CI jobs](https://github.com/Pig30nidaE/TrainCost/actions/runs/42397896774).
[Consumer PR #14](https://github.com/Pig30nidaE/TrainCost/pull/14), kept unmerged,
used that full SHA and passed
[run 42398032297](https://github.com/Pig30nidaE/TrainCost/actions/runs/42398032297).
Its separate [regression CI](https://github.com/Pig30nidaE/TrainCost/actions/runs/42398032384)
also passed all six jobs. These are same-repository checks, not external/fork tests.

The downloaded [actual outputs](evidence/hf-matrix-2026-11-08/hosted-consumer/verification.json)
record `pull_request`, base `d6fd314b6528bc077b1a755f4427b4b56987da89`, head
`db642a6c106d8a3076d12c2752a7e41abfe73684`, and Linux Python 3.12.16.
The canonical comparison returned complete and $0.10 to $0.30. Added native HF
returned complete with explicit absent-base assumptions; the mixed case returned
partial with one excluded file. Invalid input returned error and null costs.
Every report-producing case returned comment-posted=false and matched a Step
Summary file. Both expected failure steps failed, and the synthetic unsafe-output
sentinel remained unchanged. No rendered browser inspection is claimed.
