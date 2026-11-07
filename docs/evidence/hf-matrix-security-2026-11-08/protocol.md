# Dependency-upgrade compatibility study

Registered before measurement on 2026-11-08.

Purpose: exercise the security-upgraded optional training environment and reviewed
metadata boundary. The previous two studies used a lock with known advisories;
their 54 observations remain unchanged. They do not approve the replacement lock.

Use the committed source and hash-pinned macOS environment in
`.venv-hf-matrix-v2`: Torch 2.14.1, Transformers 5.22.2, datasets 5.1.0,
fsspec 2026.7.0, and the complete transitive lock. Both platform locks were audited
without suppression. Source inventory version 2 includes the pre-load metadata
validator. `bundle/source.json` records the immutable commit and execution hashes.

Run all three reviewed profiles exactly once in the fresh workspace
`.hf-validation-matrix-security-2026-11-08`. Keep the existing protocol: balanced
64-row train/test subsets, seed 42, FP32 MPS, batch 8, 128 tokens, three one-epoch
calibrations, then alternating three one-epoch base and three three-epoch PR runs
per model. Keep the 20% median prediction error and 15% within-group repeatability
criteria. A complete study contains 27 fresh training processes.

Do not run agent-initiated tests, builds, or installs during measurement. The
interactive M1 Mac mini is not a dedicated benchmark host. Preserve failures and
timeouts without automatic retry. Do not change thresholds after seeing results.
Report compatibility, report arithmetic, and timing outcomes separately. Timing
failure prevents an accuracy claim but does not invalidate successful training or
independently verified report arithmetic.

Keep all earlier workspaces. Export only the allowlisted metadata bundle, never
weights, dataset text, raw logs, tokens, or full environment variables. This study
does not validate CUDA, external/fork access, or authorize publication.
