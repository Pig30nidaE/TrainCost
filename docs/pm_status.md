# TrainCost CI PM Status

## 1. Current Project Phase

Release Approval

The MVP report-only path is validated end to end. Release preparation commit `d97fdf5fc568aa3bc82bb591c10a0a5dd27eaa3a` passed PM review and is approved for a release pull request. The tag and GitHub Release do not exist yet.

What changed from the previous PM status:

- Public installation examples now use the intended ref `Pig30nidaE/TrainCost@v0.1.0`.
- The internal smoke workflow remains on `uses: ./`.
- `docs/release_notes_v0.1.0.md` documents the first release and its known limitations.
- PM independently reran 15 core tests, 8 GitHub Action tests, action metadata checks, and the canonical report comparison.
- The cheap baseline config remains unchanged.

## 2. MVP Completion Summary

| Area | Owner Agent | Status | Notes |
| --- | --- | --- | --- |
| Product spec | ProductArchitect | Done | The MVP, target users, non-goals, supported fields, and demo story are documented. |
| Core engine | CoreEngine | Done | YAML, JSON, and simple Python parsing, estimation, rules, confidence, and Markdown generation are implemented. Core tests pass: 15/15. |
| GitHub Action | GithubAction | Done for MVP | The composite action, PR file detection, base/head loading, report output, and `comment-mode: false` path passed a live GitHub-hosted PR run. |
| QA coverage | QAReview | Pass | Core tests pass: 15/15. GitHub Action tests pass: 8/8. Local fixtures and the live PR report are validated. |
| Integration | Integration | Done | The local report matches the expected fixture byte-for-byte. |
| Demo repo | ProductArchitect / Integration | Done | The canonical base config, risky fixture, workflow, README, and expected report are present. |

## 3. End-to-End MVP Flow Status

| Step | Status | Notes |
| --- | --- | --- |
| 1. Cheap base config exists. | Pass | `examples/pytorch-demo/config.yaml` on `main` contains the baseline values. |
| 2. Expensive PR config exists. | Pass | PR #2 changes the canonical file to the risky fixture values. |
| 3. Pull request triggers GitHub Actions. | Pass | A `pull_request/synchronize` run was observed on GitHub-hosted infrastructure. |
| 4. Base and head configs are loaded separately. | Pass | The live report shows all expected base-to-head field changes. |
| 5. Estimated cost increase is calculated. | Pass | The report shows `$0.04`, `$21.33`, and `+48,662%`. |
| 6. Risk warnings are generated. | Pass | Budget, cost increase, epoch, GPU type, GPU count, precision, and batch-size warnings are present. |
| 7. Markdown report is generated. | Pass | The workflow verified a non-empty report at `/home/runner/work/TrainCost/TrainCost/report.md`. |
| 8. Action outputs are written. | Pass | The workflow verified a non-empty `report-path` and `comment-posted=false`. |
| 9. No PR comment is attempted. | Pass | The live workflow uses `comment-mode: false` with read-only repository permissions. |

## 4. Live GitHub Validation Evidence

- Repository: `Pig30nidaE/TrainCost`.
- Workflow setup PR: [#1](https://github.com/Pig30nidaE/TrainCost/pull/1), merged as `be921b6`.
- Verification assertion fix PR: [#3](https://github.com/Pig30nidaE/TrainCost/pull/3), merged as `9bd070f`.
- Live demo PR: [#2](https://github.com/Pig30nidaE/TrainCost/pull/2), intentionally left unmerged.
- Live rerun head commit: `ae2791a`.
- Event path: `pull_request/synchronize`.
- Config detected: `examples/pytorch-demo/config.yaml`.
- Output path: `/home/runner/work/TrainCost/TrainCost/report.md`.
- Comment output: `comment-posted=false`.
- Confidence: High, because epoch count, GPU type, GPU count, and estimated minutes per epoch were provided.

The first live run generated the correct report but its verification step failed because the workflow searched for a config heading without the Markdown backticks rendered by the action. PR #3 corrected only that assertion. The rerun produced the full report in the GitHub Checks Summary, which is written only after the output, file, and expected-report assertions pass.

No token, credential, secret value, or environment dump appeared in the supplied live-run evidence. The only displayed environment values were the generated report path and `COMMENT_POSTED=false`.

## 5. Current Blockers

No MVP blocker remains for the report-only GitHub Action path.

The following items are publication steps or residual risks, not blockers for the approved release commit:

- No `v0.1.0` release tag has been created yet.
- The release preparation branch must be reviewed and merged into `main` before tagging.
- `comment-mode: true` has not been exercised against a live pull request. The MVP acceptance path uses report preparation with `comment-mode: false`.
- The fallback YAML parser intentionally supports common mappings and scalar values rather than the full YAML language.

## 6. Next Release Action

No additional agent work is assigned before the release pull request. The next action is PM-controlled publication preparation:

1. Push `codex/prepare-v0.1.0-release` and open a pull request against `main`.
2. Confirm the pull request contains only the approved release documentation, refs, and permission cleanup.
3. Keep demo PR #2 unmerged so `main` retains the cheap baseline config.
4. Merge the release pull request after its checks pass.
5. Resolve the final `main` commit SHA after merge.
6. Obtain explicit publication approval before creating or pushing the `v0.1.0` tag or publishing the GitHub Release.
7. Create the tag from the approved `main` commit and use `docs/release_notes_v0.1.0.md` as the release notes.

## 7. Scope Control

- Do not add a dashboard or backend service.
- Do not add Kubernetes, MLflow, W&B, Comet, OpenCost, or Kubecost integration.
- Do not add authentication, billing, team management, or cloud account setup.
- Do not run real GPU training jobs.
- Do not implement complex model-specific runtime prediction.
- Do not claim exact GPU cost prediction.
- Do not broaden parser support beyond common YAML, JSON, and simple Python configs for this release.

## 8. Release Readiness

Release commit approved for merge

Reason: the live report-only path passed, unit tests pass, the deterministic fixture matches byte-for-byte, metadata paths and interfaces are valid, public refs are prepared, and the release notes accurately state the known limitations.

The project is not released yet. Approval in this document covers merging the release preparation commit, not creating the tag or publishing the GitHub Release.

## 9. Recommended Next Milestone

Publish `v0.1.0` from the approved release commit.

The milestone is complete when:

1. The release preparation pull request is merged into `main`.
2. The final `main` commit SHA is recorded.
3. Explicit publication approval is received.
4. Annotated tag `v0.1.0` points to the approved `main` commit and is pushed.
5. The GitHub Release is published using `docs/release_notes_v0.1.0.md`.
6. The public action ref `Pig30nidaE/TrainCost@v0.1.0` resolves successfully.
