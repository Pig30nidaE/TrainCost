# GitHub Action reference

The root action is the distribution entrypoint. Inside this repository, uses: ./packages/github-action is also supported.
The action requires Python 3.11 or later, venv, pip, Git, and access to install PyYAML==6.0.3.
Ubuntu GitHub-hosted runners are the supported beta target.

## Inputs

| Input | Default | Meaning |
| --- | --- | --- |
| config-path | config.yaml | Comma-separated repository paths or globs. Brace alternatives such as configs/*.{yaml,json} are supported. |
| config-adapter | canonical | Select `canonical` or opt in to `huggingface` training argument mapping. |
| gpu-prices | empty | NAME=PRICE entries in USD per GPU-hour; finite and non-negative. Normalized duplicate GPU names are rejected. |
| budget-limit | empty | Default non-negative USD budget if the config omits budget_limit_usd. |
| warn-increase-percent | 50 | Finite non-negative threshold; warning fires strictly above it. |
| comment-mode | false | true enables experimental GitHub comments; false passes no token to analysis. |
| report-path | report.md | Markdown output path, relative to the repository unless absolute. |
| report-json-path | empty | JSON output path; defaults to `report-path` with a `.json` suffix. The paths must differ. |

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

The outputs `report-path` and `report-json-path` point to the Markdown and JSON files. `comment-posted` is true only after a successful comment API operation.
The JSON uses schema version `1.0` and contains the analysis status, per-config analyses, safe diagnostics, and totals for analyzed configs. Costs remain unrounded numeric values. Error and skipped runs have null totals.
When both report paths pass validation and writing succeeds, analysis errors produce diagnostic reports and a Step Summary. Invalid command syntax exits without reports.
A partial report includes the excluded count. Combined totals sum analyzed configs only.
Budget and efficiency warnings are advisory; no budget enforcement mode is implemented.

## Report path safety

The Action validates both destinations before replacing either report. Markdown and JSON destinations must differ and must not name a protected config. Directory destinations, symbolic-link leaves or parents, and hard-linked files are rejected. Parent symlinks outside the checkout are also rejected, except for standard macOS `/tmp` and `/var` aliases. Absolute output paths outside the checkout are allowed. Existing regular, singly linked files at the output paths can be replaced, so choose paths that do not hold data you need to keep.

An existing output file inside the checkout is rejected if its path matches `config-path`, including a glob. This check also applies before Git analysis and when setup fails. Reports outside the checkout and reports that do not match the config glob can be used again on later runs, subject to the other path checks. For broad globs, place both reports outside the checkout:

~~~yaml
with:
  config-path: "**/*.json"
  report-path: "${{ runner.temp }}/traincost/report.md"
  report-json-path: "${{ runner.temp }}/traincost/report.json"
  comment-mode: "false"
~~~

Some invalid path inputs fall back to validated `report.md` and `report.json` locations for error diagnostics. Those defaults can replace existing regular files. If a fallback or selected output fails validation, no reports are written. Each report is staged and replaced separately, not as a two-file transaction; a later I/O failure can leave only one updated. The same checks apply to setup and analysis-error reports.

## Commit selection

Checkout must use fetch-depth: 0. PR base and head SHAs come from the GitHub event.
The comparison baseline is their single merge base, matching GitHub's three-dot
PR diff. Both changed-file selection and base config contents use that commit.
The report records its SHA and labels the costs `Merge-base estimate` and
`PR-head estimate`. Changes made only on the target branch are excluded.
This describes the PR's changes, not a prediction of a future merge result.
Missing or multiple merge bases fail explicitly; fetch full history or update the
PR branch instead of accepting an arbitrary ancestor.
Git diff uses NUL-delimited status records. Renames read the old merge-base path and the new head path.
Deleted configs are excluded. Added configs use illustrative defaults for their absent base, including in Hugging Face adapter mode. These defaults do not describe an actual earlier training run.
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

After the upgrade is reviewed, replace the placeholder below with its full commit SHA:

~~~yaml
- uses: Pig30nidaE/TrainCost@REVIEWED_UPGRADE_COMMIT_SHA
  with:
    config-path: "config.yaml"
    comment-mode: "false"
~~~

The placeholder is not a runnable reference or a published beta tag. The source is
public. Corrected candidate `a907b78423cd18b5e7a8f53f5d092fcba6df77e9` passed a separate
[hosted consumer test](external_consumer_validation.md) for both Action entrypoints.
Its follow-up real fork PR passed with Contents read and Metadata read permissions.
This covers report-only mode, not live comment posting. For private copies of the source,
cross-repository Action access requires separate repository settings.
The historical v0.1.0 tag lacks the HF adapter and JSON output described here.
Candidates before the final review do not include its merge-base and precision fixes.

The locally reproducible unrelated-consumer and fork-payload checks are in `scripts/verify_external_consumer.py`. They do not establish GitHub-hosted fork permissions or private cross-repository Action access. An example consumer workflow is in `examples/external-consumer/`.
