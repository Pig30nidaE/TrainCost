# Base Prompt for Codex Tasks

You are working on TrainCost CI.

TrainCost CI is a lightweight GitHub Action that reviews ML training configuration changes in Pull Requests and warns about possible GPU cost increases, budget violations, and inefficient settings.

Before coding:

1. Read AGENTS.md.
2. Inspect the current repository structure.
3. Identify the smallest safe change that completes the task.
4. Do not expand scope unless required.

While coding:

1. Keep core logic separate from GitHub-specific logic.
2. Prefer simple deterministic rules over complex prediction.
3. Add or update tests for meaningful behavior changes.
4. Handle missing or invalid config gracefully.
5. Avoid logging secrets or environment variables.
6. Do not claim exact cost prediction.
7. Keep outputs clear and actionable.

After coding:

1. Run relevant tests.
2. Summarize what changed.
3. Summarize how it was tested.
4. Mention any limitations or assumptions.
5. Show the files changed.

Definition of done:

1. The requested feature works.
2. Tests cover the new behavior.
3. The project still fits the MVP scope.
4. The README or docs are updated if user-facing behavior changed.
5. The final output is reviewable as a clean diff.

Current task:
[여기에 이번에 맡길 구체적인 작업을 적기]
