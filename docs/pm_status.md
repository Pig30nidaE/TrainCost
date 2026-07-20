# TrainCost CI PM Status

## 1. Current Project Phase

Release Candidate Preparation

The MVP report-only path is validated end to end. A live GitHub-hosted pull request detected the canonical demo config change, loaded separate base and head versions, generated the expected cost-risk report, wrote the action outputs, and completed with `comment-mode: false`.

What changed from the previous PM status:

- The root smoke workflow now targets `examples/pytorch-demo/config.yaml` and uses read-only repository permissions.
- Live demo PR [#2](https://github.com/Pig30nidaE/TrainCost/pull/2) ran on a GitHub-hosted runner.
- The report showed `$0.04` base cost, `$21.33` PR cost, and a `+48,662%` increase with all expected warnings.
- The verification step confirmed that the report file exists and `comment-posted=false`.
- The previous live GitHub-hosted PR blocker is resolved.

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

The following items are release preparation or residual risks, not blockers for Release Candidate status:

- No `v0.1.0` release tag has been created yet.
- Public installation examples still use a documented placeholder action ref.
- `comment-mode: true` has not been exercised against a live pull request. The MVP acceptance path uses report preparation with `comment-mode: false`.
- The fallback YAML parser intentionally supports common mappings and scalar values rather than the full YAML language.

## 6. Next Agent Assignment

### Task 1 - GithubAction

Goal:
Prepare the repository for a `v0.1.0` release decision without creating the tag or release yet.

Prompt to send:

```text
You are the GithubAction Agent for TrainCost CI.

Read AGENTS.md, docs/pm_status.md, and docs/qa_report.md first.

The live GitHub-hosted pull request smoke test with comment-mode=false has passed.
Your task is release preparation only. Do not add product features or change estimation behavior.

Do not create new agents.
Do not add dashboard, Kubernetes, MLflow, W&B, Comet, OpenCost, SaaS backend,
auth, billing, team management, runtime prediction, or real GPU training.

Tasks:
1. Keep demo PR #2 unmerged so main retains the cheap baseline config.
2. Replace public installation placeholders with the intended release ref
   Pig30nidaE/TrainCost@v0.1.0. Keep the repository's internal smoke workflow on uses: ./.
3. Prepare concise v0.1.0 release notes covering config parsing, deterministic cost
   estimation, risk warnings, Markdown report generation, and GitHub Action usage.
4. Verify root action.yml and package-local action metadata paths.
5. Run:
   python3 -m unittest discover packages/core/tests
   python3 -m unittest discover packages/github-action/tests
6. Run the canonical dry run and confirm it still matches
   examples/pytorch-demo/expected-report.md byte-for-byte.
7. Report the proposed release commit SHA, changed files, test results, and known risks.
8. Do not create or push a v0.1.0 tag and do not publish a GitHub release until PM approval.
```

No immediate CoreEngine, Integration, ProductArchitect, or QAReview task is assigned.

## 7. Scope Control

- Do not add a dashboard or backend service.
- Do not add Kubernetes, MLflow, W&B, Comet, OpenCost, or Kubecost integration.
- Do not add authentication, billing, team management, or cloud account setup.
- Do not run real GPU training jobs.
- Do not implement complex model-specific runtime prediction.
- Do not claim exact GPU cost prediction.
- Do not broaden parser support beyond common YAML, JSON, and simple Python configs for this release.

## 8. Release Readiness

Release Candidate ready

Reason: unit tests pass, the deterministic fixture matches byte-for-byte, and the report-only GitHub Action path passed a live GitHub-hosted pull request run with the expected action outputs and risk report.

The project is not released yet. Tag creation, public action refs, and release notes remain release-preparation work.

## 9. Recommended Next Milestone

Prepare the `v0.1.0` release commit.

The milestone is complete when:

1. Public installation examples reference `Pig30nidaE/TrainCost@v0.1.0`.
2. Root and package-local action metadata paths are revalidated.
3. Core and GitHub Action tests pass.
4. The canonical dry-run report still matches the expected fixture.
5. Release notes and the proposed tag commit SHA are ready for PM approval.
