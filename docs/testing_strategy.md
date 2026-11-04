# Verify a beta candidate

Run from the repository root after installing requirements-dev.txt into a venv.

~~~bash
.venv/bin/python -m coverage run --branch --source=packages/core/src/traincost_ci_core,packages/github-action -m unittest discover -s packages/core/tests
.venv/bin/python -m coverage run --append --branch --source=packages/core/src/traincost_ci_core,packages/github-action -m unittest discover -s packages/github-action/tests
.venv/bin/python -m coverage report --omit='*/tests/*'
.venv/bin/python scripts/verify_release.py
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
