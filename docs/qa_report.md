# Beta QA evidence

Updated: 2026-11-07. Current candidate: local and same-repository hosted checks PASS.
Independent external/fork gates NOT RUN. Publication: HOLD.

## Release-readiness follow-up

The two further P1 findings were reproduced independently: an output symlink could
overwrite a synthetic file outside the checkout, and a newly added valid HF config
was rejected because its absent base was normalized as an invalid HF input.
Independent tests then found a related pre-Git/bootstrap glob input overwrite.
All three paths now have regression coverage. No acceptance tests were weakened.

The shared output writer rejects unsafe paths and stages reports through directory
descriptors; actual empty/model-only HF files remain invalid. Broad globs cannot
overwrite a matching existing output path before file discovery succeeds.
See [release readiness](release_readiness.md) for current evidence and limits.

Code candidate: `20af5724ed292066d79c8e47557baf5dd3e14a43`.
Each local Python 3.11-3.14 run has 234 unittest methods: 233 pass and one
Linux-only skip. Hosted Linux has 230 pass and four macOS-only skips. Core has
110 methods, Action 71, demo tooling 47, and corpus evaluator 6. All 50 labeled
corpus cases pass. These are the same tests repeated across versions.
Hosted combined branch-enabled coverage is 89%, excluding tests and untraced
subprocess code. It is not an accuracy or release-approval metric.

