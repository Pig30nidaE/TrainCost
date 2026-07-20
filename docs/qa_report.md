# TrainCost CI MVP QA Report

## Scope Reviewed

Reviewed `AGENTS.md`, `README.md`, `docs/product_spec.md`, core package code/tests, and GitHub Action package code/tests.

Focus areas:

- Invalid YAML.
- Missing config fields.
- No config file changed.
- Base config unavailable.
- Budget exceeded.
- GPU type changed.
- GPU count increased.
- Precision changed from `bf16` to `fp32`.
- Multiple config files changed.
- Report wording that could overclaim exact prediction.
- Secret/token logging.

## Bugs Found

1. Invalid YAML in the dependency-free YAML fallback could be silently accepted when an inline list or dict scalar was malformed, such as `epochs: [1, 2`. That could produce a misleading low-confidence report instead of a skipped-analysis note.

Fix applied:

- Malformed inline YAML scalars now raise `ValueError`.
- PyYAML parse failures are normalized to `ValueError` so the action handles invalid YAML consistently.

## Tests Added

Core tests added in `packages/core/tests/test_core_engine.py`:

- Invalid YAML raises `ValueError`.
- Missing fields render low-confidence report wording.
- Sensitive-looking config values are not rendered in the Markdown report.
- Report wording uses estimated-cost language and avoids exact prediction phrases.

GitHub Action tests added in `packages/github-action/tests/test_traincost_action.py`:

- Invalid YAML returns a skipped-analysis note without crashing.
- Missing base config still analyzes the head config.
- Globbed config path with no changed files produces a graceful no-config report.
- Multiple changed config files produce a combined report.
- Comment failure does not print the GitHub token.

Existing tests already covered:

- YAML, JSON, and Python config parsing.
- Cost estimation formula.
- Budget exceeded warning.
- Cost increase warning.
- GPU type and GPU count warnings.
- Precision regression warning.
- Missing-field low-confidence behavior.
- Markdown report generation.
- Local GitHub Action dry-run output.

## Docs and Wording Review

README and product docs consistently describe costs as estimates or risk signals. They explicitly say TrainCost CI does not know the exact cloud bill and must not claim exact GPU cost prediction.

No overclaiming wording was found in the reviewed docs. The report output uses headings such as `Estimated cost` and confidence language rather than exact prediction language.

Created `docs/testing_strategy.md` to document the current test layers, commands, manual QA checklist, and known gaps.

## Security and Privacy Review

No code path was found that prints GitHub tokens, environment variables, cloud credentials, or config secret values.

Observed behavior:

- GitHub tokens are used only in the HTTP `Authorization` header for comment requests.
- Action logs print status messages and report paths, not token values.
- Sensitive-looking config keys are reported by key name only.
- Sensitive-looking config values are not included in the report.

## Test Results

Baseline before changes:

- `python3 -m unittest discover packages/core/tests`: 12 tests passed.
- `python3 -m unittest discover packages/github-action/tests`: 3 tests passed.

After changes:

- `python3 -m unittest discover packages/core/tests`: 15 tests passed.
- `python3 -m unittest discover packages/github-action/tests`: 8 tests passed.

Final demo QA pass:

- `python3 -m unittest discover packages/core/tests`: 15 tests passed.
- `python3 -m unittest discover packages/github-action/tests`: 8 tests passed.
- `python3 packages/github-action/traincost_action.py --base-config examples/pytorch-demo/configs/base-config.yaml --head-config examples/pytorch-demo/configs/risky-config.yaml --gpu-prices "T4=0.35,A10G=1.2,A100=3.20" --budget-limit "5" --comment-mode "false" --report-path /private/tmp/traincost-qa-demo-report.md`: completed and wrote the report.
- `/private/tmp/traincost-qa-demo-report.md` matched `examples/pytorch-demo/expected-report.md` byte-for-byte.
- SHA-256 for both reports: `8bc3a3b454238d90afaca5dcb28bab0e14c2a72b274750ff9cded89e511327dc`.
- Byte count for both reports: 2588 bytes.

