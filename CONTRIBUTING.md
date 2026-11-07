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
python -m unittest discover -s examples/hf-model-matrix/tests
python scripts/verify_hf_evidence.py
```

The Hugging Face demo tests and corpus evaluator run offline without downloading models or starting training. GPU measurement is a separate, opt-in workflow. See [the demo README](examples/huggingface-demo/README.md) for its limits and prerequisites.

Include a short description of the problem, the change, and the checks run in the pull request. Describe untested platforms or GitHub-hosted workflows. Use synthetic data, never credentials, private configurations, or training data. Do not submit model weights or measurement caches.

## Config corpus changes

Add only minimized, labeled cases with a source repository, immutable commit, file path, license, and a description of every mutation. Mark hypothetical settings and synthetic cases. Do not describe the corpus as measured adoption or production accuracy. Run `python scripts/verify_hf_corpus.py` after editing it.

For real pretrained models, use the [model-matrix contribution procedure](examples/hf-model-matrix/README.md#contribute-another-model).
Keep offline contract tests separate from opt-in local training. Submit immutable
model revisions and metadata-only evidence, including failures. Do not commit
weights, raw datasets, tokens, or claim a new task is supported from its model name.
Register a study in `examples/hf-model-matrix/evidence-index.json` with the bundle
manifest hash, measured source identity, exact model coverage, and its real
outcome. Failed timing must remain failed. The replay gate checks all registered
artifacts and rejects unlisted files; it never starts a GPU job.

Optional training dependencies are not Core/Action requirements. Audit both full
locks before a new experiment, using `pip-audit==2.10.1` in a separate environment:

```bash
python scripts/audit_ml_dependencies.py --lock macos --output /tmp/traincost-macos-audit.json
python scripts/audit_ml_dependencies.py --lock cuda --output /tmp/traincost-cuda-audit.json
```

These checks query public advisory data without installing GPU packages. Do not
suppress advisories to keep CI green. A lock change requires fresh compatibility
evidence, not relabeling a previous model study.

## Security reports

Follow [SECURITY.md](SECURITY.md) for suspected vulnerabilities. Do not include secrets in public issues or pull requests.
