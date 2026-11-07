# Beta QA evidence

## Resumed final review

QAReview reproduced two findings at `50ce946`. A direct base-tip/head diff selected
configs changed only on the target branch. Canonical `precision=fp32` with
`mixed_precision=true` also incorrectly raised `precision_risk`. The new tests
failed before the fixes. The Action now resolves one merge base and uses it for
both selection and base blobs, with the SHA in Action notes. Core respects the
explicit mixed-precision flag and only infers disabled precision from FP32 when
the flag is missing.

Six real-Git regressions cover unrelated target changes, both-side modifications,
target-side deletion, PR rename, unrelated histories, and multiple merge bases.
Two precision tests cover enabled, disabled, and unspecified flags. The aggregate
overflow test now mocks the new boundary and asserts its actual overflow diagnostic,
so an unrelated Git error cannot satisfy it. Local full regression passed with
317 methods, one Linux-only skip. Hosted evidence below applies to earlier SHAs
until the corrected candidate is verified separately.

## Real fork consumer follow-up, 2026-11-08

[Consumer PR #2](https://github.com/Pig30nidaE/TrainCost-consumer-validation/pull/2)
is from `anyhogs/TrainCost-consumer-validation`, repository ID `1449662675`, into
base repository ID `1449646378`. It changes the same three synthetic config files
as PR #1, not code or workflow. Both PRs have head SHA `01e7395`; that shared SHA
alone cannot identify a fork test.

[Run 42405161652, attempt 2](https://github.com/Pig30nidaE/TrainCost-consumer-validation/actions/runs/42405161652/attempts/2)
passed after the reviewed pending run was approved. Attempt 1's `action_required`
status is retained in the operator approval record. Repository policy was not
changed. The runner permission group contains only Contents read and Metadata read.
The downloaded artifact identifies PR 2, the fork repository, and distinct base/head
repositories. Root and package Actions still pin `28b4c541ab98a840a814f6bed8d3b205ece3d4ca`.

All four report-producing cases returned the expected complete/partial/error
statuses and `comment-posted=false`. Unsafe output was rejected; the synthetic
target was unchanged. Markdown matched runner Step Summary files. The eight
report files are byte-identical to the ordinary external PR's reports, with fork
identity recorded separately. Expected negative steps returned exit 2; their
actual failed outcomes are asserted before the verification step succeeds.

The [archive checker](evidence/external-consumer-2026-11-08/verify.py) now checks
both runs against fixed run IDs, PR numbers, repository IDs, fork flags, SHAs, and
workflow pins. See [full evidence and limits](external_consumer_validation.md).
Two local archive regressions passed, including rejection of 12 identity/contract
mutations. QAReview independently checked GitHub run attempt 2 and its fork head
repository ID, observed the successful verification job, and replayed the archive.
It found no additional blocking issue within this fork-validation scope.
This closes the real fork report-only gate, not live comments or publication.

## External consumer follow-up, 2026-11-08

After the user made the source public, the authorized separate
[consumer PR #1](https://github.com/Pig30nidaE/TrainCost-consumer-validation/pull/1)
passed [run 42403549313](https://github.com/Pig30nidaE/TrainCost-consumer-validation/actions/runs/42403549313).
Both Action entrypoints pin candidate `28b4c541ab98a840a814f6bed8d3b205ece3d4ca`.
The consumer contains no Core/Action implementation. Read-only permissions were
sufficient for complete, partial, error, and unsafe-output cases; reports matched
runner Step Summary files and all four comment outputs were false.

The [external validation record](external_consumer_validation.md) preserves exact
base/head SHAs, output paths, reports, workflow, and reduced GitHub API snapshots.
QAReview found two archive-checker issues: exact comparison with floating-point
200%, and lack of an independent workflow pin check. The checker now uses a tight
tolerance and verifies all five Action references plus the reviewed workflow Git
blob hash. These corrections do not change the hosted run or production code.
QAReview reran the corrected checker and independently confirmed the workflow
blob. A local negative check rejected eight mutations to identity, status, costs,
comment output, and workflow pins. Known-pattern scanning found zero matches in
617 reachable blobs and 440 worktree entries before the final documentation edits.
That scan is not proof that arbitrary credentials or confidential content are absent.

This was an ordinary branch PR in a separate consumer repository, not a fork PR.
The real fork gate was pending at that point and is covered by the follow-up above.
Candidate PR #13 is unmerged; no new tag or
release has been published. Earlier private/access-blocked entries below are
historical snapshots, not the current repository state.

## Final CI process-observer correction

Evidence commit `40d17a0` had a real
[Python 3.13 CI failure](https://github.com/Pig30nidaE/TrainCost/actions/runs/42401555797).
The Linux parent-death test observed process exit between `stat.exists()` and
`stat.read_text()`, which raised `ProcessLookupError`. The failure is preserved in
[structured evidence](evidence/hf-matrix-security-2026-11-08/ci-observer-failure.json),
not hidden by rerunning the same job.

All three test observers now use one process-state check. Linux ESRCH during the
read means terminated; a missing procfs entry requires a second PID check. A live
PID with an unreadable procfs entry fails instead of being declared dead. Permission
and other unexpected errors still fail. macOS does not interpret its absent
`/proc` as process termination. Six
deterministic regressions cover this distinction. Production watchdogs and all
measured execution-source files are unchanged. New GPU measurement is unnecessary
for this test-only correction. The [local full regression](evidence/hf-matrix-security-2026-11-08/process-observer-python312.json)
passed 308 of 309 methods, with one Linux-only skip. HF demo tests increased from
70 to 76; other suite counts are unchanged. QAReview confirmed the procfs correction
after identifying the missing-procfs ambiguity. Commit `18f209c` then passed all
eight [hosted CI jobs](https://github.com/Pig30nidaE/TrainCost/actions/runs/42401955448),
including the real Linux parent-death test on Python 3.11-3.14. The earlier failed
attempt remains recorded. This correction changes tests only, not measured code.

## Security-upgraded real-model study

The [new study](hf_security_upgrade_study.md) measured source `26613f6` with the
replacement ML lock and metadata boundary. All 27 fresh training runs passed;
each model's reports and preregistered timing checks passed. Registered evidence
replay now verifies all 81 observations across three studies, preserving the first
study's timing failures and unavailable source snapshot. The measured source passed
all eight [CI jobs](https://github.com/Pig30nidaE/TrainCost/actions/runs/42400274167).

The [pre-measurement local regression](evidence/hf-matrix-2026-11-08/security-upgrade-python312.json)
ran 303 methods: 302 passed and one Linux-only check was skipped. Suite sizes:
Core 113, Action 71, HF demo 70, matrix 43, corpus evaluator 6. The labeled corpus
passed 50/50; fixtures, local consumer simulations, and historical evidence replay
also passed. The [post-registration regression](evidence/hf-matrix-security-2026-11-08/local-python312.json)
repeated the full suite successfully with all three registered studies. QAReview
independently replayed the evidence and eight registration tests, compared all 28
source files to Git blobs, and verified measured environment/lock agreement. No
additional blocking finding was reported. Replay checks records; it does not
independently attest execution or approve a release.

The new [consumer run](https://github.com/Pig30nidaE/TrainCost/actions/runs/42401267868)
pins root and package Actions to `26613f6`. Its [actual outputs](evidence/hf-matrix-security-2026-11-08/hosted-consumer/verification.json)
record complete/partial/error behavior, false comment outputs, unchanged synthetic
symlink target, and report/Summary equality. Its separate eight-job CI passed.
This is a same-repository PR, not the blocked external/fork distribution gate.

## Optional ML dependency audit follow-up

The preserved [pip-audit 2.10.1 result](evidence/hf-matrix-2026-11-08/ml-dependency-audit.json)
reports 16 entries in datasets 4.8.5, fsspec 2026.2.0, torch 2.9.1, and
transformers 4.57.6. QAReview found 12 distinct vulnerabilities after duplicate-CVE
review. Some concern APIs outside the pinned sequence-classification workflow;
this is not a blanket no-impact conclusion. Dependencies and pre-load metadata
guards have been updated. The successful training and hosted reports below do
not approve the old optional ML environment for release.

The replacement [macOS](evidence/hf-matrix-2026-11-08/updated-macos-audit.json) and
[CUDA](evidence/hf-matrix-2026-11-08/updated-cuda-audit.json) audits cover all 52 and
71 lock entries, with zero known advisories and no suppressions. QAReview found no
concrete defect in the new advisory parser and CUDA preflight checks; seven focused
tests passed. No CUDA runtime execution was performed. The replacement model
verification is now recorded in the new study above.

See [exposure review](ml_dependency_security.md) for the distinct advisories and
assessment limits. QAReview inspected the new metadata boundary and compared its
six upstream fixtures with the reviewed hashes; it found no further blocking issue
in that narrow review. The [local boundary regression record](evidence/hf-matrix-2026-11-08/metadata-boundary-python312.json)
contains 294 methods: 293 pass, one Linux-only skip. It still uses the old lock and
does not establish compatibility with the planned dependency upgrades.

## Commit-bound matrix (2026-11-08)

The new [study](hf_committed_study.md) measured commit
`01ddafcda9a2545460f067dbb7c154f9661c2b97`. All 27 real MPS runs passed the
training contract, Decimal/report checks, and unchanged timing criteria. The
historical failed observations below remain registered. Git-based source replay
rejects modified, missing, or symlinked execution source and uses a versioned
inventory so later policy changes do not invalidate old studies.

The measured candidate passed all six
[hosted CI jobs](https://github.com/Pig30nidaE/TrainCost/actions/runs/42396945740).
That run predates the new bundle registration; follow-up evidence edits need CI.
The new local study is not CUDA evidence, an external consumer, or a public release.

The follow-up [local Python 3.12 record](evidence/hf-matrix-2026-11-08/local-python312.json)
contains 284 unittest methods: 283 passed and one Linux-only test was skipped.
Suite sizes are core 113, Action 71, HF demo 53, matrix 41, and corpus evaluator 6.
The 50-case corpus, fixtures, missing-YAML diagnostic, local normal/fork simulations,
and replay of both registered studies also passed. Git source replay was performed
by the implementation chat. QAReview separately compared bundle counts, hashes,
documented medians/errors, and retained limitations without rerunning the suite;
it found no blocking documentation discrepancy. Known-pattern scanning reported
zero findings in 409 reachable blobs and 317 worktree entries before the final
documentation additions, not a comprehensive confidentiality audit.

## Multi-model upgrade (2026-11-07)

The current local branch is `codex/hf-model-matrix`. See
[the measured study](hf_model_matrix.md) for immutable model revisions and the
metadata-only bundle. DistilBERT, BERT, and ALBERT completed 27 real MPS training
runs. All actual Trainer settings, encoder-update/gradient checks, Decimal cost
checks, Action outputs and Step Summary comparisons passed. Timing repeatability
failed for DistilBERT and BERT; ALBERT passed. Overall timing remains FAIL.

Local Python 3.11-3.14 each passed 266 tests with one Linux-only skip, plus the
50-case labeled corpus and static/consumer checks. New regressions cover physical
HF microbatch warning semantics, subcent calibration, model-profile safety,
parent watchdog termination, calibration freeze, condition hashes, exact Action
outputs, incomplete statuses, and nested bundle metadata rejection. QAReview
identified the status/bundle issues; PM added and ran their regressions. The
post-measurement export hardening does not replace the recorded training source
fingerprint with the final source fingerprint.

No new hosted PR, external-consumer permission test, CUDA run, release, tag push,
public transition, or Action access change occurred. Earlier results below are
historical and do not supply those missing gates for this worktree.

## Final MVP demo QA (2026-11-07)

The canonical config-only demo passed local QA in an existing Python 3.12.8
environment with PyYAML 6.0.3 and jsonschema 4.25.1. The worktree contained
pre-existing code and fixture changes; this result applies to that worktree,
not to an independently identified release commit.

- `python3 -m unittest discover packages/core/tests`: 113 tests passed.
- `python3 -m unittest discover packages/github-action/tests`: 71 tests passed,
  including local Git-based PR-path cases.
- The requested Action dry run returned exit 0 and `analysis-status: complete`.
  `cmp /private/tmp/traincost-qa-demo-report.md examples/pytorch-demo/expected-report.md`
  returned 0: the files match byte-for-byte.
- The initial commands under system Python 3.14 failed because PyYAML and
  jsonschema were absent. The core run reported 19 failures and 7 errors; the
  Action run reported 25 failures and 9 errors; the dry run returned exit 2.
  The successful reruns used `/private/tmp/traincost-hf-tests/bin` on `PATH`.
- `examples/pytorch-demo/config.yaml` matches the base fixture byte-for-byte.
  The in-repository example selects that path; the standalone workflow selects
  `config.yaml` at the consumer repository root.
- `OWNER/traincost-ci@v1` does not appear in the repository. The standalone
  workflow uses a full historical candidate SHA, not that placeholder. The
  reviewed demo wording calls costs estimates and distinguishes input confidence
  from billing accuracy.
- Inspection of the Action and CLI log statements found no direct token or
  environment dump. The suites include synthetic-secret cases. This is not a
  guarantee that all possible secrets or logging paths are covered.

No new live GitHub PR was run for this worktree. Historical same-repository
PR smoke evidence appears below and in the current release-readiness record;
it does not verify the present uncommitted changes or an external consumer.
The source repository is private with Action access set to `none`, so an
independent external consumer or real fork remains unvalidated. Human review
and separate publication approval also remain open. The historical v0.1.0 tag
already exists and must not be moved. Recommendation: **Demo ready** for the
local config-only scenario, not ready for a new public release.

Scope review: the Action analyzes configs without executing training. The
repository nevertheless contains a separate opt-in real-training validation
example, and its Mac smoke has run; therefore a claim that the entire repository
contains no real GPU training would be false. This QA did not add, launch, or
verify that experiment. No dashboard or SaaS backend was identified in this review.

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
