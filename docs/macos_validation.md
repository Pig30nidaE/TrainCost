# Mac validation record

Executed on 2026-11-07. Scope: **Mac compatibility and report arithmetic**, not RTX 3060
acceptance, general runtime prediction, or release approval. Windows validation is
deferred at the user's request.

## Environment and source

- Apple M1 Mac mini, 16 GiB unified memory, macOS 26.6.2, arm64.
- Python 3.12.8 in an isolated environment. PyTorch 2.9.1, Transformers 4.57.6,
  Accelerate 1.15.0, Datasets 4.8.5, Safetensors 0.8.0, NumPy 2.5.4.
- The separate [Mac lock](../examples/huggingface-demo/macos-requirements.lock) was
  installed with hashes enforced. `pip check` found no broken requirements.
- Repository base: `fa687ad297b8a9b488255bc4e304297494f76fa9`, with the Mac smoke script,
  Mac lock and eight tests added locally. Core, Action, and the CUDA runner were not changed.
- Initial script SHA-256: `e8346e1084ff05ac65aab3ac61d70f5f776318d079b42e8b6744079e1abc99e2`.
- Final, rerun script SHA-256: `e1c2b5bcc360101cb3324981730a501493a643d829a286b2057016037ed065ef`.
- Final combined execution-source fingerprint: `7b05b206449d42f06c1de64a842703a553438819c7d17bcf3bbea0ab6fce406e`.
- Mac lock SHA-256: `818183f690b55833021b565136a78260c614ef77ab815b036a456efe624054d3`.

The model and dataset use the same pinned revisions as the CUDA plan. Model loading
uses local Safetensors, `trust_remote_code=False`, and no token. Downloads used the
public Hub; no repository source, training results, dataset text, or weights were uploaded.

## Executed checks

| Check | Result |
| --- | --- |
| Core regression suite | 43 passed |
| Action suite, including real temporary-Git comparisons | 30 passed |
| Demo suite including the Mac orchestration tests | 46 passed, 1 Linux-only test skipped |
| Core/Action branch-enabled coverage | 88%; this does not include the Mac training script |
| Existing risk, missing and invalid fixtures | All matched byte-for-byte |
| Static six-minute HF fixture and known-limitations verifier | Passed |
| Missing-PyYAML diagnostic | Passed |
| Wheel build and installation outside the repository | Passed |
| Known-pattern local history/worktree secret scan | No findings; not a complete confidentiality audit |
| Real DistilBERT download and MPS fine-tuning | Passed for both conditions |

The skipped test is Linux `PR_SET_PDEATHSIG` behavior. macOS timeout and SIGTERM process
group cleanup tests passed. Prior hosted Linux evidence remains separate.

## Real model results

Two fresh processes loaded the original DistilBERT checkpoint. Each used the same 64
balanced IMDb training examples and 64 balanced test examples, seed 42, batch 8, fixed
padding length 128, FP32, accumulation 1, AdamW at 2e-5, a constant schedule, and no
positive `max_steps`. The prepared source subsets and the actual 64-example indices
are recorded in the evidence. Selected test text did not overlap selected training text.
This pair was executed initially and then once more after evidence-control fixes;
both pairs are retained below. The training settings were not changed.

MPS was explicitly required and CPU fallback was disabled. The actual Trainer/model
device was checked. Each training process had a 600-second parent watchdog, with a
child-side deadline and parent-liveness check. There was no automatic retry.

| Observed value | 1 epoch | 3 epochs |
| --- | --- | --- |
| Optimizer updates | 8 | 24 |
| Synchronized `train()` wall time | 6.101106 s | 12.802659 s |
| Training loss | 0.694702 | 0.671450 |
| Test accuracy, 64 examples | 0.531250 | 0.546875 |
| Test F1 | 0.250000 | 0.641975 |
| Finite, nonzero gradient checks | 8/8 | 24/24 |
| Encoder parameter changed | Yes | Yes |
| Sampled maximum MPS allocated memory | 1.183 GiB | 1.183 GiB |

QA found that direct internal-stage invocation could overwrite initial stage evidence,
and that the first result hashed only the Mac script, not all imported source files.
The final runner rejects existing stage artifacts, creates files exclusively, requires
its supervising process, and checks a combined code fingerprint before and after stages.
The initial run does not have this stronger provenance and is not presented as if it did.
The parent-PID/session checks prevent accidental misuse and detect parent exit; they
do not authenticate a caller or defend against another process with the same filesystem access.

