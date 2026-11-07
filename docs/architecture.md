# Why TrainCost treats configs as untrusted data

A PR author controls config contents and filenames. The reviewer expects the report to describe the requested commit, preserve secrets, and avoid inventing certainty.

## Data flow

~~~text
GitHub event base/head SHAs
  -> verified Git commits and a single common merge base
  -> NUL-delimited merge-base/head changes and matching base blobs
  -> bounded Git blobs
  -> YAML/JSON/Python literal parsing
  -> credential exclusion, validation, conflict checks, field paths
  -> normalized TrainingConfig
  -> deterministic estimates and risk rules
  -> escaped Markdown, versioned JSON, runner outputs, Step Summary
~~~

Core owns config interpretation, the formula, warnings, and report content.
The Action owns Git, event handling, file selection, runner outputs, and the optional GitHub API.
Bootstrap owns a disposable Python environment and pinned dependency installation.
Core can be installed as a wheel and used without GitHub.
The installed `traincost-ci` command and `python -m traincost_ci_core` compare two
local files. Core serialization owns the public JSON envelope; Action and CLI use
the same schema instead of exposing raw dataclass internals.

## Decisions

1. Require one YAML parser. The previous fallback silently skipped list items and interpreted inputs differently across runners. A missing dependency now produces an explicit error.
2. Reject conflicting fields. Global first-match traversal could choose evaluation.batch_size over training.batch_size. Field paths now explain extraction; conflicting values stop that file's analysis.
3. Preserve partial epochs. Truncating 2.9 to 2 understated runtime. Counts such as gpu_count remain integers.
4. Keep missing inputs distinct from invalid inputs. Missing fields retain visible illustrative defaults. Malformed values cannot produce a numeric estimate.
5. Read exact Git blobs from the PR merge base and head. Worktree fallback could mix a merge checkout with a requested head commit, and glob expansion included unchanged files. Direct base-tip/head diff also included changes made only on the target branch. Missing or ambiguous common ancestry now fails rather than guessing.
6. Sanitize before diffing. A sensitive-value warning alone did not prevent the Changed section from printing the value. Sensitive fields and subtrees are now removed before analysis.
7. Keep reports advisory. A risk warning is not a failed analysis. Status outputs separate complete, partial, skipped, and error without claiming to enforce a spending budget.

## Alternatives and limits

Generic framework inference would need training semantics, not just aliases. Hugging Face permits fractional epochs and max_steps overrides.
Lightning devices may mean GPU indices, automatic hardware, or a count per node. That scope is deferred to explicit, tested adapters.
The opt-in Hugging Face adapter translates a bounded epoch-based TrainingArguments
subset. It refuses positive max_steps instead of deriving epochs from incomplete
dataset and dataloader assumptions. Canonical remains the default, so adding an
adapter does not reinterpret existing configurations silently.
Executing a Python config to discover values would cross the PR trust boundary, so expressions remain unsupported.

Known unmodeled runtime keys are compared using internal fingerprints without
retaining their raw values in reports. Canonical runtime-affecting fields are
compared directly. Reusing the same epoch time after condition changes triggers a
warning, not an invented timing adjustment. This is a change heuristic, not a
validated measurement-provenance system.

Default prices are examples, not a pricing feed. Confidence reports input completeness.
A GPU count change is evaluated at fixed runtime, not with predicted distributed speedup.
Several changed configs are not necessarily several scheduled jobs, so totals state that assumption.

## Verification

Regression tests reproduce credential leaks, non-finite arithmetic, duplicate values, and deleted-file mistakes.
Git integration tests create real commits and alter the worktree to prove it is ignored.
Wheel verification uses a fresh environment outside the repository.
CI and candidate-SHA smoke evidence are recorded separately from local test results in docs/qa_report.md.
