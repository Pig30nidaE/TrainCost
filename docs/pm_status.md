# TrainCost CI PM status

Updated: 2026-11-07.

## Decision

Technical validation passed for the report-only beta candidate. Publication remains on hold for human review and explicit approval.
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

## Completion gates

- Local regression suites, three fixtures, package installation, and isolated bootstrap: see docs/qa_report.md.
- Python 3.11-3.14 GitHub CI and SHA-pinned consumer smoke: passed; links and exact outputs are in docs/qa_report.md.
- Known-credential history scan: no known-pattern findings; repeat and manually review confidentiality before public visibility changes.
- Repository visibility, release tag push, and GitHub Release: require separate approval.
- Comment mode remains experimental and outside the beta gate.

## Next milestone

Review [implementation PR #7](https://github.com/Pig30nidaE/TrainCost/pull/7).
Keep [consumer demo PR #8](https://github.com/Pig30nidaE/TrainCost/pull/8) unmerged.
The implementation branch retains the low-cost config; only the consumer branch contains the risky demo change.
After review, select the release commit explicitly and rerun gates for any implementation change before tag approval.
Do not reuse v0.1.0 live evidence as proof of the new candidate.
No dashboard, backend, framework inference, or GPU training is included.

## Follow-up order

1. ProductArchitect: specify a Hugging Face adapter with max_steps precedence and a small labeled evaluation corpus.
2. CoreEngine and QAReview: implement and evaluate that adapter only after the canonical beta is accepted.
3. GithubAction: validate comment create/update, permissions, pagination, and concurrency separately from report-only support.
4. Integration: add user-provided measured runtime with provenance; no autonomous runtime prediction.

These are future tasks, not additions to this beta or permission to publish.

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
