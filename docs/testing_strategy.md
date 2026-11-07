# Verify a beta candidate

Run from the repository root after installing requirements-dev.txt into a venv.

For a structured local result with the tested code/configuration fingerprint:

```bash
.venv/bin/python scripts/verify_upgrade.py --output /tmp/traincost-upgrade-evidence.json
```

This runs the offline checks below, but does not replace the networked isolated
installation, wheel distribution, history scan, or hosted consumer gates.
See [the current upgrade record](upgrade_validation.md) for measured results.

~~~bash
.venv/bin/python -m coverage run --branch --source=packages/core/src/traincost_ci_core,packages/github-action -m unittest discover -s packages/core/tests
.venv/bin/python -m coverage run --append --branch --source=packages/core/src/traincost_ci_core,packages/github-action -m unittest discover -s packages/github-action/tests
.venv/bin/python -m coverage report --omit='*/tests/*'
.venv/bin/python scripts/verify_release.py
.venv/bin/python scripts/verify_hf_corpus.py
.venv/bin/python scripts/verify_external_consumer.py
.venv/bin/python -m unittest discover examples/huggingface-demo/tests
python3 -I -S scripts/verify_no_yaml.py
.venv/bin/python -m build packages/core --no-isolation --outdir /tmp/traincost-dist
.venv/bin/python scripts/verify_wheel.py /tmp/traincost-dist
.venv/bin/python scripts/audit_secrets.py
~~~

## Release gates

- Core validation: negative and non-finite inputs, count fractions, fractional epochs, overflow, threshold and budget boundaries.
- Parser consistency: equivalent formats, duplicate keys, cycles, resource bounds, list ambiguity, and non-execution of Python expressions.
- Security: synthetic credentials in labels, sensitive subtrees, invalid syntax, report output, stdout, stderr, and dependency errors.
- Git: modifications, additions, deletions, renames, no changes, globs, braces, Unicode paths, unavailable commits, and ignored worktree changes.
- Distribution: four Python versions in CI, root/package metadata, actual isolated bootstrap, wheel installation outside the repository.
- Evidence: three deterministic fixtures and a GitHub-hosted consumer run pinned to the candidate commit SHA.
- Review regressions: known unmodeled keys cannot produce a clean report, reused runtime is flagged, epoch-only changes do not spuriously invalidate epoch time, and subcent/near-budget comparisons remain distinguishable.
- HF adapter: stopping-rule precedence, micro/global batch and accumulation, nested/root conflicts, precision flags, unknown hardware, and unsafe/unsupported settings.
- JSON: versioned schema validation, unrounded amounts, status/exclusion contracts, secret safety, and preservation of input files when output paths collide.

The HF corpus contains upstream-derived minimized examples and deliberately
constructed mutations. It is not an independent production accuracy benchmark.
Local normal/fork event simulations test Git and process boundaries, not hosted
GitHub permissions. With the private source Action's cross-repository access set to
`none`, true hosted external installation remains an unpassed gate. Do not loosen
permissions or claim a copied local Action is equivalent evidence.

Coverage is reported as measured, including branches. It does not replace scenario acceptance.
No coverage percentage alone approves publication.

## Fixture and image updates

After reviewing an intentional report change:

~~~bash
.venv/bin/python scripts/verify_release.py --update-fixtures
python3 scripts/render_reports.py
~~~

Image rendering requires Pillow. Images are local renderings of fixture excerpts, not screenshots of a GitHub run.
The original v0.1.0 PR evidence does not validate changes in this branch.
