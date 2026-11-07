# External consumer validation

Recorded 2026-11-08 KST. The source repository is public following the user's
visibility change. The user approved creating a public validation repository and
running test PRs. Source PR merges, tag pushes, and release publication remain
outside that approval.

## Corrected candidate follow-up

Runtime candidate `a907b78423cd18b5e7a8f53f5d092fcba6df77e9` fixes PR merge-base
selection, report baseline labels, and explicit precision precedence. The old
candidate results below are retained as history, not substituted for this rerun.

With the user's explicit approval, the existing ordinary and fork test branches
were updated from `01e73957f09b473cc0d133e7bc67c333530030f0` to
`fe7e9778257a24a5efa884c94fb08d7b5068281d`. The only diff was six SHA replacements
in the workflow: five Action references and the recorded candidate field. Test
assertions, config inputs, permissions, and repository policy were unchanged.

| Field | Ordinary PR #1 | Actual fork PR #2 |
| --- | --- | --- |
| Run | [42406963444](https://github.com/Pig30nidaE/TrainCost-consumer-validation/actions/runs/42406963444) | [42406970081](https://github.com/Pig30nidaE/TrainCost-consumer-validation/actions/runs/42406970081/attempts/2) |
| Attempt / result | 1 / success | 2 / success |
| Head repository ID | `1449646378` | `1449662675`, `anyhogs/TrainCost-consumer-validation` |
| Event | `pull_request` | `pull_request` |
| Python | 3.12.16 | 3.12.16 |

Both use base `bb0b5b974e7e702a9232ea3434dfb62da30b3c70` and the new head above.
The reviewed workflow Git blob is `dbd81fc78d2599db80973b1179041cd8f8856cc8`.
Fork attempt 1 required approval. The specific run was approved after reviewing
that SHA-only diff; no approval policy was relaxed. Actual token permissions were
Contents read and Metadata read. No checkout or permissions error occurred after
approval. The expected negative-step failures and third-party Action deprecation
notices remain distinguishable from unexpected failures.

Every contract in the table below passed again. All four comment outputs were
false and reports matched runner Step Summary files byte-for-byte. The modified
report contains `Merge-base estimate: $0.10`, `PR-head estimate: $0.30`, and the
exact merge-base SHA in diagnostics. The new reports and reduced identity records
are in [the final archive](evidence/final-consumer-2026-11-08/reports/verification.json)
and [its fork archive](evidence/final-consumer-2026-11-08/fork/reports/verification.json).

```bash
.venv/bin/python docs/evidence/final-consumer-2026-11-08/verify.py
```

Both old and corrected archive replays run in CI. They check recorded evidence,
not a new hosted execution or the browser-rendered Summary. No source PR or
consumer PR was merged, and no tag or release was published.

## Earlier tested identity, preserved

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
.venv/bin/python -m unittest discover -s docs/evidence/external-consumer-2026-11-08 -p 'test_verify.py'
```

The checker compares fixed expected run, PR, repository IDs, base/head SHAs, Action
pins, workflow Git blob hash, report paths, statuses, and costs. It requires PyYAML.
Replaying an archive does not rerun GitHub or independently attest how it was produced.
Do not run the checker with Python's `-O` flag, which disables assertions.

## Real fork follow-up

The ordinary branch run above did not prove fork behavior. The user subsequently
opened [PR #2](https://github.com/Pig30nidaE/TrainCost-consumer-validation/pull/2)
from another account. Its three synthetic config changes and unchanged workflow
were reviewed before approving the pending run.

| Field | Observed value |
| --- | --- |
| Run | [42405161652, attempt 2](https://github.com/Pig30nidaE/TrainCost-consumer-validation/actions/runs/42405161652/attempts/2), success |
| Job | `128501877714`, consumer |
| Head repository | `anyhogs/TrainCost-consumer-validation`, ID `1449662675` |
| Base repository | `Pig30nidaE/TrainCost-consumer-validation`, ID `1449646378` |
| Event | `pull_request`, PR 2 |
| Fork identity | `head_is_fork=true`, `distinct_head_repository=true` |
| Base/head SHA | Same base/head as PR #1 above |
| Action candidate | `28b4c541ab98a840a814f6bed8d3b205ece3d4ca` |
| Environment | GitHub-hosted Linux, Python 3.12.16 |
| Actual token permissions | Contents read, Metadata read |

Attempt 1 stopped at `action_required` without executing jobs. After review, the
specific run was approved; attempt 2 passed. No repository policy was loosened.
The head SHA alone is not sufficient evidence because PRs 1 and 2 share it.
The [fork artifact](evidence/external-consumer-2026-11-08/fork/reports/verification.json)
records PR 2 and its fork identity. Reduced [run](evidence/external-consumer-2026-11-08/fork/run.json)
and [PR](evidence/external-consumer-2026-11-08/fork/pr.json) API snapshots independently
record the distinct repository IDs. The archive checker requires these exact values,
checks attempt 2, and checks the reviewed workflow blob and recorded permissions.

All contracts in the observed-contracts table passed again. All eight Markdown/JSON
reports are byte-identical to the first run. Each report matched a runner Step
Summary file, and every comment output was false. The two exit-2 annotations are
expected negative tests: the workflow checks their actual `failure` outcomes despite
`continue-on-error`. No checkout or permission issue occurred after approval.

The runner also emitted Node 20 Action deprecation and ubuntu-latest migration
notices. They did not fail this run. Updating those third-party pins is separate
maintenance and is not claimed complete by this evidence.

The same archive command above now checks both runs. It remains an offline replay,
not a fresh execution or a rendered Summary inspection. The permission record is
a narrow log excerpt, not a token or full environment dump. No `pull_request_target`,
write permission, self-hosted runner, model download, or GPU training was added.
Two local regression tests accept both original archives and reject 12 mutations,
including replacing the fork identity with the ordinary PR's identity.

## Remaining approval

External installation and the real fork report-only gate are now validated for
the pinned candidate. Live comments, CUDA, other HF task families, and community
adoption are outside these checks. Final candidate review and explicit merge/tag/
release approval remain separate. Keep validation PRs unmerged.

Candidate PR #13 remains separate from the public default branch. No new tag or
release was created as part of this validation.