Final demo documentation QA:

- `examples/pytorch-demo/config.yaml` is the canonical live PR path and matches `examples/pytorch-demo/configs/base-config.yaml`.
- The risky PR fixture is `examples/pytorch-demo/configs/risky-config.yaml`.
- `docs/demo_script.md`, `examples/pytorch-demo/README.md`, and the demo workflow consistently describe replacing `examples/pytorch-demo/config.yaml` with the risky config contents for a live PR demo.
- `README.md`, `docs/github_action_usage.md`, `packages/github-action/README.md`, `examples/pytorch-demo/README.md`, and the demo workflow mark `OWNER/traincost-ci@v1` as a placeholder rather than an actual released ref.
- README, demo docs, and expected report use estimated/risk/confidence language and do not claim exact GPU cost prediction.
- No dashboard, Kubernetes, MLflow, W&B, Comet, OpenCost, SaaS backend, auth, billing, team management, runtime prediction, or real GPU training feature was added.

GitHub Action PR-path smoke test:

- Created a temporary local git repository with a base commit containing `config.yaml` and a head commit changing the same `config.yaml` path.
- Ran the action entrypoint with a synthetic `pull_request` event, `comment-mode: false`, `config-path: config.yaml`, and `GITHUB_OUTPUT` pointed at a temporary output file.
- Confirmed `git diff` detected `config.yaml`.
- Confirmed the report showed base-to-head changes such as `epochs: 5 -> 50`, proving the base version was loaded separately from the head version.
- Confirmed the report included `Config: config.yaml`, estimated base cost `$0.04`, estimated PR cost `$21.33`, budget/cost/GPU/precision/batch-size warnings, and high-confidence wording.
- Confirmed action outputs were written as `report-path=<temporary report path>` and `comment-posted=false`.
- Repeated the same PR-style check through the package-local action path used by `packages/github-action/action.yml`.

Required validation on this pass:

- `python3 -m unittest discover packages/core/tests`: 15 tests passed.
- `python3 -m unittest discover packages/github-action/tests`: 8 tests passed.
- `python3 packages/github-action/traincost_action.py --base-config examples/pytorch-demo/configs/base-config.yaml --head-config examples/pytorch-demo/configs/risky-config.yaml --gpu-prices "T4=0.35,A10G=1.2,A100=3.20" --budget-limit "5" --comment-mode "false" --report-path /private/tmp/traincost-github-action-report.md`: completed and wrote the report.

Action metadata validation:

- Root `action.yml` is valid for released usage when the action is published from the repository root because it runs `python3 "$GITHUB_ACTION_PATH/packages/github-action/traincost_action.py"`.
- `packages/github-action/action.yml` remains valid for local package usage because it runs `python3 "$GITHUB_ACTION_PATH/traincost_action.py"`.
- The demo workflow keeps `OWNER/traincost-ci@v1` as a documented placeholder because no real owner/ref is known in this repository.

## Remaining Risks

- Comment posting still needs a live pull request smoke test.
- Changed-file detection passed in a temporary git pull-request-style smoke test, but the demo workflow should still be observed once in an actual GitHub-hosted pull request run with `comment-mode: false`.
- The fallback YAML parser is intentionally limited to common config mappings and scalar values.
- Base-unavailable analysis is graceful, but its low-confidence output should be reviewed in a real PR for readability.

## Release Readiness Recommendation

Demo ready.

The local demo is self-contained, unit tests pass, the dry-run report matches the expected fixture byte-for-byte, placeholder action refs are labeled, and docs avoid exact-cost overclaims. Do not tag v0.1.0 yet; the remaining blocker is a live GitHub-hosted pull request smoke test that confirms the workflow writes the report and action outputs in GitHub Actions.

## Recommended Next Fixes

1. Run a live GitHub-hosted demo PR with `comment-mode: false`.
2. Confirm `report-path` and `comment-posted=false` outputs in that workflow run.
3. Decide whether invalid complex YAML should always skip analysis or whether PyYAML should become an explicit dependency for broader YAML support.
