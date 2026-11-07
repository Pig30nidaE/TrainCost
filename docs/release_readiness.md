# Report-only beta release readiness

Updated: 2026-11-07. Target: `v0.2.0-beta.1`, not published.

This record supersedes the earlier review-driven upgrade's local result. The
release-readiness branch preserves the previous implementation and Mac evidence,
and incorporates the user's current main branch, including its AGENTS.md deletion.
No existing release tag is moved. No release, public transition, or access-policy
change is authorized by this record.

## Fixed release blockers

- Output paths no longer follow PR-controlled leaf or parent symlinks. A shared
  output boundary opens directories with no-follow descriptors, stages both reports,
  and replaces each file atomically. Hardlinks and input/output collisions are
  rejected. Normal diagnostics and bootstrap-failure diagnostics use the same writer.
- A valid new HF configuration is analyzed when Git establishes that no base file
  exists. The absent base has explicit illustrative defaults and low confidence;
  an actual empty or model-only HF input is still rejected.
- Existing report destinations matching a config glob are protected before Git
  discovery and dependency installation. Git/setup errors cannot overwrite them.
  Broad config globs should use explicit report paths outside the checkout.
- The dependency audit identified advisories in the old build requirements.
  Setuptools is now pinned to 84.1.0 and wheel to 0.46.2. The strict runtime/build
  audit checks 12 resolved packages and reports zero known findings. CI repeats it.

The two output files are not one filesystem transaction. An operating-system
failure between replacements can leave one updated file; the command fails rather
than claiming completion. Linux and macOS are supported; Windows users use WSL2.

## Validation evidence

The four interpreter records in [the evidence directory](evidence/release-readiness-2026-11-07/)
identify the exact code/configuration fingerprint, test counts, skips, and commands.
They do not count Markdown or screenshots as source fingerprint inputs.

The intended release checks include:

1. Core, Action, optional demo tooling, and corpus evaluator regression suites.
2. Fifty labeled, minimized upstream-derived HF cases and three fixed reports.
3. Explicit missing-PyYAML behavior and actual temporary-Git comparisons.
4. Wheel build, isolated installation, and the installed CLI outside this checkout.
5. Normal and fork-style local consumers through direct and isolated-bootstrap paths.
6. Known-pattern credential scan and runtime/build dependency advisory scan.
7. GitHub-hosted Python 3.11-3.14 CI and a full-SHA consumer PR for the candidate.

Local fork payloads do not establish GitHub fork permissions. Historical hosted runs
for earlier candidates do not establish that the latest changes pass. Hosted run
links and the exact candidate SHA must be recorded after observing completion.

## User-controlled publication gate

The user explicitly chose to keep Action access at `none` on 2026-11-07. The source
repository remains private. Do not create a separate consumer repository or widen
access as a workaround. Same-repository SHA-pinned hosted tests can be performed,
but independent cross-repository installation and a real external fork run remain
unverified under this constraint.

This prevents a claim that every agreed public-distribution gate is complete.
No amount of additional local testing changes that permission boundary. The
remaining gate must be reported honestly, not silently removed from acceptance.

Comment creation/update remains experimental. RTX 3060 calibration is deferred.
The Mac training records are compatibility evidence, not general runtime accuracy.
Prices are illustrative or user supplied; the tool does not predict actual bills.

## Reproduce locally

```bash
python -m pip install -r requirements-dev.txt
python scripts/verify_upgrade.py --output /tmp/traincost-release-evidence.json
python scripts/verify_external_consumer.py
python -m build packages/core --no-isolation --outdir /tmp/traincost-release-dist
python scripts/verify_wheel.py /tmp/traincost-release-dist
python scripts/audit_secrets.py
```

Run the dependency advisory scan in a separate environment with `pip-audit==2.10.1`:

```bash
python -m pip_audit -r requirements-dev.txt --strict --progress-spinner off
```

It sends package names and versions to the advisory service, not repository code.
Use a fresh distribution directory for each wheel build. The optional GPU demo's
ML environment is separate from the report-only package and runtime/build audit.
