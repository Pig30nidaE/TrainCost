# TrainCost CI GitHub Action

The package-local composite action supports uses: ./packages/github-action inside this repository.
The root action is the external distribution entrypoint.

Both entrypoints run bootstrap.py with Python isolation, install PyYAML==6.0.3 in a disposable venv,
and invoke the same traincost_action.py. Report-only mode receives no GitHub token.

Inputs and outputs are documented in ../../docs/github_action_usage.md.
Root/package interface and bootstrap path parity are checked by scripts/verify_release.py.
Experimental comments are not a beta release gate.
