# TrainCost CI v0.2.0-beta.1

Unpublished report-only beta candidate.

## Changes

- Remove sensitive fields before comparison and sanitize parser errors and Markdown.
- Validate finite values, preserve partial epochs, reject fractional counts and conflicting settings.
- Require pinned PyYAML with bounded structures and duplicate-key rejection.
- Record extracted field paths, applied inputs, default assumptions, and separate base/PR price sources.
- Analyze only matching Git changes, including renames and deletions, without worktree fallback.
- Use one merge base for both PR changed-file selection and base config values; exclude target-branch-only changes and reject ambiguous ancestry.
- Label PR report amounts as merge-base and PR-head estimates rather than current base-branch costs. Local file comparison labels remain unchanged.
- Respect explicit canonical mixed-precision enablement when interpreting FP32 labels.
- Add analysis-status and automatic Step Summary. Failed analysis returns exit 2 after writing diagnostics.
- Add an opt-in Hugging Face TrainingArguments adapter for literal, epoch-based configs. The default remains canonical.
- Add the `traincost-ci` CLI and a versioned JSON report alongside Markdown.
- Report known unmodeled settings and warn when a runtime-affecting change reuses the same minutes-per-epoch input.
- Preserve positive subcent amounts in Markdown and distinguish unequal budget comparisons that would otherwise round alike. JSON costs remain unrounded numbers.
- Validate both report destinations before replacement. Reject unsafe links, directory destinations, and collisions with protected inputs. Reject existing checkout outputs that match the config glob, including on early errors. Report files are staged separately, not committed as an atomic pair.
- Install Action dependencies in a disposable isolated venv without a token in report-only mode.
- Verify Python 3.11-3.14 in CI, build/install the wheel independently, and publish three reproducible demo outcomes.
- Add MIT licensing and portfolio documentation.
- Add reviewed DistilBERT, BERT, and ALBERT MPS validation profiles, committed-source replay, and metadata-only evidence. Preserve all 81 observations across three studies, including historical failures.
- Upgrade optional ML locks, audit both complete locks in CI, and validate pinned model/tokenizer metadata before loading. The replacement environment has its own 27-run study; old vulnerable locks remain historical evidence only.

## Compatibility

Existing Action inputs and outputs remain. `analysis-status`, `report-json-path`, and the `config-adapter` input are additive.
Invalid inputs that previously produced defaults or non-finite estimates now produce errors.
YAML merge keys, duplicate keys, multi-experiment lists, and nonliteral Python assignments are rejected.
PyYAML is required; the permissive fallback parser is removed.
Report layout includes provenance and assumptions. Do not parse Markdown as a stable data API.
Use the [versioned JSON contract](json_report.md) for automation.
CostEstimate.price_source values are gpu_prices_input, builtin_price_table, and default_hourly_price.
The Python package version is 0.2.0b1, the PEP 440 form of the planned beta.

## Limits

The Hugging Face adapter is explicit, not framework autodetection. It maps epochs,
per-device batch size, gradient accumulation, explicit GPU count or world size, and
bf16/fp16 flags. Positive `max_steps` overrides epoch counts and is rejected because
step-based runtime is not supported. Model-only configs, automatic batching, and
unsupported distributed engines are rejected. See [config reference](config_reference.md).
Prices are illustrative unless overridden, runtime is supplied or assumed, and GPU speedups are not modeled.
An added file uses illustrative absent-base assumptions; it is not compared with a measured earlier run.
`complete` means the selected configs were analyzed, not that every training setting was modeled.
Report-only mode is the beta target. Comment mode remains experimental and is not a release gate.
Real-model evidence covers small IMDb sequence-classification runs on MPS, not general HF tasks or runtime prediction. See the [current study](hf_security_upgrade_study.md).
The user made the source public. Candidate `28b4c54` passed CI and a separate
[external consumer](external_consumer_validation.md) using both Action entrypoints.
The real fork report-only test also passed. Candidate PR #13 is unmerged, and tag push
and release publication require separate approval. See [PM status](pm_status.md).
The v0.1.0 tag remains unchanged.
