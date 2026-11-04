# Report-only beta checklist

## Implemented and locally verified

- [x] Canonical YAML, JSON, and Python literal analysis.
- [x] Safe numeric validation, conflict rejection, and sensitive-value exclusion.
- [x] Explicit assumptions, input paths, and illustrative price sources.
- [x] Actual Git modifications, additions, deletions, and renames.
- [x] Complete, partial, skipped, and error outputs.
- [x] Automatic Step Summary and isolated dependencies.
- [x] Three deterministic demo fixtures and local report images.
- [x] Wheel build and installation outside the repository.
- [x] Unit and integration tests with measured coverage.
- [x] Local known-credential pattern scan.

## Evidence required before publication

- [x] Python 3.11-3.14 GitHub-hosted CI verified for e21f1f4fd445e64e24f7596ec7ff1cf2f2c5b54c.
- [x] Consumer workflow pinned to that candidate SHA verified, including Step Summary.
- [ ] Human review of the hardening PR and confidential repository content.
- [ ] Explicit approval to change repository visibility and publish the beta.

Live comment posting is experimental and not a checked-off capability.
See docs/qa_report.md for the current evidence rather than inferring readiness from this checklist.
