# External consumer workflow

Copy `examples/external-consumer/.github/workflows/traincost.yml` into `.github/workflows/traincost.yml` in a separate consumer repository. Replace `REVIEWED_UPGRADE_COMMIT_SHA` with the reviewed full upgrade commit SHA. The placeholder is not runnable. Private repositories need cross-repository Action access configured by their owners.

Add a training config at the consumer repository root, for example:

```json
{
  "model_name": "distilbert/distilbert-base-uncased",
  "gpu_type": "T4",
  "gpu_count": 1,
  "estimated_minutes_per_epoch": 3,
  "training_args": {
    "num_train_epochs": 1,
    "per_device_train_batch_size": 8
  }
}
```

The GPU price table and three-minute runtime are illustrative. Set `gpu-prices` in the workflow to use your own USD per GPU-hour rate. Open a pull request that changes `training_args.num_train_epochs`, for example from 1 to 3. The Action compares the versions from the PR commits and writes Markdown and JSON. It does not download the model or run training.

If the config is first added in the PR, the report uses illustrative defaults for the absent base. Keep the config on the base branch when you need to demonstrate an actual config-to-config comparison.

Run `python scripts/verify_external_consumer.py` from TrainCost CI to exercise both the direct Action entrypoint and the isolated bootstrap against an unrelated local Git repository. The bootstrap installs its pinned dependency and needs package-index access. Use `--direct-only` to skip the bootstrap when that access is unavailable. These normal and fork-style event payloads simulate GitHub locally; they do not verify hosted permissions or private cross-repository access.

The user made the source repository public. A separate hosted consumer verified
root and package Actions at `28b4c541ab98a840a814f6bed8d3b205ece3d4ca` without
copying the implementation. See the [run and archived reports](../../docs/external_consumer_validation.md).
This was an ordinary branch PR in a separate repository. Real fork PR permissions
remain unverified; local event simulations do not replace that check.

Inspect the Action's Step Summary in the hosted run and compare its contents with the report. A later workflow step gets a different `GITHUB_STEP_SUMMARY` file, so it cannot compare the Action step's summary using its own summary path.
