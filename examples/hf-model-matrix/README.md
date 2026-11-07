# Real-model validation matrix

This opt-in study connects the same Hugging Face training arguments to actual
fine-tuning and TrainCost reports. It covers sequence classification with three
pretrained architectures, not every Hugging Face model or task. The GitHub Action
does not download models or train them.

| Profile | Upstream model | Pinned revision | License |
| --- | --- | --- | --- |
| distilbert | [distilbert/distilbert-base-uncased](https://huggingface.co/distilbert/distilbert-base-uncased) | `12040accade4e8a0f71eabdb258fecc2e7e948be` | Apache-2.0 |
| bert | [google-bert/bert-base-uncased](https://huggingface.co/google-bert/bert-base-uncased) | `86b5e0934494bd15c9632b12f734a8a67f723594` | Apache-2.0 |
| albert | [albert/albert-base-v2](https://huggingface.co/albert/albert-base-v2) | `8e2f239c5f8a2c0f253781ca60135db913e5c80c` | Apache-2.0 |

The classification head is initialized with seed 42 and the encoder is fine-tuned.
The worker uses `AutoModelForSequenceClassification` and the generic `base_model`
interface. Adding an architecture does not require a hard-coded encoder attribute.
All downloads are pinned; training uses local Safetensors with
`trust_remote_code=False` and network access disabled through Hub offline mode.
No remote model code, external tracking, or Hub upload is enabled.
Before calling Transformers, the runner checks model and tokenizer metadata against
reviewed SHA-256 values. It rejects remote-code, custom-kernel, template, and
external-file fields, duplicate/nonfinite JSON, and unreviewed model dimensions.
This boundary does not make vulnerable third-party libraries safe; the optional
ML dependency audit must be reviewed separately before running an environment.

## Reproduce on Apple Silicon

Requirements: macOS arm64, Python 3.12, working MPS, at least 3 GiB available system
memory at each process start, and enough disk space for model and dataset caches.
This is a local experiment. It rejects CI and PR runners. The older
[RTX 3060 study](../huggingface-demo/README.md) remains separate and unexecuted.

From the repository root:

```bash
python3.12 -m venv .venv-hf-matrix
.venv-hf-matrix/bin/python -m pip install -r examples/huggingface-demo/macos-requirements.lock
.venv-hf-matrix/bin/python scripts/verify_hf_matrix.py --list
.venv-hf-matrix/bin/python -I scripts/verify_hf_matrix.py \
  --workspace "$PWD/.hf-validation-matrix-new"
```

The workspace must not exist and must not contain symlink path components. On
macOS, use `/private/tmp` rather than its `/tmp` symlink. To run one reviewed
profile, add `--models bert`. A subset run is not evidence for the other models.
No automated retries or resumption are supported. Preserve failed workspaces.
Commit execution-source changes before running. The controller rejects source
that differs from HEAD, including untracked execution modules. Its metadata bundle
contains `source.json` with the commit SHA and every execution-file hash. Use a
full Git checkout to replay the registered source check. Git objects are read,
never executed by the checker. Keep the ignored workspace until its evidence is
reviewed and archived; temporary directories may disappear between sessions.

The controller launches a fresh process and original pretrained weights for every
measurement. It stops each training process after 600 seconds and limits combined
training-process wall time to 3,600 seconds. Preparation has a separate 1,200-second
limit per model. A parent-death watchdog stops orphaned workers. There is no CPU
fallback or automatic batch reduction. OOM and configuration mismatch are failures;
timeout is inconclusive. Logs do not include raw exceptions, tokens, or environment
variables.

## Protocol

The dataset is [stanfordnlp/imdb](https://huggingface.co/datasets/stanfordnlp/imdb),
revision `e6281661ce1c48d982bc483cf8a173c1bbeb5d31`. Its license metadata is `other`,
not the models' Apache license. Neither reviews nor weights are redistributed.
Each model uses the same seeded, balanced 64 training and 64 test examples. Exact
text overlap between splits is excluded. Selection indices and content hashes are
recorded. The small subsets are a compatibility experiment, not a model benchmark.

- FP32 on one MPS device, fixed padding to 128 tokens, per-device batch 8,
  gradient accumulation 1, AdamW at `2e-5`, constant scheduler, no warmup.
- No intermediate evaluation or checkpoint saving. Full encoder fine-tuning.
- Three independent 1-epoch calibration runs. Freeze their median and a budget
  of twice the base estimated cost before any held-out measurement.
- Three independent 1-epoch base and three 3-epoch PR runs. Alternate their order.
  The total is nine runs per model, 27 for the full matrix, with 8 or 24 updates.
- Synchronize MPS immediately before and after `Trainer.train()`. Include startup
  within that method. Record loading, tokenization, evaluation, and parameter
  checking separately. Gradient-safety callback overhead is included in training.
- Require finite losses and gradients, changed encoder parameters, and matching
  actual Trainer device, world size, precision, batching, and epochs.
- Model file hashes, subset hashes, installed versions, settings, attention
  implementation, and source fingerprint bind each comparison. Epoch is the only
  permitted training-condition change.

Accuracy and F1 describe these small runs. There is no accuracy release gate, and
no claim of useful fine-tuned model quality.

## Interpret the results

`compatibility_status`, `report_status`, and `timing_status` are separate. A model
can train successfully and produce the correct report while linear time
extrapolation fails. A completed timing study passes only when each held-out median
is within 20% of its frozen prediction and every observation in all three groups
is within 15% of its group's median. These thresholds are fixed before execution.
The controller never adjusts them to obtain a pass.

Cost uses an explicit **hypothetical $1 per MPS-unit-hour**. It is not electricity
cost or a cloud bill. Independent Decimal arithmetic checks the JSON values and
Markdown display. The real Action entrypoint must return `complete` and
`comment-posted=false`; its report must match Step Summary. This is local Action
evidence, not a substitute for a GitHub-hosted external-consumer test.

The `bundle/` directory contains metadata and reports only. It excludes caches,
weights, review text, raw subprocess logs, tokens, and full environment variables.
Recheck its hashes, actual settings, costs, and timing calculations without GPU
libraries or model downloads:

```bash
.venv/bin/python scripts/verify_hf_matrix.py --check-bundle /path/to/bundle
```

A successful bundle check means the recorded results are internally consistent.
It does not change a recorded `FAIL` or `INCONCLUSIVE` into a pass and is not a
cryptographic attestation that training occurred.

## Contribute another model

1. Choose an ungated pretrained sequence-classification-compatible architecture
   with Safetensors and a fast tokenizer. Review the upstream license and model
   card. Record an immutable Hub commit, not `main` or a mutable tag.
2. Add its profile to `profiles.json`. Permit only the required model/tokenizer
   filenames. Add reviewed `config.json` and `tokenizer_config.json` hashes plus
   byte-preserved regression fixtures with license attribution. Do not add Python
   or pickle files. Keep the existing study protocol.
3. Run the offline tests and then the opt-in study on the supported device. Record
   failures as well as successes. Do not reuse calibration across models or settings.
4. Submit metadata evidence, its committed source revision, and file hashes. Do not commit weights,
   raw dataset content, or authentication material.

```bash
.venv/bin/python -m unittest discover -s examples/hf-model-matrix/tests
.venv/bin/python scripts/verify_hf_matrix.py --list
```

Generation, vision, speech, quantization, PEFT/LoRA, positive `max_steps`, distributed
training, CUDA timing, and native Windows are outside this matrix. Supporting them
requires a separate execution contract and tests, not another model name.
