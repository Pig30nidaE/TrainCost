# TrainCost CI GitHub Action

The package-local composite action supports uses: ./packages/github-action inside this repository.
The root action is the external distribution entrypoint.

Both entrypoints run bootstrap.py with Python isolation, install PyYAML==6.0.3 in a disposable venv,
and invoke the same traincost_action.py. Report-only mode receives no GitHub token. Each run writes Markdown and versioned JSON reports, including error diagnostics when output paths are writable.

Inputs and outputs are documented in ../../docs/github_action_usage.md.
Root/package interface and bootstrap path parity are checked by scripts/verify_release.py.
Experimental comments are not a beta release gate.

The default `config-adapter` is `canonical`. Opt in to `huggingface` for the documented
TrainingArguments subset. A newly added config uses illustrative absent-base assumptions,
not a measured previous run. Runtime-condition and unmodeled-setting warnings are advisory;
they do not enforce a budget. JSON totals cover analyzed configs only.

Choose output paths that do not contain data you need to keep. Unsafe links, directories,
and collisions with protected inputs are rejected; existing regular output files can be
replaced. Existing checkout outputs that match a config glob are rejected, including on
early errors. Put both reports under `runner.temp` for broad globs. Reports are staged
separately, not committed as an atomic pair. The Action reference describes diagnostic
fallbacks and platform-specific handling.
