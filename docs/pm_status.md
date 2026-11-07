# TrainCost CI PM status

Updated: 2026-11-08.

## Current decision

The optional ML dependency blocker is resolved for the reviewed replacement locks.
The [security-upgraded study](hf_security_upgrade_study.md) measured commit
`26613f604b9a25cecd65a6f8835dfd3ca8f5997e`: 27 fresh runs across DistilBERT, BERT,
and ALBERT passed training, report arithmetic, and fixed timing criteria. All eight
[hosted CI jobs](https://github.com/Pig30nidaE/TrainCost/actions/runs/42400274167)
passed, including both complete ML-lock audits. All 81 observations across three
studies remain registered, including historical failures and limitations.

This supports a report-focused beta with three reviewed sequence-classification
profiles. It is not support for every HF task or a general runtime predictor.
QAReview replayed source/evidence and found no additional blocking issue. The
post-registration local suite passed, and the refreshed SHA-pinned
[same-repository consumer](https://github.com/Pig30nidaE/TrainCost/actions/runs/42401267868)
and its eight-job CI passed. Evidence-only changes do not alter the measured
Core/Action implementation.

The user made the source repository public and approved a separate public consumer
repository. Candidate `28b4c541ab98a840a814f6bed8d3b205ece3d4ca` passed all eight
[final CI jobs](https://github.com/Pig30nidaE/TrainCost/actions/runs/42402097394)
and the [external consumer run](https://github.com/Pig30nidaE/TrainCost-consumer-validation/actions/runs/42403549313).
Root and package Actions were downloaded by full SHA from a checkout without the
TrainCost implementation. Complete, partial, error, unsafe-output rejection, and
report/Summary checks passed. This closes the cross-repository installation gate,
not the real fork gate. [Exact identity and results](external_consumer_validation.md).

The user will create a fork PR from another account and provide its URL. Next,
review that PR's changes and workflow, verify distinct base/head repository IDs,
and observe its GitHub-hosted run. Do not replace it with a simulated event or the
ordinary branch PR already tested. Candidate PR #13 and consumer PRs remain
unmerged. PR merge, tag push, and release publication still require separate
approval. No agent-initiated source visibility or Action access change occurred.

Final CI exposed a Linux test-observer exit race at `40d17a0`. The test-only fix
`18f209c` adds six regressions and passed all eight
[hosted jobs](https://github.com/Pig30nidaE/TrainCost/actions/runs/42401955448).
Local coverage is now 309 methods: 308 passed, one Linux-only skip. QAReview also
checked the procfs-unavailable case. The measured execution fingerprint remains
unchanged; no additional GPU study was needed. See the QA record for the preserved
failed attempt and correction.

## Earlier security follow-up, superseded

The active user goal now includes an actual release after meeting the open-source,
multi-model validation, and portfolio requirements. It is not achieved yet.
The preceding goal turn made progress by implementing and measuring the matrix;
its final compatibility result is not the whole release objective.

New blocking finding: optional ML-lock auditing reported 16 advisory entries in
four packages, 12 distinct vulnerabilities after duplicate-CVE review. The
original audit is preserved under the committed study's evidence directory.
Core/Action runtime-build CI does not audit this separate training environment.
Integration owns lock upgrades, QAReview owns exposure review, and PM owns model
metadata guards and renewed committed-source compatibility evidence. No blanket
advisory suppression or new GPU run on the old environment is planned.
The replacement macOS and CUDA locks now report zero known advisories across
52 and 71 packages respectively. CI now audits these separate locks. A new
preregistered study must verify the replacement dependencies before this blocker
can be closed; the old training results cannot stand in for it.

Current release gates are a reviewed immutable candidate, current hosted CI,
commit-bound real-model evidence, documented support/limitations, independent
installation/fork evidence, confidentiality review, and publication. Private
Action access remains `none`; permission/visibility changes have not been
authorized. [PR #13](https://github.com/Pig30nidaE/TrainCost/pull/13) now contains
the upgrade. Measured commit `01ddafcda9a2545460f067dbb7c154f9661c2b97` passed all
six [hosted CI jobs](https://github.com/Pig30nidaE/TrainCost/actions/runs/42396945740).
The old failed timing study remains preserved and cannot be relabeled
or used as proof of stable runtime prediction.

The [commit-bound study](hf_committed_study.md) completed 27 new real training runs,
all PASS for training contracts, reports, and timing. The versioned source inventory
is verified against immutable Git blobs; dirty execution source is rejected before
training. QAReview identified nested-module and inventory-version issues, and the
implementation includes their fixes and regressions. Historical evidence remains
registered, including timing failures and its missing executable snapshot.

Evidence registration at `d6fd314` passed hosted CI and the SHA-pinned consumer
[PR #14](https://github.com/Pig30nidaE/TrainCost/pull/14). Keep that PR unmerged.
Subsequent dependency/security edits need their own validation. Remaining release
work is the ML dependency fix and compatibility rerun, final candidate review,
independent external/fork validation when permitted, confidentiality review, and
publication approval. Same-repository or local simulations cannot replace the
external/fork gate. No permission expansion, tag push, release, or merge occurred.

## Earlier matrix snapshot, superseded

The current local `codex/hf-model-matrix` upgrade supersedes the candidate snapshot
below for HF validation. DistilBERT, BERT, and ALBERT each completed nine real MPS
fine-tuning runs and correct Action reports. The timing study did not fully pass:
DistilBERT and BERT failed repeatability; ALBERT passed. See the
[full study and regression evidence](hf_model_matrix.md). This supports a bounded,
multi-architecture text-classification validation claim, not a general runtime
predictor or every HF task.

The HF microbatch warning and demo subcent-calibration regressions are fixed.
CoreEngine, Integration, and QAReview worked on separate files/reviews; no new
agents were created. The changes remain local on a branch based on PR #11's
`5983297a22352fe25078cd35a340a930d3663539`. The previous hosted runs do not cover
this upgrade. Next: review the new diff, then validate the selected candidate in
hosted CI under existing permissions. Do not merge, publish, push tags, or expand
Action access as a consequence of this study. Public distribution remains HOLD.

## Previous candidate snapshot

The latest [release-readiness record](release_readiness.md) supersedes the upgrade
snapshot below. Both reproduced P1 paths and the follow-up glob diagnostic overwrite
are fixed and covered by independent acceptance tests. Runtime/build dependencies
were updated after an advisory scan. Candidate
`20af5724ed292066d79c8e47557baf5dd3e14a43` passed four-version local and hosted
CI, wheel installation, dependency audit, and a same-repository SHA-pinned
consumer PR covering complete, partial, error, and unsafe-output rejection.

Implementation [PR #11](https://github.com/Pig30nidaE/TrainCost/pull/11) is ready
for human review. Keep consumer [PR #12](https://github.com/Pig30nidaE/TrainCost/pull/12)
unmerged. The baseline config remains unchanged on the implementation branch.
Evidence-only commits after the candidate do not change its code/config fingerprint.

The user explicitly retained private Action access `none` on 2026-11-07. No separate
consumer repository, permission expansion, public transition, release, or tag push
is permitted. Public-distribution approval remains HOLD until the outstanding
external consumer/fork gate and separate publication approval are satisfied.

## Earlier upgrade snapshot, superseded

Current upgrade: local regression validation passed; release readiness remains on hold.
The P1 false-safe and stale-runtime findings, subcent display, bounded HF adapter,
CLI/JSON contract, labeled corpus, consumer harness, and contribution documentation
are implemented in the uncommitted worktree based on `fa687ad297b8a9b488255bc4e304297494f76fa9`.
See [current upgrade evidence](upgrade_validation.md) for exact tests and source hashes.
Python 3.11-3.14 each passed 189 tests with one Linux-only skip; the 50-case corpus passed.
New hosted CI and a true cross-repository/fork consumer are not yet validated.
The private Action has cross-repository access `none`; no permission or visibility
change was made to bypass that gate. No release, tag push, commit, or remote push
was performed in this upgrade. Existing changes and Mac evidence were preserved.

The next owner is GithubAction for a reviewed, committed candidate's hosted evidence
when an authorized consumer can access it, followed by QAReview and PM. Local fork
payload simulations and the old hosted runs do not satisfy that gate.

## Historical beta decision

The following approval and completion records apply to earlier commits only.
Technical validation passed for that report-only beta candidate. Publication remained on hold for human review and explicit approval.
The historical v0.1.0 tag exists at 107ddebce40cec45e932c875dafa1b8b46ba05fb and will not be moved.
The target is a report-only v0.2.0-beta.1 candidate. The repository remains private.
The tested code SHA is 45f6652ebbff1a48162b58738e4ef1974c244232.

PR #7 review found an additional YAML constructor error path that exposed input values.
That P1 is fixed at the parser boundary and covered by new CLI and real-Git regression tests.
The updated four-version CI and SHA-pinned consumer run passed; evidence is in docs/qa_report.md.
This resolves the reproduced finding, not a blanket guarantee that no other defects exist.

The previous release approval was limited to the canonical v0.1.0 demo.
A broader review reproduced secret disclosure, invalid numerical estimates, and deleted-file analysis.
This branch fixes those issues and incorporates the existing uncommitted CI, license, pricing explanation, and rename work.

## Scope and ownership

CoreEngine owns validated config extraction, provenance, estimation, and safe reports.
GithubAction owns commit-based discovery, isolated execution, runner outputs, and candidate smoke tests.
QAReview owns regression and release evidence. Integration owns the three demos.
ProductArchitect and PM own support boundaries, documentation, and the publication decision.
No new agents are required.

## Historical completion gates

- Local regression suites, three fixtures, package installation, and isolated bootstrap: see docs/qa_report.md.
- Python 3.11-3.14 GitHub CI and SHA-pinned consumer smoke: passed; links and exact outputs are in docs/qa_report.md.
- Known-credential history scan: no known-pattern findings; repeat and manually review confidentiality before public visibility changes.
- Repository visibility, release tag push, and GitHub Release: require separate approval.
- Comment mode remains experimental and outside the beta gate.

## Earlier milestone

Review [implementation PR #7](https://github.com/Pig30nidaE/TrainCost/pull/7).
Keep [consumer demo PR #8](https://github.com/Pig30nidaE/TrainCost/pull/8) unmerged.
The implementation branch retains the low-cost config; only the consumer branch contains the risky demo change.
After review, select the release commit explicitly and rerun gates for any implementation change before tag approval.
Do not reuse v0.1.0 live evidence as proof of the new candidate.
No dashboard, backend, framework inference, or GPU training is included.

## Earlier follow-up order (superseded)

1. ProductArchitect: specify a Hugging Face adapter with max_steps precedence and a small labeled evaluation corpus.
2. CoreEngine and QAReview: implement and evaluate that adapter only after the canonical beta is accepted.
3. GithubAction: validate comment create/update, permissions, pagination, and concurrency separately from report-only support.
4. Integration: add user-provided measured runtime with provenance; no autonomous runtime prediction.

The later user-approved upgrade implemented the bounded HF adapter before publication;
the current scope and remaining gates are in upgrade_validation.md. Comments and
measured-runtime provenance remain separate follow-ups, not permission to publish.

## User-approved validation follow-up

A separate `codex/hf-distilbert-validation` branch adds an opt-in DistilBERT/IMDb experiment,
not a Hugging Face parser or a change to the core/Action contract. The user will operate an
RTX 3060 12GB under WSL2. No GPU run is authorized on this Mac or on a PR runner.
Integration owns the runner and reproducible inputs, QAReview owns an independent oracle
and tooling tests, and GithubAction owns the report-only consumer workflow.
See [the separate validation record](hf_validation_status.md) for actual evidence and pending gates.
PR #7 and consumer PR #8 remain unmerged. No publication approval follows from this work.

Implementation [PR #9](https://github.com/Pig30nidaE/TrainCost/pull/9) and report-only
consumer [PR #10](https://github.com/Pig30nidaE/TrainCost/pull/10) are draft and unmerged.
The final validation tooling candidate is `243ed0889473180b50fdbc704ede5fd116d3527a`.
Hosted Python 3.11-3.14 CI passed with 43 core, 30 Action, and 39 demo tests.
The SHA-pinned consumer reported complete / false and $0.10 -> $0.30 (+200%).
Next owner: the user, for WSL2 dependency installation and preflight, followed by
explicit local GPU stages. PM must review the returned evidence before judging the
experiment; rendered hosted Summary inspection and every GPU measurement remain pending.

The user subsequently deferred Windows execution and approved real Mac mini training.
The separate [Mac validation](macos_validation.md) passed model loading, MPS fine-tuning,
and cost arithmetic on a 64-example smoke pair. This is not the CUDA acceptance study:
there were no repeated runs or independent calibration, and simple 3x extrapolation
overestimated observed time by 42.965%. A second compatibility run after evidence-control
fixes overestimated by 7.496%; both results are retained without choosing a preferred run.
RTX 3060 verification and publication remain on hold.
