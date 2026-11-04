# Beta QA evidence

Updated: 2026-11-04. Technical beta gates: PASS. Publication: HOLD for review and explicit approval.

Code candidate: e21f1f4fd445e64e24f7596ec7ff1cf2f2c5b54c.
Later evidence and installation-example edits do not change this tested code.

## Local evidence

- Environment: macOS arm64, Python 3.14.0, PyYAML 6.0.3 in an isolated venv.
- Core: 39 tests passed. Action and bootstrap: 28 tests passed, including real temporary-Git integration cases.
- Coverage.py 7.17.1, branch measurement enabled: 88% combined coverage, excluding tests.
- All three demo fixtures match byte-for-byte; metadata inputs and outputs match.
- Python -I -S dependency check: missing PyYAML gives a safe, explicit diagnostic.
- Built wheel installed and executed in a new venv outside the repository.
- Actual disposable-venv bootstrap generated the risky report successfully.
- Local known-pattern scan after the code candidate: 139 reachable Git blobs and 67 worktree entries, no findings.
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
- Candidate CI: [run 41780255071](https://github.com/Pig30nidaE/TrainCost/actions/runs/41780255071).
  Python 3.11, 3.12, 3.13, and 3.14 plus the isolated composite job all passed.
  Each matrix job ran both suites, checked all fixtures and metadata, tested the missing dependency,
  built the wheel, installed/imported it outside the repository, and scanned known credential patterns.
  The Python 3.14 job measured 88% branch-enabled coverage; fixture sizes were 4101, 2583, and 247 bytes.
- SHA-pinned consumer: [PR #8](https://github.com/Pig30nidaE/TrainCost/pull/8), intentionally unmerged.
- Consumer report: [run 41780305127](https://github.com/Pig30nidaE/TrainCost/actions/runs/41780305127),
  [verification job](https://github.com/Pig30nidaE/TrainCost/actions/runs/41780305127/job/126410080839), passed.
- Consumer CI: [run 41780305103](https://github.com/Pig30nidaE/TrainCost/actions/runs/41780305103), all five jobs passed.

| Consumer evidence | Observed value |
| --- | --- |
| Event | pull_request |
| Action ref and base SHA | e21f1f4fd445e64e24f7596ec7ff1cf2f2c5b54c |
| Head SHA | ef2281071303b76bef1c9e036cbd1360e7846b64 |
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
