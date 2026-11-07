# Report-only beta release readiness

Updated: 2026-11-07. Target: `v0.2.0-beta.1`, not published.

This is the historical PR #11 candidate record. [PR #13](https://github.com/Pig30nidaE/TrainCost/pull/13)
now includes the [security-upgraded multi-model study](hf_security_upgrade_study.md),
its eight-job hosted CI, and the refreshed SHA-pinned consumer PR #14. Follow
[PM status](pm_status.md) for its remaining release gates.
Do not apply the completion decision below to that newer candidate. Publication
and Action access remain unchanged.

This record supersedes the earlier review-driven upgrade's local result. The
release-readiness branch preserves the previous implementation and Mac evidence,
and incorporates the user's current main branch, including its AGENTS.md deletion.
No existing release tag is moved. No release, public transition, or access-policy
change is authorized by this record.

Decision: the report-only beta implementation and permitted validation are complete.
Public-distribution approval remains HOLD. The user retained private Action access
`none`, so independent external-repository and real fork validation have not run.
Human review and separate publication approval also remain outstanding.

Implementation candidate: `20af5724ed292066d79c8e47557baf5dd3e14a43` in
[PR #11](https://github.com/Pig30nidaE/TrainCost/pull/11). Later evidence-only commits
do not change this candidate's code/configuration fingerprint. Keep the
[consumer PR #12](https://github.com/Pig30nidaE/TrainCost/pull/12) unmerged.

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

| Check | Observed result |
| --- | --- |
| Local Python 3.11.14, 3.12.8, 3.13.12, 3.14.0 | Each has 234 unittest methods: 233 pass, one Linux-only skip |
| Hosted Linux Python 3.11-3.14 | Each has 234 methods: 230 pass, four macOS-only skips |
| Suite sizes | Core 110, Action 71, HF demo tooling 47, corpus evaluator 6 |
| Labeled upstream-derived HF corpus | 50/50 pass; constructed boundary cases, not a production accuracy benchmark |
| Canonical report fixtures | Three byte-identical reports, 4101 / 2583 / 247 bytes |
| Missing PyYAML and actual Git paths | Pass, including safe diagnostics and temporary-Git comparisons |
| Wheel and installed CLI | Fresh installation outside checkout, HF adapter and subcent JSON/Markdown pass |
| Local consumers | Normal-direct, normal-bootstrap, fork-direct, fork-bootstrap pass |
| Runtime/build advisory scan | 12 resolved packages, zero known findings with pip-audit 2.10.1 |
| Hosted combined branch-enabled coverage | 89%; tests excluded, CLI subprocess code not traced |

Repeating suites across Python versions does not create additional distinct tests.
The Linux-only process-cleanup test runs in hosted CI; macOS alias/case tests run
locally. No skipped platform-specific test is represented as an executed pass.

All four local records match this 82-file code/configuration fingerprint:

`0beebb92cc656d52e8737d5fc71029914cb7cc33c0f10fef3162995ebe2253b0`

The local records captured the dirty worktree before the candidate commit. Their
base Git SHA alone is not the tested state; the recorded file hashes identify it.
The final local wheel is `traincost_ci_core-0.2.0b1-py3-none-any.whl`, SHA-256:

`b8c3a6451e587d98ba41083d4b4bb877e03b0660f87a44e4f27b0d75a3c130a8`

The candidate's [CI run 42350182764](https://github.com/Pig30nidaE/TrainCost/actions/runs/42350182764)
passed all six jobs: the four Python versions, isolated composite action, and
runtime/build dependency audit. Each matrix job built and installed the wheel.
Known-pattern scanning covered 291 reachable Git blobs and 154 worktree entries
at the candidate, with zero findings. Evidence-only files added later are scanned
again by CI. This does not establish that arbitrary secrets or confidential text
are absent.

## Hosted consumer evidence

[Run 42350745903](https://github.com/Pig30nidaE/TrainCost/actions/runs/42350745903)
and its [verification job](https://github.com/Pig30nidaE/TrainCost/actions/runs/42350745903/job/128338140550)
passed. The consumer branch's [regression CI](https://github.com/Pig30nidaE/TrainCost/actions/runs/42350745809)
also passed. The earlier consumer run 42350307003 did not assert Summary equality;
the final run does.

| Property | Observed value |
| --- | --- |
| Event | `pull_request` |
| Root and package Action ref | `20af5724ed292066d79c8e47557baf5dd3e14a43` |
| Base SHA | `20af5724ed292066d79c8e47557baf5dd3e14a43` |
| Head SHA | `95486b6c43cf9eb2da14b164cda57f68454260aa` |
| Environment | GitHub-hosted Linux, Python 3.12.16 |
| Modified canonical config | `complete`, $0.10 -> $0.30, +200%, budget warning |
| Added native HF config through package Action | `complete`, one analysis, $0.30 PR estimate, Low confidence |
| Mixed valid/invalid HF configs | `partial`, one analysis, one excluded, $0.30 analyzed total |
| Invalid positive max_steps | `error`, zero analyses, null costs, expected step failure |
| Unsafe output symlink | Expected step failure; synthetic target unchanged; no blocked Markdown written |
| comment-posted | `false` in all four report-producing cases |
| Summary | Each of the four reports matches a runner Step Summary file byte-for-byte |
| Permissions and checkout | `contents: read`, full history, no persisted credentials, no checkout/permission error |

The two intentional failure cases use `continue-on-error`. The verifier checks
their actual step `outcome == failure`; a green overall job does not hide an
unexpected successful analysis. No raw model/data downloads or training occur.
The consumer log's known-credential-pattern scan passed without printing or
committing the raw log. Expected non-sensitive runner metadata, report paths, and
selected verification values are visible in Actions. No absence-of-all-secrets
guarantee is inferred from this scan.

Exact report paths are `/home/runner/work/_temp/traincost-release-evidence/` plus
`modified.md`, `added.md`, `partial.md`, and `invalid.md`. JSON outputs use the same
basenames with `.json`. The [downloaded metadata](evidence/release-readiness-2026-11-07/hosted/verification.json)
records every actual output; the adjacent Markdown and JSON files are preserved
from the run artifact. The added config's $0.50 base and -40% comparison use
illustrative absent-base defaults, not measured savings. Its report states this
and remains Low confidence.

Step Summary file content is verified, but visual inspection in GitHub's browser
was blocked by an unauthenticated session on this private repository. No rendered
UI inspection is claimed. Local fork payloads and this same-repository hosted run
do not establish external-repository installation or real fork permissions.

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
