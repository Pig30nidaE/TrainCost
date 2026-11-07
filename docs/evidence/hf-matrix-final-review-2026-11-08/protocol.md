# Final-review compatibility study

Registered before execution on 2026-11-08 KST for candidate
`a907b78423cd18b5e7a8f53f5d092fcba6df77e9`.

The final review corrected PR merge-base selection and canonical mixed-precision
warning precedence. Keep all 81 earlier observations, including timing failures.
This fourth study verifies the corrected committed source; it does not relabel
earlier runs as measurements of the new candidate.

Use `.venv-hf-matrix-v2` and the existing hash-pinned macOS dependency lock.
Run DistilBERT, BERT, and ALBERT once each with the unchanged 64-row balanced
train/test subsets, seed 42, FP32 MPS, batch 8, 128 tokens, and AdamW protocol.
Each profile has three one-epoch calibrations and six alternating held-out runs:
three one-epoch base and three three-epoch PR measurements. Total: 27 processes.

Keep the existing 20% median error and 15% within-group repeatability limits,
600-second per-training-process watchdog, and 3,600-second combined limit.
Do not change thresholds or retry after seeing results. Preserve every failure
and timeout. Compatibility, report correctness, and timing are separate outcomes.

Use a new workspace `.hf-validation-matrix-final-review-2026-11-08`. Do not run
other agent-initiated local tests, builds, or installs during measurement.
Export only the existing allowlisted metadata bundle. Do not publish model
weights, dataset text, raw logs, tokens, or environment dumps. This study does not
validate CUDA, general HF task support, real billing, or release authorization.
