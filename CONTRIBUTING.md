# Contributing

TrainCost CI analyzes training configuration changes locally. Read the [product spec](docs/product_spec.md), [architecture](docs/architecture.md), and [config reference](docs/config_reference.md) before changing behavior. Keep changes to the smallest behavior needed, and add tests for changed behavior.

## Set up

Use Python 3.11 or later:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

## Run checks

From the repository root, run:

```bash
python -m unittest discover -s packages/core/tests
python -m unittest discover -s packages/github-action/tests
python -m unittest discover -s examples/huggingface-demo/tests
python -m unittest discover -s examples/hf-config-corpus/tests
python scripts/verify_release.py
python scripts/verify_hf_demo.py
python scripts/verify_hf_corpus.py
```

The Hugging Face demo tests and corpus evaluator run offline without downloading models or starting training. GPU measurement is a separate, opt-in workflow. See [the demo README](examples/huggingface-demo/README.md) for its limits and prerequisites.

Include a short description of the problem, the change, and the checks run in the pull request. Describe untested platforms or GitHub-hosted workflows. Use synthetic data, never credentials, private configurations, or training data. Do not submit model weights or measurement caches.

## Config corpus changes

Add only minimized, labeled cases with a source repository, immutable commit, file path, license, and a description of every mutation. Mark hypothetical settings and synthetic cases. Do not describe the corpus as measured adoption or production accuracy. Run `python scripts/verify_hf_corpus.py` after editing it.

## Security reports

Follow [SECURITY.md](SECURITY.md) for suspected vulnerabilities. Do not include secrets in public issues or pull requests.