| Verification rerun after these fixes | 1 epoch | 3 epochs |
| --- | --- | --- |
| Optimizer updates / finite nonzero gradient checks | 8 / 8 | 24 / 24 |
| Synchronized `train()` wall time | 4.563241 s | 12.735159 s |
| Training loss | 0.694702 | 0.671450 |
| Accuracy / F1 | 0.531250 / 0.250000 | 0.546875 / 0.641975 |
| Encoder changed / final parameters finite | Yes / Yes | Yes / Yes |
| Sampled maximum MPS allocated memory | 1.183 GiB | 1.183 GiB |

All final model parameters were finite. Memory figures are callback samples, not a
global device-memory peak. Timing includes the safety callbacks and first-step overhead;
model loading, tokenization and evaluation are recorded separately. Accuracy/F1 are
descriptive smoke results, not evidence of a useful classifier or a quality improvement.

## What this did not prove

The report used the first run's measured seconds per epoch and an explicit **hypothetical
$1 per compute-unit-hour**. The same assumption was passed to both configs. Independent
Decimal arithmetic agreed with the engine, and budget, cost-increase, epoch-increase,
and FP32 warnings appeared. This is not a cloud price, electricity bill, or MPS price claim.

Multiplying 6.101106 seconds by three predicted 18.303318 seconds, versus 12.802659
seconds observed: **42.965% relative overestimate**, and an observed ratio of 2.098x.
The verification rerun predicted 13.689724 seconds versus 12.735159 observed, a
**7.496% relative overestimate**. The first result was not replaced by this smaller error.
Each pair used its own single base run; there was no independent calibration or
preplanned repetition study, and the runner's evidence controls changed between pairs.
This result does not pass or fail the separately planned RTX 3060 timing gate. It shows
why compatibility/arithmetical success must not be presented as timing accuracy.
Initialization overhead is a possible contributor; this experiment did not isolate its cause.

The small amounts also reveal a display limitation: the report rounds base cost and
budget to `$0.00`, although their unrounded values are positive. The detailed inputs
retain the budget. No core formatting behavior was changed during this validation.
In the rerun the display is `$0.00 -> $0.00 (+200%)`, with a zero-looking budget warning.
The actual hypothetical amounts are approximately `$0.001268 -> $0.003803`, with a
`$0.002535` budget. Sub-cent formatting is a concrete follow-up defect, not a reason
to describe the arithmetic or the hardware execution as failed.

## Evidence and reproduction

[Result](evidence/macos-distilbert-2026-11-07/result.json),
[base run](evidence/macos-distilbert-2026-11-07/base.json),
[PR run](evidence/macos-distilbert-2026-11-07/pr.json),
[selection indices and hashes](evidence/macos-distilbert-2026-11-07/selection.json),
[report](evidence/macos-distilbert-2026-11-07/report.md),
[base config](evidence/macos-distilbert-2026-11-07/measured-base.json), and
[PR config](evidence/macos-distilbert-2026-11-07/measured-pr.json).
These files contain metadata only. Do not archive or share the cache directory.

The stronger-provenance rerun has its own [result](evidence/macos-distilbert-2026-11-07/rerun/result.json),
[base](evidence/macos-distilbert-2026-11-07/rerun/base.json),
[PR](evidence/macos-distilbert-2026-11-07/rerun/pr.json),
[source contract](evidence/macos-distilbert-2026-11-07/rerun/run-contract.json),
and [report](evidence/macos-distilbert-2026-11-07/rerun/report.md). No best run was selected.

From the repository root on the tested Mac, use a new environment and workspace:

```bash
python3.12 -m venv "$HOME/traincost-macos-hf"
. "$HOME/traincost-macos-hf/bin/activate"
python -m pip install --require-hashes --only-binary=:all: -r examples/huggingface-demo/macos-requirements.lock
python -m pip check
python scripts/verify_hf_macos.py --device mps --workspace "$HOME/traincost-macos-smoke-001"
```

This opt-in command downloads the pinned assets and executes actual training. It refuses
an existing workspace and CI execution. On MPS failure it does not silently switch to CPU.
Use the original `requirements.lock` and `run_validation.py` only for the separate WSL2
experiment. Mac timings must never populate its RTX 3060 calibration artifacts.

References: [PyTorch 2.9 MPS backend](https://docs.pytorch.org/docs/2.9/notes/mps.html),
[HF Trainer fine-tuning](https://huggingface.co/docs/transformers/v4.57.1/en/training).
