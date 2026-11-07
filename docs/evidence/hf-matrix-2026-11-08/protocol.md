# Committed-source follow-up study

Registered before measurement on 2026-11-08.

Purpose: replace the missing executable-source provenance of the historical study
with a new, commit-bound measurement. The previous 27 observations and their
timing failures remain published. This is not a retry-until-pass procedure.

The measured commit will be recorded automatically in `bundle/source.json` before
model preparation. The controller refuses changed or untracked execution source.
Its source fingerprint must remain unchanged through completion. Registration
requires a full Git-object replay of every execution-file hash at that commit.

Use all three pinned profiles in `examples/hf-model-matrix/profiles.json` and the
existing protocol without changes: 64 balanced train and 64 test rows, length 128,
batch 8, FP32 MPS, three one-epoch calibrations, then three one-epoch base and three
three-epoch PR measurements per model. Keep the existing 20% median error and 15%
within-group repeatability thresholds. The study includes 27 training processes.

No repository tests, builds, package installs, or other agent-initiated compute
jobs will run on this Mac while the study executes. The Mac remains an interactive
desktop, not an isolated benchmark host. Ordinary OS/user activity cannot be
excluded. Do not claim controlled thermal or scheduling conditions.

Use the existing hash-pinned macOS lock in `.venv-hf-matrix`. Keep the complete
workspace in ignored `.hf-validation-matrix-2026-11-08`; archive only the allowlisted
metadata bundle. Do not publish model weights, raw reviews, or subprocess logs.

Run exactly once. Preserve failures and inconclusive attempts. Stop on watchdog
limits; do not alter the protocol or discard observations after seeing results.
Compatibility, report arithmetic, and timing outcomes remain separate. A timing
failure does not establish runtime prediction accuracy or prevent the limited
claim that a real configuration was trained and its cost arithmetic checked.

This study does not authorize a release, tag push, permission expansion, or
repository visibility change.
