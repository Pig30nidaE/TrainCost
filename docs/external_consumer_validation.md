# External consumer validation

Recorded 2026-11-08 KST. The source repository is public following the user's
visibility change. The user approved creating a public validation repository and
running test PRs. Source PR merges, tag pushes, and release publication remain
outside that approval.

## Tested identity

| Field | Observed value |
| --- | --- |
| Source | `Pig30nidaE/TrainCost` |
| Action candidate | `28b4c541ab98a840a814f6bed8d3b205ece3d4ca` |
| Consumer | [Pig30nidaE/TrainCost-consumer-validation](https://github.com/Pig30nidaE/TrainCost-consumer-validation) |
| Consumer repository ID | `1449646378` |
| PR | [#1](https://github.com/Pig30nidaE/TrainCost-consumer-validation/pull/1), draft, unmerged |
| Base | `bb0b5b974e7e702a9232ea3434dfb62da30b3c70` |
| Head | `01e73957f09b473cc0d133e7bc67c333530030f0` |
| Run | [42403549313](https://github.com/Pig30nidaE/TrainCost-consumer-validation/actions/runs/42403549313), attempt 1, success |
| Event | `pull_request` |
| Environment | GitHub-hosted Linux, Python 3.12.16 |
| Permissions | `contents: read` |
| Head repository is fork | `false` |
| Head repository differs from base | `false` |

Both root and package Actions use the full candidate SHA. The consumer checkout
has no `action.yml` or `packages/core`; the workflow asserts their absence.
No model download, GPU training, self-hosted runner, or user-provided secret is
part of this test. No checkout or permission error occurred.

## Observed contracts

| Case | Status | Analyzed / excluded | Base / PR estimate | Result |
| --- | --- | --- | --- | --- |
| Modified canonical config | `complete` | 1 / 0 | $0.10 / $0.30 | +200%, budget warning |
| Added native HF config, package Action | `complete` | 1 / 0 | $0.50 / $0.30 | Explicit absent-base assumptions, Low confidence |
| Valid and invalid native HF configs | `partial` | 1 / 1 | $0.50 / $0.30 | Total covers analyzed configs only |
| Invalid native HF config | `error` | 0 / 1 | null / null | Actual step outcome `failure`, no analysis |
| Symlink output destination | Rejected | Not applicable | Not applicable | Actual step outcome `failure`, synthetic target unchanged |

The added config's base estimate is illustrative, not observed savings. All rates
are hypothetical. The four report-producing cases returned `comment-posted=false`.
For each case, `report-path` was
`/home/runner/work/_temp/traincost-release-evidence/<case>.md` and
`report-json-path` was the same path with `.json`, where `<case>` is `modified`,
`added`, `partial`, or `invalid`. Exact strings are retained in
[verification.json](evidence/external-consumer-2026-11-08/reports/verification.json).
Each Markdown report matched a runner Step Summary file byte-for-byte. This is
not a rendered browser inspection of the Summary.

## Archived evidence

[Reports](evidence/external-consumer-2026-11-08/reports/verification.json),
[workflow](evidence/external-consumer-2026-11-08/workflow.yml),
[run API snapshot](evidence/external-consumer-2026-11-08/run.json), and
[PR API snapshot](evidence/external-consumer-2026-11-08/pr.json) are preserved.
The snapshots include selected public identity/status fields, not tokens or full
environment dumps. The workflow does not print tokens or enumerate environment
variables. Workflow-generated logs may include runner paths and its explicitly
declared test inputs; this is not a claim of zero environment values in logs.

From the source checkout with its development environment installed:

```bash
.venv/bin/python docs/evidence/external-consumer-2026-11-08/verify.py
```

The checker compares fixed expected run, PR, repository IDs, base/head SHAs, Action
pins, workflow Git blob hash, report paths, statuses, and costs. It requires PyYAML.
Replaying an archive does not rerun GitHub or independently attest how it was produced.
Do not run the checker with Python's `-O` flag, which disables assertions.

## Remaining gate

This run proves consumption from another repository, not a PR from a fork.
The user will provide a fork PR from another account. Before accepting its run,
review changed files and workflow, confirm `head.repo.fork=true` and different
base/head repository IDs, and check the same outputs under fork permissions.
Do not enable `pull_request_target`, add write permissions, or register the user's
GPU computer as a runner. Keep validation PRs unmerged.

Candidate PR #13 remains separate from the public default branch. No new tag or
release was created as part of this validation.
