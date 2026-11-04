"""Run the action in a disposable venv, isolated from consumer imports."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

ACTION_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ACTION_DIR))
from traincost_action import AnalysisRun, parse_args, publish_report, render_no_config_report, resolve_report_path


def main():
    args = parse_args(sys.argv[1:])
    env = dict(os.environ)
    if args.comment_mode.lower() != "true":
        env.pop("GITHUB_TOKEN", None)
        env.pop("GH_TOKEN", None)
    report_path, path_error = resolve_report_path(Path(args.repo_root).resolve(), args.report_path)
    try:
        if path_error:
            publish_report(AnalysisRun(render_no_config_report([], [path_error]), "error"), report_path)
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
        outcome = AnalysisRun(render_no_config_report([], ["Isolated dependency setup failed; PyYAML==6.0.3 is required."]), "error")
        try:
            publish_report(outcome, report_path)
        except (OSError, ValueError):
            print("TrainCost CI could not write setup diagnostics.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
