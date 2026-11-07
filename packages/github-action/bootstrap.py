"""Run the action in a disposable venv, isolated from consumer imports."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

ACTION_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ACTION_DIR))
from traincost_action import (ConfigError, OutputPathError, declared_input_paths, error_run, parse_args,
                              protected_output_candidates, publish_report, resolve_output_paths, validate_report_paths)


def main():
    try:
        args = parse_args(sys.argv[1:])
    except ConfigError:
        print("Invalid command arguments; use --help for supported options.", file=sys.stderr)
        return 2
    env = dict(os.environ)
    if args.comment_mode.lower() != "true":
        env.pop("GITHUB_TOKEN", None)
        env.pop("GH_TOKEN", None)
    repo_root = Path(args.repo_root).resolve()
    report_path, json_path, path_error = resolve_output_paths(repo_root, args.report_path, args.report_json_path)
    input_paths = declared_input_paths(repo_root, args)
    input_paths.extend(protected_output_candidates(repo_root, args, (report_path, json_path)))
    try:
        validate_report_paths(report_path, json_path, protected_paths=input_paths, workspace_root=repo_root)
    except OutputPathError:
        print("TrainCost CI could not write reports to unsafe output paths.", file=sys.stderr)
        return 2
    try:
        if path_error:
            publish_report(error_run(path_error), report_path, json_path=json_path,
                           protected_paths=input_paths, workspace_root=repo_root)
            return 2
        with tempfile.TemporaryDirectory(prefix="traincost-", dir=os.getenv("RUNNER_TEMP")) as temp:
            venv = Path(temp) / "venv"
            subprocess.run([sys.executable, "-I", "-m", "venv", str(venv)], check=True,
                           env=env, cwd=temp, capture_output=True, timeout=120)
            python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            subprocess.run([str(python), "-I", "-m", "pip", "--isolated", "install",
                            "--disable-pip-version-check", "--no-cache-dir", "--only-binary=:all:",
                            "-r", str(ACTION_DIR / "requirements.txt")], check=True,
                           env=env, cwd=temp, capture_output=True, timeout=120)
            return subprocess.run([str(python), "-I", str(ACTION_DIR / "traincost_action.py"),
                                   *sys.argv[1:]], env=env, check=False).returncode
    except (OSError, subprocess.SubprocessError):
        # Installation output may contain registry credentials. Never echo it.
        outcome = error_run("Isolated dependency setup failed; PyYAML==6.0.3 is required.")
        try:
            publish_report(outcome, report_path, json_path=json_path,
                           protected_paths=input_paths, workspace_root=repo_root)
        except (OSError, ValueError):
            print("TrainCost CI could not write setup diagnostics.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
