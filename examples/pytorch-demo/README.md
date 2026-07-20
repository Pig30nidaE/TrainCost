# PyTorch Demo

Minimal PyTorch-like config scenario for TrainCost CI.

- `config.yaml` is the canonical config path for the live pull request demo.
- `configs/base-config.yaml` is the same cheap baseline config used for local dry runs.
- `configs/risky-config.yaml` simulates a pull request that increases epochs, switches to A100, doubles GPU count, disables mixed precision, and lowers batch size.
- `.github/workflows/traincost-ci.yml` runs TrainCost CI with `comment-mode: "false"` and writes `report.md`.
- `expected-report.md` is the expected local dry-run report.

The standalone demo workflow uses the intended release ref, `Pig30nidaE/TrainCost@v0.1.0`.

For a live PR demo, start with `config.yaml` on the base branch, then replace its contents with `configs/risky-config.yaml` on a branch named `expensive-training-config`.

Run a local dry run from the repository root:

```bash
python3 packages/github-action/traincost_action.py \
  --base-config examples/pytorch-demo/configs/base-config.yaml \
  --head-config examples/pytorch-demo/configs/risky-config.yaml \
  --gpu-prices "T4=0.35,A10G=1.2,A100=3.20" \
  --budget-limit "5" \
  --comment-mode "false" \
  --report-path "report.md"
```

The command writes `report.md` and should match `examples/pytorch-demo/expected-report.md`. In a pull request run, the action adds a `Config: config.yaml` line above the same risk report.
