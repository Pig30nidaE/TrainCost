# Hugging Face real-model validation

This is the historical study. The later [committed-source study](hf_committed_study.md)
adds another 27 runs with reproducible Git provenance. It does not replace the
failed timing observations or missing-source limitation recorded below.

Date: 2026-11-07. Branch: `codex/hf-model-matrix`, based on
`5983297a22352fe25078cd35a340a930d3663539`. The changes are local and are not the
already-hosted PR #11 candidate.

## Scope

The new profile-driven matrix tests real pretrained DistilBERT, BERT, and ALBERT
models on the same balanced IMDb text-classification subsets. It tests actual
Trainer arguments against the explicit Hugging Face adapter, finite training,
encoder updates, and generated cost reports. It does not prove support for all
Hugging Face tasks, estimate electricity charges, or predict runtime from a model
name. No GPU work is performed by the GitHub Action.

The source fingerprint for this execution is
`466eb92ed15a920d617ac9ac46120230626a390ff0720708c1393bae54e7624b`.
It covers the worker, controller, profiles, imported helpers, pinned dependency
lock, core, and Action entrypoint. Tests and documentation are not in this hash.
No execution source is changed while the study runs.

After measurement, only controller export/check functions were hardened:
`validate_export`, `export_bundle`, `verify_bundle`, and the new
`reproduce_report`. An AST comparison confirmed no training, scheduling,
calibration, or watchdog function changed. The final execution-source fingerprint
is `c5bc0c3bd7a4e873e42bc9dd2128378baa3ef5ad7ed5e2c0d9d062c89938b88b`.
The original measurement fingerprint remains in every run. The stricter checker
successfully revalidated that original bundle; this is not a second GPU study
under the final fingerprint.

Follow-up audit, 2026-11-08: the temporary source copy and temporary environments
are no longer present. The repository artifacts preserve results and the aggregate
source fingerprint, not a complete executable snapshot of the measured worktree.
`evidence-index.json` therefore records no measured commit and marks the source
snapshot unavailable. The historical AST comparison above is a prior observation,
not a check a new checkout can independently rerun. Fresh release-candidate
measurements must bind to a committed source revision.

## Protocol and evidence

See the [execution guide](../examples/hf-model-matrix/README.md) for the fixed
revisions, licenses, subset construction, commands, and contribution procedure.
Each model receives three independent calibration runs and six independent
held-out runs. Calibration is fixed before evaluation. A process watchdog bounds
resource use; failed and incomplete attempts are preserved.

The environment is M1 Mac mini, macOS arm64, Python 3.12.8, PyTorch 2.9.1,
Transformers 4.57.6, Accelerate 1.15.0, datasets 4.8.5, and Safetensors 0.8.0.
MPS and FP32 are required. Checkpoints and external tracking are disabled.

All 27 scheduled fine-tuning runs completed. Every run used MPS, changed encoder
weights, produced finite checked gradients and losses, and matched the reviewed
Trainer settings. There were no automatic retries. Combined training-process
wall time, including process startup and evaluation, was 669.60 seconds.

| Model | Parameters | Training/report | Base median | PR median | PR prediction error | Timing gate |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| DistilBERT | 66,955,010 | PASS / PASS | 5.951 s | 14.950 s | 18.53% over | FAIL |
| BERT | 109,483,778 | PASS / PASS | 12.169 s | 37.934 s | 11.11% under | FAIL |
| ALBERT | 11,685,122 | PASS / PASS | 8.194 s | 25.179 s | 5.55% over | PASS |

All base and PR median errors were within 20%. DistilBERT and BERT failed the
separate 15% within-group repeatability gate. DistilBERT failed repeatability in
all groups; BERT failed in its held-out base and PR groups. The aggregate timing
outcome is **FAIL**, retained in [outcome.json](evidence/hf-matrix-2026-11-07/bundle/outcome.json).
The controller's exit 1 reflects that measured outcome, not a failed download or
cost calculation.

