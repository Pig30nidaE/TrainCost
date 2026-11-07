# Report-only beta checklist

Updated 2026-11-08. Runtime candidate `a907b78423cd18b5e7a8f53f5d092fcba6df77e9`.
See [final review](final_review.md) and [QA evidence](qa_report.md) for the checks
behind these marks. Historical candidates do not substitute for this source.

## Implementation and verification

- [x] Canonical YAML, JSON, and Python literal analysis; explicit bounded HF adapter.
- [x] Safe numeric validation, conflict rejection, and sensitive-value exclusion.
- [x] Explicit assumptions, input paths, and illustrative price sources.
- [x] Actual Git changes, renames, and divergent-branch merge-base comparisons.
- [x] Complete, partial, skipped, and error outputs.
- [x] Automatic Step Summary and isolated dependencies.
- [x] Three deterministic demo fixtures and local report images.
- [x] Wheel and sdist build and installation outside the repository.
- [x] Three actual model profiles; 108 preserved observations across four studies.
- [x] Unit and integration tests with measured coverage.
- [x] Local known-credential pattern scan.

- [x] Candidate Python 3.11-3.14 hosted CI and complete dependency audits.
- [x] Separate public consumer and actual fork PR at the exact candidate SHA.
- [x] Read-only fork permissions and report/Summary equality.
- [x] Source made public by the user; no agent-initiated visibility/access change.

## Before publication

- [ ] Final evidence-registration CI at the PR head.
- [ ] Human review and explicit approval to merge PR #13.
- [ ] Select and verify the release commit without changing tested runtime files.
- [ ] Explicit approval for the annotated beta tag push and GitHub prerelease.

Keep consumer PRs unmerged and the existing `v0.1.0` tag unchanged. No PyPI upload
is included. Live comments, CUDA/WSL2 execution, and general HF task coverage are
not checked-off capabilities. A known-pattern scan is not a general confidentiality guarantee.
