# Final report-only beta review

Recorded 2026-11-08 KST. Runtime candidate:
`a907b78423cd18b5e7a8f53f5d092fcba6df77e9` in
[PR #13](https://github.com/Pig30nidaE/TrainCost/pull/13).
This is a release-candidate assessment, not publication approval.

## Corrections and scope

Final review found that a base-tip/head diff could attribute target-branch-only
changes to a PR. The Action now uses one unique merge base for both file selection
and baseline contents. Reports name the merge-base and PR-head estimates and
record the baseline SHA. This follows PR changes; it does not simulate the future
merge result. Unrelated histories or multiple best ancestors fail explicitly.

Canonical `mixed_precision: true` now takes precedence over the `fp32` label for
the disabled-precision warning. This interprets declared settings, not observed
hardware behavior. Six actual-Git regressions and two precision tests reproduce
the previously incorrect behavior. Local file comparisons keep their old labels.
Public inputs, structured JSON, and the numeric formula are unchanged.

## Hosted checks

All eight [candidate CI jobs](https://github.com/Pig30nidaE/TrainCost/actions/runs/42406869566)
passed, including Python 3.11-3.14, isolated Action installation, runtime/build
audit, and both complete optional ML-lock audits.
Evidence registration commit `59ceb45c3b224c471ab4708b41e2e9c79fbac78d` also passed
all eight [CI jobs](https://github.com/Pig30nidaE/TrainCost/actions/runs/42408642946),
including the added archive replay and verification-record guards. It changes
verification, evidence, and documentation, not the measured runtime.

The ordinary [external PR run](https://github.com/Pig30nidaE/TrainCost-consumer-validation/actions/runs/42406963444)
and the [real fork run, attempt 2](https://github.com/Pig30nidaE/TrainCost-consumer-validation/actions/runs/42406970081/attempts/2)
both pin the same runtime candidate. Complete, partial, error, unsafe-output
rejection, false comment outputs, and report/Step Summary equality passed.
The user authorized only the candidate-SHA update to the existing fork branch.
The workflow changed six SHA strings, not assertions or permissions. The specific
pending run was approved after review without changing repository policy.
Actual fork token permissions were Contents read and Metadata read.
See [identity, outputs, and archives](external_consumer_validation.md).

## Fresh real-model study

The [protocol](evidence/hf-matrix-final-review-2026-11-08/protocol.md) was written
before execution. The fourth study ran once, without retries or threshold changes,
on the same M1 Mac mini, 16 GB, macOS 26.6.2, Python 3.12.8, and audited macOS lock.
No agent-initiated local tests, builds, installs, or other model jobs ran during
measurement. This interactive computer is not an isolated benchmark host.

Pinned DistilBERT, BERT, and ALBERT revisions used balanced IMDb train/test subsets
of 64 rows each, batch 8, length 128, FP32 MPS, seed 42, and AdamW. Each model had
three one-epoch calibrations and six held-out runs, alternating one and three
epochs. Actual Trainer settings, finite gradients/loss, encoder updates, report
arithmetic, and Step Summary checks passed. Accuracy and F1 are recorded but do
not establish model usefulness on these small subsets.

| Model | Runs | Base median | PR median | PR estimate | Base / PR relative error | Training / report / timing |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| DistilBERT | 9 | 5.123 s | 14.717 s | 15.276 s | 0.60% / 3.80% | PASS / PASS / PASS |
| BERT | 9 | 8.700 s | 25.969 s | 28.332 s | 8.55% / 9.10% | PASS / PASS / PASS |
| ALBERT | 9 | 5.753 s | 16.729 s | 16.715 s | 3.16% / 0.09% | PASS / PASS / PASS |

All base/PR median errors met the fixed 20% limit; all observations in each
calibration/base/PR group met the 15% repeatability limit. Training-process wall
time was 441.71 seconds. The timed train intervals exclude loading, tokenization,
and evaluation, which are recorded separately. No model weights, review text,
tokens, or full environment dump are included in the shared bundle.

The [source inventory](evidence/hf-matrix-final-review-2026-11-08/bundle/source.json)
contains 28 execution files from the immutable runtime candidate. Its hash is
`4703409d434d365efc4fe24289c9c9eaa1a72e9c799f27f7f64734d84e54e107`.
The [bundle manifest](evidence/hf-matrix-final-review-2026-11-08/bundle/manifest.json)
SHA-256 is `a857852c06a7984d4adf2e90bd59f5b6c095fafa78598b9547b39cb05aa8f033`.
Registration replay checks Git blobs and all 108 observations across four studies.
The original timing failures and missing source snapshot remain explicit.
This is bounded sequence-classification evidence, not general HF coverage, CUDA
validation, runtime-prediction accuracy, or real billing. Rates are hypothetical.

## Local regression and package verification

The [final local record](evidence/final-review-local-2026-11-08.json) contains
323 unittest methods: 322 passed and one Linux-only test was skipped on macOS.
Suite sizes are Core 115, Action 77, HF demo 76, model matrix 43, corpus evaluator
6, archive regression 2, and verification-record guards 4. The labeled corpus
passed 50/50. All fixtures, local consumers, missing-PyYAML diagnostics, and archived
evidence replays passed. Inputs were unchanged during the checks. Later copying
the result into the repository is evidence registration, not part of that measured
input fingerprint. QAReview statically reviewed the final output guard and found
no additional actionable issue; it did not rerun that last four-test suite.

Both distributions were built from the runtime candidate with
`SOURCE_DATE_EPOCH=1794080035`. Each was installed in a separate temporary venv
outside the repository. Import, fractional epochs, installed CLI, HF adapter,
subcent Markdown, and JSON checks passed for both wheel and sdist.
All 15 packaged modules match Git blobs; package metadata and MIT license match;
the tar archive has no links or escaping paths. These are local unpublished files,
not uploaded assets or a claim of bit-for-bit cross-platform reproducibility.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `traincost_ci_core-0.2.0b1-py3-none-any.whl` | 29,876 | `9c45f78f83ecad751c6bee7373420ae80ed99226856164fd56e8f341b57b4944` |
| `traincost_ci_core-0.2.0b1.tar.gz` | 40,625 | `255e95dc8c8776984bb03cdaeddf4ca657f742a71d943a982a820b3453327253` |

Reproduce the checks from a full checkout with development dependencies:

```bash
.venv/bin/python scripts/verify_hf_evidence.py
.venv/bin/python docs/evidence/final-consumer-2026-11-08/verify.py
.venv/bin/python scripts/verify_upgrade.py --output /tmp/traincost-local-checks.json
env SOURCE_DATE_EPOCH=1794080035 .venv/bin/python -m build packages/core --no-isolation --outdir /tmp/traincost-dist
.venv/bin/python scripts/verify_wheel.py /tmp/traincost-dist
.venv/bin/python scripts/verify_wheel.py /tmp/traincost-dist --sdist
```

Archive replay is not a new hosted run or independent execution attestation. The
local-check output must be a new file outside the checkout; use a fresh path on
each invocation. Archive it only after verification completes. All existing
evidence inputs remain fingerprinted, including previous verification records.
The full source-package development tests require repository fixtures as documented
in the package README. No PyPI release is claimed.

## Decision boundary

The corrected report-only implementation has candidate-bound hosted, fork,
real-model, and package evidence, and registration CI passed. PM recommends a
report-only beta candidate within the documented limits. Human merge/tag/release
approval must precede publication. PR #13 and consumer PRs remain unmerged. No tag was moved or
pushed and no GitHub Release was published. The remaining unsupported scope is
explicit: live comments, CUDA/WSL2 execution, generation, vision, speech, PEFT,
distributed training, arbitrary HF settings, and production prediction accuracy.