This was a shared interactive Mac, not a thermally or workload-isolated benchmark
machine. Separate QA regression activity overlapped the early measurement period.
Do not attribute the variability solely to the architectures or claim production
runtime accuracy. A future timing study needs a quiet host and a preregistered
larger workload; the present failed observations must not be discarded.

All Action-entrypoint reports returned `complete`, `comment-posted=false`, matched
their Step Summary, and passed independent Decimal checks. The hypothetical
1-to-3-epoch costs were approximately $0.001641 to $0.004922 for DistilBERT,
$0.003122 to $0.009367 for BERT, and $0.002461 to $0.007382 for ALBERT. Each increase
was 200%; full unrounded values remain in JSON. They are not actual bills.

Accuracy across runs ranged from 0.53125 to 0.5625 for DistilBERT, 0.5 to 0.59375
for BERT, and 0.59375 to 0.609375 for ALBERT. Those small-subset results do not
establish useful classifier quality. Sampled MPS allocations peaked at 1,211.3,
2,012.2, and 239.5 MiB respectively. Sampling occurs after backward passes and is
not a measurement of total system memory or every transient activation peak.

The [metadata-only bundle](evidence/hf-matrix-2026-11-07/bundle/manifest.json)
contains all runs, model file hashes, subset indices/hashes, reports, and settings.
It contains no weights or dataset text. Reproduce the evidence checks:

```bash
python scripts/verify_hf_matrix.py \
  --check-bundle docs/evidence/hf-matrix-2026-11-07/bundle
python scripts/verify_hf_evidence.py
```

## Regression verification

Python 3.11.14, 3.12.8, 3.13.12, and 3.14.0 each discovered 267 tests: 266 passed
and one Linux-only test was skipped on macOS. This includes 113 core, 71 Action,
53 original-demo, 24 matrix, and 6 corpus-evaluator tests. All 50 labeled HF corpus
cases passed. The three deterministic fixtures, missing-PyYAML diagnostic, and
local normal/fork consumer simulations passed. These are local checks, not new
hosted CI evidence.

Structured results: [Python 3.11](evidence/hf-matrix-2026-11-07/local-python311.json),
[3.12](evidence/hf-matrix-2026-11-07/local-python312.json),
[3.13](evidence/hf-matrix-2026-11-07/local-python313.json), and
[3.14](evidence/hf-matrix-2026-11-07/local-python314.json).

The core sdist/wheel built successfully. A fresh environment outside the repository
installed the wheel and exercised its console CLI, HF adapter, subcent Markdown,
and JSON. The first install attempt hit sandbox DNS restrictions; the networked
rerun passed with the pinned PyYAML dependency. The known-credential-pattern scan
found zero matches in 373 reachable blobs and the current worktree. That scan is
not a comprehensive confidentiality audit or publication approval.

## Defects fixed alongside this study

- HF utilization warnings now use per-device microbatch size. A large gradient
  accumulation or world size no longer hides a physically small batch. Canonical
  mode retains its existing batch precedence.
- Demo calibration no longer assumes every cost displays with two decimals.
  Its independent Decimal oracle checks JSON totals and complete Markdown rows,
  including subcent values and rounding boundaries.
- Matrix timeout remains inconclusive rather than being labeled measured timing
  failure. Bundle exports reject unexpected metadata fields and omit raw data,
  weights, tokens, full environment variables, and subprocess logs.

## Publication decision

Private Action access remains `none`. No release, tag push, repository visibility
change, PR merge, or permission expansion is performed. The earlier hosted runs
do not validate this new worktree. A reviewed candidate still needs its own
hosted CI evidence; independent external-consumer and fork validation remain
blocked under the retained access restriction.

The contribution claim is deliberately bounded: reproducible configuration
review and a reusable verification protocol across several real text encoders.
Generation, multimodal training, LoRA, distributed engines, and CUDA measurements
need separate evidence before support can be claimed.
