# TrainCost CI v0.2.0-beta.1

Unpublished report-only beta candidate.

## Changes

- Remove sensitive fields before comparison and sanitize parser errors and Markdown.
- Validate finite values, preserve partial epochs, reject fractional counts and conflicting settings.
- Require pinned PyYAML with bounded structures and duplicate-key rejection.
- Record extracted field paths, applied inputs, default assumptions, and separate base/PR price sources.
- Analyze only matching Git changes, including renames and deletions, without worktree fallback.
- Add analysis-status and automatic Step Summary. Failed analysis returns exit 2 after writing diagnostics.
- Install Action dependencies in a disposable isolated venv without a token in report-only mode.
- Verify Python 3.11-3.14 in CI, build/install the wheel independently, and publish three reproducible demo outcomes.
- Add MIT licensing and portfolio documentation.

## Compatibility

Existing Action inputs and outputs remain. analysis-status is additive.
Invalid inputs that previously produced defaults or non-finite estimates now produce errors.
YAML merge keys, duplicate keys, multi-experiment lists, and nonliteral Python assignments are rejected.
PyYAML is required; the permissive fallback parser is removed.
Report layout includes provenance and assumptions. Do not parse Markdown as a stable data API.
CostEstimate.price_source values are gpu_prices_input, builtin_price_table, and default_hourly_price.
The Python package version is 0.2.0b1, the PEP 440 form of the planned beta.

## Limits

This beta uses canonical field names, not framework inference.
Prices are illustrative unless overridden, runtime is supplied or assumed, and GPU speedups are not modeled.
Comment mode is experimental. Publication and public repository visibility require approval.
The v0.1.0 tag remains unchanged.
