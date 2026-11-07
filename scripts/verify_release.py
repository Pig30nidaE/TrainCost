"""Reproduce metadata and all three demo fixture checks without GitHub access."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_action", ROOT / "packages/github-action/traincost_action.py")
action = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = action
spec.loader.exec_module(action)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-fixtures", action="store_true")
    args = parser.parse_args()
    root = yaml.safe_load((ROOT / "action.yml").read_text())
    package = yaml.safe_load((ROOT / "packages/github-action/action.yml").read_text())
    for field in ("name", "description", "author", "branding", "inputs", "outputs"):
        assert root[field] == package[field], f"Metadata drift: {field}"
    for metadata, location in ((root, ROOT), (package, ROOT / "packages/github-action")):
        step = metadata["runs"]["steps"][0]
        script = step["run"].split("$GITHUB_ACTION_PATH/", 1)[1].strip('"\n ')
        assert (location / script).is_file(), "Missing bootstrap"
        assert "python3 -I" in step["run"], "Interpreter must be isolated"
        assert "inputs.comment-mode == 'true'" in step["env"]["GITHUB_TOKEN"], "Report-only mode must not receive a token"
    print("Root/package metadata and isolated bootstrap paths: passed")
    demo = ROOT / "examples/pytorch-demo"
    for name, head, status, expected in (
        ("risk", "configs/risky-config.yaml", "complete", "expected-report.md"),
        ("missing", "configs/missing-config.yaml", "complete", "expected-missing-report.md"),
        ("invalid", "configs/invalid-config.yaml", "error", "expected-invalid-report.md"),
    ):
        # Relative display paths keep diagnostics deterministic across machines.
        result = action.run_local_pair(Path("examples/pytorch-demo/configs/base-config.yaml"),
            Path("examples/pytorch-demo") / head, default_budget_limit_usd=5,
            gpu_hourly_prices={"T4": .35, "A10G": 1.2, "A100": 3.20})
        assert result.status == status, f"Unexpected {name} status"
        fixture = demo / expected
        if args.update_fixtures:
            fixture.write_text(result.report, encoding="utf-8")
        assert fixture.read_bytes() == result.report.encode(), f"Fixture mismatch: {name}"
        print(f"{name}: status={status}, fixture matches ({len(result.report.encode())} bytes)")


if __name__ == "__main__":
    main()
