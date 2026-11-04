# TrainCost CI PM status

Updated: 2026-11-04.

## Decision

Publication is on hold pending beta verification and explicit publication approval.
The historical v0.1.0 tag exists at 107ddebce40cec45e932c875dafa1b8b46ba05fb and will not be moved.
The target is a report-only v0.2.0-beta.1 candidate. The repository remains private.

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
- Python 3.11-3.14 GitHub CI and SHA-pinned consumer smoke: record actual results before approval.
- Known-credential history scan: run locally before public visibility changes.
- Repository visibility, release tag push, and GitHub Release: require separate approval.
- Comment mode remains experimental and outside the beta gate.

## Next milestone

Review the hardening PR and its exact candidate SHA. Approve the beta only after the recorded gates pass.
Keep risky demo PRs unmerged. Do not reuse v0.1.0 live evidence as proof of the new candidate.
No dashboard, backend, framework inference, or GPU training is included.
