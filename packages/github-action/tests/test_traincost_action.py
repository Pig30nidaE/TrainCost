from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch


ACTION_FILE = Path(__file__).resolve().parents[1] / "traincost_action.py"
SPEC = importlib.util.spec_from_file_location("traincost_action", ACTION_FILE)
traincost_action = importlib.util.module_from_spec(SPEC)
sys.modules["traincost_action"] = traincost_action
assert SPEC.loader is not None
SPEC.loader.exec_module(traincost_action)


class ActionEntrypointTests(unittest.TestCase):
    def test_parses_gpu_price_input(self) -> None:
        prices = traincost_action.parse_gpu_prices("T4=0.5,A10G=1.2,A100=3.5")

        self.assertEqual(prices, {"T4": 0.5, "A10G": 1.2, "A100": 3.5})

    def test_local_dry_run_generates_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            base_path = tmp_path / "base.yaml"
            head_path = tmp_path / "config.yaml"
            report_path = tmp_path / "report.md"
            base_path.write_text(
                """
                epochs: 5
                batch_size: 64
                precision: bf16
                mixed_precision: true
                gpu_type: T4
                gpu_count: 1
                estimated_minutes_per_epoch: 1.5
                """,
                encoding="utf-8",
            )
            head_path.write_text(
                """
                epochs: 50
                batch_size: 8
                precision: fp32
                mixed_precision: false
                gpu_type: A100
                gpu_count: 2
                estimated_minutes_per_epoch: 1.5
                """,
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"GITHUB_OUTPUT": ""}, clear=False):
                exit_code = traincost_action.main(
                    [
                        "--base-config",
                        str(base_path),
                        "--head-config",
                        str(head_path),
                        "--gpu-prices",
                        "T4=0.5,A100=3.5",
                        "--budget-limit",
                        "5",
                        "--comment-mode",
                        "false",
                        "--report-path",
                        str(report_path),
                    ]
                )

            report = report_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("## TrainCost CI Report", report)
        self.assertIn("Cost risk detected.", report)
        self.assertIn("Budget limit exceeded", report)
        self.assertIn("Mixed precision appears disabled", report)

    def test_missing_config_generates_graceful_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            event_path = tmp_path / "event.json"
            report_path = tmp_path / "report.md"
            event_path.write_text(
                json.dumps(
                    {
                        "pull_request": {
                            "base": {"sha": "base"},
                            "head": {"sha": "head"},
                        }
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"GITHUB_OUTPUT": ""}, clear=False):
                exit_code = traincost_action.main(
                    [
                        "--repo-root",
                        str(tmp_path),
                        "--event-name",
                        "pull_request",
                        "--event-path",
                        str(event_path),
                        "--config-path",
                        "missing.yaml",
                        "--report-path",
                        str(report_path),
                    ]
                )

            report = report_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("No supported training config file found.", report)
        self.assertIn("missing.yaml", report)

    def test_invalid_yaml_is_reported_without_crashing(self) -> None:
        item = traincost_action.analyze_config_texts(
            display_path="config.yaml",
            base_text="epochs: 1\nestimated_minutes_per_epoch: 5\n",
            head_text="epochs: [1, 2\n",
            file_suffix=".yaml",
            default_budget_limit_usd=None,
            gpu_hourly_prices={},
        )

        self.assertEqual(item["report"], "")
        self.assertEqual(len(item["notes"]), 1)
        self.assertIn("Skipped config.yaml", item["notes"][0])
        self.assertIn("Invalid YAML", item["notes"][0])

    def test_base_config_unavailable_still_analyzes_head_config(self) -> None:
        item = traincost_action.analyze_config_texts(
            display_path="config.yaml",
            base_text=None,
            head_text="""
            epochs: 5
            estimated_minutes_per_epoch: 2
            gpu_count: 1
            gpu_type: T4
            """,
            file_suffix=".yaml",
            default_budget_limit_usd=None,
            gpu_hourly_prices={"T4": 0.5},
        )

        report = item["report"]

        self.assertEqual(item["notes"], [])
        self.assertIn("## TrainCost CI Report", report)
        self.assertIn("- epochs: not set -> 5", report)
        self.assertIn("Low-confidence estimate.", report)

    def test_glob_with_no_changed_config_files_generates_graceful_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = traincost_action.run_pull_request_analysis(
                repo_root=Path(tmpdir),
                event={"pull_request": {"base": {"sha": "base"}, "head": {"sha": "head"}}},
                event_name="pull_request",
                config_path_input="configs/*.yaml",
                default_budget_limit_usd=None,
                gpu_hourly_prices={},
            )

        self.assertIn("No supported training config file found.", report)
        self.assertIn("No changed supported config files matched the configured path.", report)

    def test_multiple_changed_config_files_render_combined_report(self) -> None:
        contents = {
            ("base", "configs/vision.yaml"): """
                epochs: 1
                estimated_minutes_per_epoch: 5
                gpu_count: 1
                gpu_type: T4
            """,
            ("head", "configs/vision.yaml"): """
                epochs: 10
                estimated_minutes_per_epoch: 60
                gpu_count: 1
                gpu_type: A100
                budget_limit_usd: 2
            """,
            ("base", "configs/language.yaml"): """
                epochs: 2
                estimated_minutes_per_epoch: 10
                gpu_count: 1
                gpu_type: T4
            """,
            ("head", "configs/language.yaml"): """
                epochs: 3
                estimated_minutes_per_epoch: 10
                gpu_count: 2
                gpu_type: T4
            """,
        }

        def fake_read_git_file(repo_root: Path, sha: str | None, path: str) -> str | None:
            return contents.get((sha, path))

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(
                traincost_action,
                "changed_supported_files",
                return_value=["configs/vision.yaml", "configs/language.yaml"],
            ):
                with patch.object(traincost_action, "read_git_file", side_effect=fake_read_git_file):
                    report = traincost_action.run_pull_request_analysis(
                        repo_root=Path(tmpdir),
                        event={"pull_request": {"base": {"sha": "base"}, "head": {"sha": "head"}}},
                        event_name="pull_request",
                        config_path_input="configs/*.yaml",
                        default_budget_limit_usd=None,
                        gpu_hourly_prices={"T4": 0.5, "A100": 4.0},
                    )

        self.assertIn("Analyzed 2 config files.", report)
        self.assertIn("### `configs/vision.yaml`", report)
        self.assertIn("### `configs/language.yaml`", report)
        self.assertIn("Budget limit exceeded", report)
        self.assertIn("GPU count increased", report)

    def test_comment_failure_does_not_print_github_token(self) -> None:
        token = "ghs_super_secret_token"
        event = {"pull_request": {"comments_url": "https://api.github.test/repos/o/r/issues/1/comments"}}
        output = io.StringIO()

        with patch.dict("os.environ", {"GITHUB_TOKEN": token}, clear=False):
            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("network unavailable")):
                with contextlib.redirect_stdout(output):
                    posted = traincost_action.post_or_update_pr_comment(event, "report body")

        self.assertFalse(posted)
        self.assertNotIn(token, output.getvalue())


if __name__ == "__main__":
    unittest.main()
