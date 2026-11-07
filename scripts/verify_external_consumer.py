#!/usr/bin/env python3
"""Exercise the Action against an unrelated local Git consumer repository."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
ENTRYPOINT = SOURCE / "packages/github-action/traincost_action.py"
BOOTSTRAP = SOURCE / "packages/github-action/bootstrap.py"
SYNTHETIC_TOKEN = "ghp_" + "A" * 36
BASE = {"num_train_epochs": 1, "per_device_train_batch_size": 8, "world_size": 1,
        "gpu_type": "T4", "estimated_minutes_per_epoch": 6, "budget_limit_usd": 0.2}


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True,
                            capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def run_case(root: Path, repo: Path, base: str, head: str, *, fork: bool, bootstrap: bool) -> None:
    label = ("fork" if fork else "normal") + ("-bootstrap" if bootstrap else "-direct")
    case = root / label
    case.mkdir()
    event = {"pull_request": {"base": {"sha": base}, "head": {"sha": head,
             "repo": {"fork": fork, "full_name": "other/fork" if fork else "owner/consumer"}}}}
    event_path = case / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    report, machine, output, summary = (case / name for name in ("report.md", "report.json", "output", "summary"))
    env = {"PATH": os.environ.get("PATH", ""), "GITHUB_OUTPUT": str(output),
           "GITHUB_STEP_SUMMARY": str(summary), "GITHUB_EVENT_PATH": str(event_path),
           "GITHUB_EVENT_NAME": "pull_request", "GITHUB_WORKSPACE": str(repo),
           "GITHUB_TOKEN": SYNTHETIC_TOKEN, "GH_TOKEN": SYNTHETIC_TOKEN,
           "INPUT_CONFIG_PATH": "config.json", "INPUT_CONFIG_ADAPTER": "huggingface",
           "INPUT_GPU_PRICES": "T4=1", "INPUT_COMMENT_MODE": "false",
           "INPUT_REPORT_PATH": str(report), "INPUT_REPORT_JSON_PATH": str(machine)}
    run = subprocess.run([sys.executable, "-I", str(BOOTSTRAP if bootstrap else ENTRYPOINT)],
                         cwd=repo, env=env, capture_output=True, text=True, timeout=300)
    if run.returncode:
        raise RuntimeError(f"{label} failed (exit {run.returncode}); isolated bootstrap requires PyYAML installation access")
    values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
    text = report.read_text(encoding="utf-8")
    data = json.loads(machine.read_text(encoding="utf-8"))
    assert values["analysis-status"] == "complete" and values["comment-posted"] == "false"
    assert values["report-path"] == str(report) and values["report-json-path"] == str(machine)
    assert summary.read_text(encoding="utf-8") == text
    assert data["schema_version"] == "1.0" and data["analysis_status"] == "complete"
    assert data["summary"]["analyzed_count"] == 1 and data["summary"]["excluded_count"] == 0
    assert abs(data["summary"]["base_cost_usd"] - 0.1) < 1e-12
    assert abs(data["summary"]["pr_cost_usd"] - 0.3) < 1e-12
    assert data["analyses"][0]["path"] == "config.json"
    assert "Budget limit exceeded" in text and "epochs: 1 -> 3" in text
    for content in (run.stdout, run.stderr, text, machine.read_text(), output.read_text(), summary.read_text()):
        assert SYNTHETIC_TOKEN not in content and '"raw_fields"' not in content
    print(f"{label}: passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-only", action="store_true", help="Skip bootstrap dependency installation.")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="traincost-external-consumer-") as temp:
        root = Path(temp)
        repo = root / "consumer"
        repo.mkdir()
        git(repo, "init", "-q")
        config = repo / "config.json"
        config.write_text(json.dumps(BASE), encoding="utf-8")
        git(repo, "add", "config.json")
        git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base")
        base = git(repo, "rev-parse", "HEAD")
        config.write_text(json.dumps({**BASE, "num_train_epochs": 3}), encoding="utf-8")
        git(repo, "add", "config.json")
        git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "head")
        head = git(repo, "rev-parse", "HEAD")
        for fork in (False, True):
            run_case(root, repo, base, head, fork=fork, bootstrap=False)
            if not args.direct_only:
                run_case(root, repo, base, head, fork=fork, bootstrap=True)
    if args.direct_only:
        print("Bootstrap was not exercised (--direct-only).")
    print("Local payload simulations only; no GitHub-hosted PR was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