Candidate [CI run](https://github.com/Pig30nidaE/TrainCost/actions/runs/42350182764)
passed all six jobs, including the isolated composite action and strict dependency
audit. The final wheel installed and ran outside the checkout. The runtime/build
audit found zero known advisories in 12 resolved packages; optional ML dependencies
are not included in that audit. See the release-readiness record for consumer
outputs, exact SHAs, report artifacts, and the remaining browser inspection limit.

The user retained private Action access `none`; true external-consumer/fork hosting
is not silently replaced by local simulations or a same-repository PR.

## Earlier review-driven upgrade, superseded

The uncommitted worktree based on `fa687ad297b8a9b488255bc4e304297494f76fa9`
fixes unsupported-setting false-safe reports, stale runtime assumptions, and subcent
display. It adds a bounded opt-in HF adapter, installed CLI, versioned JSON output,
an independent-consumer harness, and a 50-case upstream-derived boundary corpus.

Independent QA acceptance covers the original findings plus alias conflicts,
root/nested stopping-rule bypasses, path/symlink/hardlink input preservation,
invalid CLI arguments, redaction, and non-finite aggregate results.

Each of Python 3.11.14, 3.12.8, 3.13.12, and 3.14.0 passed Core 89, Action 48,
HF demo 46 (one Linux-only skip), and corpus evaluator 6 tests. All 50 labeled
corpus cases passed. Final wheel installation outside the checkout, all four local
normal/fork direct/bootstrap modes, and existing report fixtures also passed.
Measured combined branch-enabled coverage, excluding tests, is 85%; the measurement
does not trace the tested CLI subprocesses. It is not a release approval metric.

See [the current validation record](upgrade_validation.md) for exact source hashes,
four interpreter evidence files, commands, limitations, and remaining owners.
This code has no new hosted run evidence. Actual external/fork Action access remains
unvalidated: the source is private with access level `none`, and that setting was
not changed. No release, remote push, tag push, merge, or public transition occurred.

## Historical beta evidence

The following PASS records belong to the named older commits, not the current worktree.

Code candidate: 45f6652ebbff1a48162b58738e4ef1974c244232.
Later evidence and installation-example edits do not change this tested code.

## PR review follow-up

Review of eb6f01c reproduced a remaining P1: malformed YAML scalar tags could bypass
the safe error boundary, leak a synthetic credential to stderr, and discard otherwise valid files.
Earlier successful runs at e21f1f4 did not cover this path and do not establish that the issue was fixed.

The current candidate converts constructor failures into value-free ConfigError diagnostics with
line and column numbers. Existing duplicate-key and resource-limit diagnostics remain intact.
Six new test methods cover explicit bool/int/float/timestamp failures, mapping keys and sensitive subtrees,
valid explicit tags, actual CLI outputs on base/head errors, and mixed-file PR analysis using real Git commits.
The focused reproduction now returns exit 2 with error outputs and no secret leakage;
the mixed-file case returns exit 0 with partial status and retains the valid estimate.

## Local evidence

- Environment: macOS arm64, Python 3.14.0, PyYAML 6.0.3 in an isolated venv.
- Core: 43 tests passed. Action and bootstrap: 30 tests passed, including real temporary-Git integration cases.
- Coverage.py 7.17.1, branch measurement enabled: 88% combined coverage, excluding tests.
- All three demo fixtures match byte-for-byte; metadata inputs and outputs match.
- Python -I -S dependency check: missing PyYAML gives a safe, explicit diagnostic.
- Wheel installation and the disposable-venv bootstrap were rechecked by the hosted runs below.
- Local known-pattern scan after the code candidate: 127 reachable Git blobs and 67 worktree entries, no findings.
  This scan is not a guarantee that arbitrary credentials or confidential content are absent.

Commands are maintained in docs/testing_strategy.md and scripts/verify_release.py.

## Reproduced defects now covered

Synthetic tokens in model_name and gpu_type, malformed YAML containing tokens, sensitive subtrees,
negative and non-finite inputs, fractional-count truncation, partial epoch preservation,
conflicting fields, duplicate keys, cycles, missing dependencies, deleted configs,
unchanged glob matches, brace patterns, renames, Unicode paths, unavailable SHAs, and ignored worktree edits.

Tests use synthetic credentials and never real keys.
Comment create/update has mocked API tests only; no live-comment claim is made.

## GitHub evidence

- Implementation: [PR #7](https://github.com/Pig30nidaE/TrainCost/pull/7), kept draft for review.
- Candidate CI: [run 41782284598](https://github.com/Pig30nidaE/TrainCost/actions/runs/41782284598).
  Python 3.11, 3.12, 3.13, and 3.14 plus the isolated composite job all passed.
  Each matrix job ran both suites, checked all fixtures and metadata, tested the missing dependency,
  built the wheel, installed/imported it outside the repository, and scanned known credential patterns.
  The Python 3.14 job measured 88% branch-enabled coverage; fixture sizes were 4101, 2583, and 247 bytes.
- SHA-pinned consumer: [PR #8](https://github.com/Pig30nidaE/TrainCost/pull/8), intentionally unmerged.
- Consumer report: [run 41782394357](https://github.com/Pig30nidaE/TrainCost/actions/runs/41782394357),
  [verification job](https://github.com/Pig30nidaE/TrainCost/actions/runs/41782394357/job/126416714565), passed.
- Consumer CI: [run 41782394335](https://github.com/Pig30nidaE/TrainCost/actions/runs/41782394335), all five jobs passed.

| Consumer evidence | Observed value |
| --- | --- |
| Event | pull_request |
| Action ref and base SHA | 45f6652ebbff1a48162b58738e4ef1974c244232 |
| Head SHA | c3c1315a1fe9511e0e429f37998594972e9986e4 |
| Runner | GitHub-hosted Ubuntu 26.04.1, ubuntu-26.04 image |
| Dependency | PyYAML==6.0.3 in the disposable venv |
| report-path | /home/runner/work/TrainCost/TrainCost/report.md |
| comment-posted | false |
| analysis-status | complete |
| Costs | Base $0.04, PR $21.33, increase +48,662% |
| Warnings | All seven expected risk warnings checked by the workflow |
| Summary | Verification found the generated report bytes in the runner Step Summary file |
| Permissions and checkout | contents: read; fetch-depth: 0; persist-credentials: false; no failures |

The consumer downloaded the action using owner/repository@full-SHA, not a local action path.
It used a branch of the same private repository, not a separately authorized private consumer repository or a fork.
The system Python patch version was not printed by this consumer workflow; the separate four-version CI is recorded above.
No raw config, token, credential, or full environment dump was observed in the reviewed consumer job log.
The Action's GITHUB_TOKEN entry was empty. A known-pattern scan of that log found no matches.
GitHub's normal runner metadata and the intentionally verified non-sensitive paths and SHAs are visible.

## Remaining limitations

- Human PR review, confidentiality review, and separate publication approval are still required.
- Known-pattern scanning cannot establish the absence of arbitrary secrets or confidential text.
- Live comments, fork permission behavior, and cross-repository private-action access were not validated.
- Prices and runtime are inputs or illustrative assumptions, not measured cloud bills.
- The public v0.2.0-beta.1 tag and GitHub Release have not been created.

Historical PR #6 validated v0.1.0 at head 913bcfe715d72b408ae3a252cc986133eab3f3d9.
It is not evidence for this beta's code.

## DistilBERT tooling follow-up (2026-11-07)

This is separate from the beta release assessment above. The experiment is not yet run.
Candidate `243ed0889473180b50fdbc704ede5fd116d3527a` leaves core and Action code unchanged.
Its final hosted CI passed 43 core, 30 Action, and 39 demo tests on Python 3.11-3.14,
including actual Linux parent-SIGKILL cleanup. The SHA-pinned config-only consumer
also passed. Local macOS skipped that one Linux-specific test and passed the other 38.

Tests cover the independent oracle, mocked Trainer mapping and finite-value guards,
balanced subsets, frozen calibration, strict live config types, safe failure bundles,
evidence immutability, watchdog process groups, CLI report/status/Summary, and static
cost fixture. They do not establish actual Transformers/CUDA installation or timing accuracy.
The dependency install dry run resolved 63 hashed distributions; no GPU stack was
installed on the user PC by these checks.

See [the validation evidence record](hf_validation_status.md) for exact run links,
SHAs, outputs, remaining Summary inspection, and all GPU gates marked NOT RUN.
No PR merge, release, tag push, or repository visibility change was performed.

## Mac-only execution follow-up (2026-11-07)

At the user's request, Windows testing is deferred. The separate Mac MPS smoke ran
real DistilBERT fine-tuning on balanced 64-example IMDb subsets. Both the initial
1/3-epoch pair and a rerun after evidence-control fixes passed 8/24 updates, finite
gradient/weight checks, encoder updates, and independent report arithmetic.

The updated local suites passed 119 tests and skipped one Linux-only test. Known-pattern
secret scanning, package installation, and existing fixtures passed. See [Mac results](macos_validation.md)
for preserved raw metadata, exact code/lock hashes, timings, and the 42.965% / 7.496%
single-base extrapolation errors. These are compatibility checks, not a CUDA calibration
study, product-wide timing accuracy evidence, or a release approval.
