# Three TrainCost demo scenarios

config.yaml is the cheap baseline for live PRs. Keep it unchanged on main.

| Head config | Expected report | Status |
| --- | --- | --- |
| configs/risky-config.yaml | expected-report.md | complete, risk warnings |
| configs/missing-config.yaml | expected-missing-report.md | complete, Low confidence |
| configs/invalid-config.yaml | expected-invalid-report.md | error, no cost, exit 2 |

Run scripts/verify_release.py from the repository root after installing requirements-dev.txt.
The exact local dry-run command is in the root README. The live PR heading adds the config path.
The sample standalone workflow requires a reviewed candidate SHA before use.
See ../../docs/demo_script.md for images and the narrative, and ../../docs/qa_report.md for live evidence.
