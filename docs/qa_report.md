# Beta QA evidence

Updated: 2026-11-04. Publication decision: HOLD pending GitHub-hosted verification and publication approval.

## Local evidence

- Environment: macOS arm64, Python 3.14.0, PyYAML 6.0.3 in an isolated venv.
- Core: 39 tests passed. Action and bootstrap: 25 tests passed.
- Coverage.py 7.17.1, branch measurement enabled: 88% combined coverage, excluding tests.
- All three demo fixtures match byte-for-byte; metadata inputs and outputs match.
- Python -I -S dependency check: missing PyYAML gives a safe, explicit diagnostic.
- Built wheel installed and executed in a new venv outside the repository.
- Actual disposable-venv bootstrap generated the risky report successfully.
- Local known-pattern scan: 78 reachable Git blobs, no findings at this checkpoint.
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

Candidate commit SHA and workflow URLs will be recorded after the candidate is pushed and verified.
Local results do not establish the four-version Linux CI result.

Historical PR #6 validated v0.1.0 at head 913bcfe715d72b408ae3a252cc986133eab3f3d9.
It is not evidence for this beta's code.
