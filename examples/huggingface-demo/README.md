# DistilBERT CUDA validation

This opt-in experiment connects a real single-GPU fine-tuning run to the existing TrainCost report. It is not a Hugging Face adapter or a runtime predictor. Do not run it in a pull request or CI. No download or training occurs until the commands below are run by the operator.

For the separate, smaller Mac compatibility smoke, see [Mac validation](../../docs/macos_validation.md).
It has its own dependency lock and runner; it does not replace the CUDA experiment below.

## Prerequisites

- Windows with WSL2 Ubuntu, one NVIDIA RTX 3060 with 12 GiB VRAM, a working WSL NVIDIA driver, at least 8 GiB currently free GPU memory, and Python 3.12.
- Enough disk space for the CUDA dependencies, model, dataset, caches, and temporary training files. Installation and `prepare` require network access. Confirm the [IMDb dataset terms](https://huggingface.co/datasets/stanfordnlp/imdb) before downloading; its Hub card lists the license as `other`.
- Run from a trusted checkout. Never run unreviewed PR code on the GPU. Use a new private workspace directory, not a symlink; do not put credentials in its path. Do not share the workspace cache or model files.

Install the NVIDIA WSL-compatible driver on the Windows host. **Do not install a Linux NVIDIA display driver inside WSL**; follow the [NVIDIA CUDA on WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html) for the supported setup.

Create an isolated environment and install the pinned Linux x86-64 CUDA wheels:

```bash
python3.12 -m venv "$HOME/traincost-hf-venv"
. "$HOME/traincost-hf-venv/bin/activate"
python -m pip install --require-hashes --only-binary=:all: -r examples/huggingface-demo/requirements.lock
```

The lock includes the official PyTorch CUDA wheel and transitive dependency hashes. Installation downloads packages; it does not download the model or dataset. Check `nvidia-smi` before starting and stop unrelated GPU workloads yourself. The runner does not stop other processes.

## Static report, without training

```bash
python packages/github-action/traincost_action.py \
  --base-config examples/huggingface-demo/fixtures/base.json \
  --head-config examples/huggingface-demo/fixtures/risky.json \
  --gpu-prices 'RTX3060=1.00' --comment-mode false \
  --report-path /tmp/traincost-hf-static-report.md
```

The fixed 6 minutes/epoch fixture yields $0.10 to $0.30, +200%, with budget and FP32 warnings. The $1/GPU-hour price and $0.20 budget are hypothetical arithmetic inputs, not an RTX 3060 cloud quote, electric bill, or actual spend.

## Local measurement

Choose a new directory and run the stages in order. `preflight` validates the environment and static report. `prepare` downloads pinned model and IMDb Parquet revisions, selects balanced subsets, and runs an eight-update smoke test. `calibrate` performs three independent full one-epoch runs and fixes the median-derived inputs and budget before `verify`. `verify` alternates three fresh base and three fresh PR runs, then evaluates each on a separate balanced test subset. `bundle` copies only allowlisted evidence, not the cached model or dataset.

```bash
WORK="$HOME/traincost-hf-run-001"
python examples/huggingface-demo/run_validation.py preflight --workspace "$WORK"
python examples/huggingface-demo/run_validation.py prepare --workspace "$WORK"
python examples/huggingface-demo/run_validation.py calibrate --workspace "$WORK"
python examples/huggingface-demo/run_validation.py verify --workspace "$WORK"
python examples/huggingface-demo/run_validation.py bundle --workspace "$WORK"
```

Use `bundle` after a recorded failure or timeout as well; its manifest reports `FAIL` or `INCONCLUSIVE`, not `PASS`. Each training process has a 600-second watchdog; the persistent total budget is 3,600 seconds, including process startup and evaluation. GPU OOM or failed checks are failures; timeout or insufficient remaining budget is inconclusive. The runner does not retry or shrink a batch. A failed, interrupted, altered, or partially completed workspace cannot be resumed or overwritten: investigate and start with a fresh workspace. If a hard interruption leaves `.traincost.lock`, verify no process is running; use a new workspace rather than removing evidence.

## Interpretation

The live PR config is `config.json`: it matches the base fixture on the implementation branch and the risky fixture in the demo PR. The two fixtures differ only in epochs. Run the measurement stages from the implementation commit; the runner explicitly measures the fixed base/PR fixture pair, then uses each generated measured config for both `Trainer` and the Action. Only strict TrainCost keys are accepted; arbitrary HF, distributed, and model metadata fields are rejected. Both configs use batch size 8, accumulation 1, fixed length 128, FP32, AdamW at 2e-5, a constant schedule, and no checkpoint or external reporting. The model and dataset revisions, seed, subset sizes, and timeout policy are in `manifest.json`.

Each measurement is the CUDA-synchronized wall time of the entire `Trainer.train()` call, including first-step overhead, callbacks, and training logging, but excluding model/data loading, tokenization, evaluation, post-training parameter validation, and saving. Loading, tokenization, post-training parameter validation, evaluation, peak allocated VRAM, accuracy, and F1 are recorded separately. The smoke checks finite loss and gradients and a changed encoder parameter; full runs check finite logged loss and gradient norm when logged, and every run checks all floating model parameters after training. Full gradient checking is not repeated on every full-run step to avoid distorting timed runs. Accuracy and F1 are descriptive, not a quality gate. Text present in the selected training subset is excluded from the selected test subset by SHA-256 before deterministic balanced test sampling.

The independent oracle compares the median predicted and observed full-training times. A run passes when each group's three measurements are within 15% of its median and both base and PR median time errors are at most 20%. The same oracle independently checks the unrounded assumed-price arithmetic. Differences due to GPU load or first-epoch overhead are possible: no result is a billing measurement or an accuracy guarantee. TrainCost's `High` confidence means fields were supplied, not that timing is accurate.

`bundle/bundle-manifest.json` lists hashes and the experiment status. Inspect the allowlisted JSON and Markdown before sharing. It includes model/dataset selection indices and hashes, package and GPU metadata, but no dataset text, tokens, environment dump, or model weights. Known credential-pattern detection is a precaution, not a complete secret scanner.
