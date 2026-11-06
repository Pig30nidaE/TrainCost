# Verify the Hugging Face config in a consumer PR

This check compares the canonical DistilBERT config across two Git commits. It uses a pinned TrainCost Action and does not run model training. The six minutes per epoch and RTX 3060 hourly price are inputs to the estimate, not measurements.

## Prepare the PR

1. Push the reviewed `codex/hf-distilbert-validation` branch with the workflow and baseline config. Confirm `examples/huggingface-demo/config.json` has `epochs: 1`.
2. Create `codex/hf-distilbert-consumer-smoke` from that branch in the same repository.
3. Change only `epochs` from `1` to `3` in `examples/huggingface-demo/config.json`. Commit and push the branch.
4. Open a pull request from `codex/hf-distilbert-consumer-smoke` into `codex/hf-distilbert-validation`. Keep the PR unmerged while collecting evidence.

The workflow runs only when the canonical config changes in a PR from that same-repository branch. It skips the strict consumer job on the implementation PR, where the config may not exist in the base commit.

## Check the run

Open the **Hugging Face config consumer validation** workflow run for the consumer PR. The **Verify consumer report** step must pass. It checks the following:

- `analysis-status=complete`, `comment-posted=false`, and a nonempty report at `report-path`.
- Config path `examples/huggingface-demo/config.json` and `epochs: 1 -> 3`.
- Estimated costs of `$0.10` for the base and `$0.30` for the PR, with a `+200%` increase.
- Budget, cost increase, epoch increase, and mixed precision warnings.

The action writes its report to the run's Step Summary. Inspect the **Run TrainCost CI** step's summary in GitHub and compare it with the verified report values. GitHub gives each step a different summary file, so the verification step cannot read the action step's summary through its own `GITHUB_STEP_SUMMARY` path.

## Record evidence

Record the PR URL, workflow run and job URLs, event, runner, base and head SHAs, pinned action SHA, report path, outputs, costs, warnings, and the observed Step Summary. Record any failed assertion or unavailable summary instead of claiming a pass. The workflow requires `contents: read`, full Git history, and access to the pinned action and its Python dependencies.
