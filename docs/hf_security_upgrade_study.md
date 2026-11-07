# Real-model validation after the dependency upgrade

Date: 2026-11-08. Measured commit:
`26613f604b9a25cecd65a6f8835dfd3ca8f5997e`, in
[PR #13](https://github.com/Pig30nidaE/TrainCost/pull/13).

DistilBERT, BERT, and ALBERT each completed nine fresh MPS fine-tuning runs with
the replacement dependency lock. All training contracts, report checks, and
preregistered timing criteria passed. This closes the discovered optional-lock
advisory and local compatibility follow-up. It does not authorize publication or
establish support for all Hugging Face models, tasks, or accelerators.

## Environment and provenance

The [protocol](evidence/hf-matrix-security-2026-11-08/protocol.md) was committed
before execution. The study ran exactly once on an interactive M1 Mac mini with
16 GB memory, macOS 26.6.2, and Python 3.12.8. No agent-initiated tests, builds,
installs, or other model processes ran concurrently. This was not an isolated
benchmark host; ordinary OS and user activity cannot be excluded.

The fresh `.venv-hf-matrix-v2` environment used the complete hash-pinned macOS lock:
Torch 2.14.1, Transformers 5.22.2, datasets 5.1.0, Accelerate 1.15.0,
Safetensors 0.8.0, and Hugging Face Hub 1.31.0. Installation, `pip check`, actual
Trainer argument construction, and MPS preflight passed before training.
The [security record](ml_dependency_security.md) includes all 52 macOS and 71 CUDA
dependency audit entries, with no known advisories or suppressions at the recorded
time. Advisory checking is not a guarantee against undiscovered vulnerabilities.

[source.json](evidence/hf-matrix-security-2026-11-08/bundle/source.json) records
inventory version 2, 28 execution files, and the measured commit. Its source hash is
`b18e1a307d31b15cf83b5333eea55e5f50558a377164633b3495e2f7b2b2a3da`.
The verifier reconstructs that inventory from immutable Git blobs. Metadata hashes
and the pre-load safety validator are part of the measured source. Model and data
revisions, balanced 64-row subsets, batch 8, length 128, FP32, and all other
training conditions remain fixed. Epoch count is the only comparison change.

## Results

| Model | Runs | Base median | PR median | PR estimate | PR absolute relative error | Training / reports / timing |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| DistilBERT | 9 | 4.897 s | 14.246 s | 14.883 s | 4.47% | PASS / PASS / PASS |
| BERT | 9 | 8.726 s | 25.603 s | 26.188 s | 2.28% | PASS / PASS / PASS |
| ALBERT | 9 | 5.592 s | 16.234 s | 16.756 s | 3.22% | PASS / PASS / PASS |

All base and PR median errors were within 20% of their frozen calibration-based
predictions. Every run in each calibration/base/PR group was within 15% of its
group's median. Total training-process wall time was 429.94 seconds, including
process startup and evaluation but excluding preparation/downloads. Timed
`Trainer.train()` intervals exclude model loading, tokenization, and evaluation.

Every run used MPS, matched its actual Trainer settings, changed encoder weights,
and passed finite loss/gradient checks. The bundle records accuracy, F1, sampled
MPS allocation, process RSS, and component timings without publishing reviews or
weights. These small subsets do not establish useful model quality.

The real local Action returned `complete` and `comment-posted=false` for each
model. JSON numbers and Markdown display matched independent Decimal arithmetic;
the reports matched Step Summary. Costs use a hypothetical `$1/unit-hour`, not a
bill or electricity measurement. Each one-to-three-epoch comparison increased the
estimate by 200%.

## Reproduce and audit

```bash
.venv/bin/python scripts/verify_hf_evidence.py
.venv/bin/python scripts/verify_hf_matrix.py \
  --check-bundle docs/evidence/hf-matrix-security-2026-11-08/bundle
```

The first command needs a full Git checkout. It replays all three registered
studies, 81 observations, and verifies available source snapshots against Git
blobs, preserving the original timing failures and provenance limitation. The
second command checks only the specified 27-run bundle's internal consistency;
it does not compare source to Git blobs. Neither command needs ML packages,
downloads, or a GPU. The old locks and measurements remain historical evidence,
not recommended installation targets. No observations were discarded or thresholds
adjusted to produce the new result.

The bundle manifest SHA-256 is
`00f943c29c0f58cdf4abc83e2e40cac4421a6cb2da8c8e436e1affda467ee672`.
The measured commit passed all eight
[hosted CI jobs](https://github.com/Pig30nidaE/TrainCost/actions/runs/42400274167),
including Python 3.11-3.14, isolated Action installation, and both optional ML audits.

The SHA-pinned [consumer PR #14](https://github.com/Pig30nidaE/TrainCost/pull/14)
also passed [run 42401267868](https://github.com/Pig30nidaE/TrainCost/actions/runs/42401267868).
Its root and package Actions use measured commit `26613f6`. Base SHA was that same
commit; head was `4d745b8a096a8c7178a674cce868253e750294b5`. The event was
`pull_request` on GitHub-hosted Linux/Python 3.12.16. Complete, added HF, partial,
invalid, and unsafe-output cases passed their assertions. All four report outputs
had `comment-posted=false` and matched runner Step Summary files. The added case's
base cost is an explicit default, not measured savings. Exact outputs and reports
are retained in [verification.json](evidence/hf-matrix-security-2026-11-08/hosted-consumer/verification.json).
The consumer branch's [eight-job CI](https://github.com/Pig30nidaE/TrainCost/actions/runs/42401267872)
passed too. Keep the consumer PR unmerged. No rendered browser inspection is claimed.

CUDA/WSL2 execution, generation, vision, speech, PEFT, distributed training, and
general runtime prediction remain outside this evidence. Real external-repository
and fork distribution validation remains blocked by the retained private Action
access setting. Same-repository reports do not satisfy that gate. No release,
tag push, repository visibility change, or access expansion was performed.
