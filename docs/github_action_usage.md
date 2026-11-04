# GitHub Action reference

The root action is the distribution entrypoint. Inside this repository, uses: ./packages/github-action is also supported.
The action requires Python 3.11 or later, venv, pip, Git, and access to install PyYAML==6.0.3.
Ubuntu GitHub-hosted runners are the supported beta target.

## Inputs

| Input | Default | Meaning |
| --- | --- | --- |
| config-path | config.yaml | Comma-separated repository paths or globs. Brace alternatives such as configs/*.{yaml,json} are supported. |
| gpu-prices | empty | NAME=PRICE entries in USD per GPU-hour; finite and non-negative. Normalized duplicate GPU names are rejected. |
| budget-limit | empty | Default non-negative USD budget if the config omits budget_limit_usd. |
| warn-increase-percent | 50 | Finite non-negative threshold; warning fires strictly above it. |
| comment-mode | false | true enables experimental GitHub comments; false passes no token to analysis. |
| report-path | report.md | Markdown output path, relative to the repository unless absolute. |

Paths select changed files only. A leading **/ includes root files. The beta uses case-sensitive fnmatch patterns; * may span directory separators.
Absolute config paths and parent traversal are rejected. Literal commas in filenames cannot be selected individually; use a glob.
YAML, YML, JSON, and PY extensions are supported.

## Outputs and exits

| analysis-status | Meaning | Exit |
| --- | --- | --- |
| complete | All selected non-deleted configs analyzed. Defaults may still make confidence Low. | 0 |
| partial | At least one config analyzed and at least one failed. | 0 |
| skipped | No matching changes, only deletions, or not a pull_request event. | 0 |
| error | Invalid inputs, unavailable Git commits, failed setup, or every selected non-deleted config failed. | 2 |

report-path points to the generated file. comment-posted is true only after a successful comment API operation.
Reports and Step Summary are written for errors when the runner output locations are writable.
A partial report includes the excluded count. Combined totals sum analyzed configs only.
Budget and efficiency warnings are advisory; no budget enforcement mode is implemented.

## Commit selection

Checkout must use fetch-depth: 0. PR base and head SHAs come from the GitHub event.
Git diff uses NUL-delimited status records. Renames read the old base path and the new head path.
Deleted configs are excluded. Added configs explicitly use illustrative defaults for their absent base.
A missing commit or unreadable blob is an error, not an empty config.
The checked-out worktree is never substituted for a PR blob.

## Dependency and token isolation

Each action invocation creates a disposable venv and installs the pinned YAML parser.
Python runs with -I so consumer PYTHONPATH and modules do not influence imports.
Installation failure returns an error report rather than falling back to a different YAML parser.
The action needs contents: read. Persisted checkout credentials should be disabled.

## Experimental comments

Use comment-mode: true and pull-requests: write only when you intend to post a report.
Known token patterns and sensitive config values are removed before rendering.
Only GitHub API URLs are accepted and redirects are not followed.
The first 100 comments are searched for a bot report marker. Concurrent writers and pagination are not solved in this beta.
Forks may not have write permission; comment failure preserves the report.
Create/update mocks are tested; live comment mode is not part of this release gate.

## External installation

Pin the reviewed commit SHA from docs/qa_report.md:

~~~yaml
- uses: Pig30nidaE/TrainCost@e21f1f4fd445e64e24f7596ec7ff1cf2f2c5b54c
  with:
    config-path: "config.yaml"
    comment-mode: "false"
~~~

This is the tested code candidate, not a published beta tag. Repository access is required while the project remains private.
Private cross-repository action access requires GitHub repository settings and has not been validated by the same-repository smoke test.
The v0.1.0 tag is historical and lacks the beta hardening.
