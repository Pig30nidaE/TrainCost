from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ACTION_FILE = Path(__file__).resolve().parents[1] / "traincost_action.py"
SPEC = importlib.util.spec_from_file_location("traincost_action", ACTION_FILE)
action = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = action
SPEC.loader.exec_module(action)

BASE = "epochs: 5\ngpu_type: T4\ngpu_count: 1\nestimated_minutes_per_epoch: 1.5\n"
RISKY = "epochs: 50\ngpu_type: A100\ngpu_count: 2\nestimated_minutes_per_epoch: 4\nbudget_limit_usd: 5\n"
SECRET = "ghp_" + "A" * 36


class ActionEntrypointTests(unittest.TestCase):
    def invoke(self, root, *extra):
        report, outputs, summary = (root / name for name in ("report.md", "outputs", "summary"))
        env = {"GITHUB_OUTPUT": str(outputs), "GITHUB_STEP_SUMMARY": str(summary),
               "GITHUB_EVENT_PATH": "", "GITHUB_EVENT_NAME": "", "GITHUB_TOKEN": SECRET}
        with patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = action.main(["--repo-root", str(root), "--report-path", str(report), *extra])
        result = (code, report.read_text(), outputs.read_text(), summary.read_text(), stdout.getvalue() + stderr.getvalue())
        for output in result[1:]:
            self.assertNotIn(SECRET, output)
        return result

    def test_local_dry_run_generates_report_and_outputs_without_comment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "base.yaml").write_text(BASE)
            (root / "head.yaml").write_text(RISKY)
            with patch.object(action, "post_or_update_pr_comment") as comment:
                code, report, outputs, summary, _ = self.invoke(root, "--base-config", str(root / "base.yaml"), "--head-config", str(root / "head.yaml"))
            self.assertEqual(code, 0)
            self.assertIn("Budget limit exceeded", report)
            self.assertIn("analysis-status=complete", outputs)
            self.assertIn("comment-posted=false", outputs)
            self.assertEqual(summary, report)
            self.assertIn("Base config file:", report)
            self.assertIn("PR config file:", report)
            comment.assert_not_called()

    def test_bad_inputs_still_write_diagnostics_outputs_summary(self):
        for flag, value in (("--gpu-prices", "T4=nan"), ("--budget-limit", "-1"), ("--warn-increase-percent", "inf"), ("--gpu-prices", SECRET), ("--comment-mode", "maybe")):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as temp:
                code, report, outputs, summary, _ = self.invoke(Path(temp), flag, value)
                self.assertEqual(code, 2)
                self.assertIn("analysis-status=error", outputs)
                self.assertEqual(report, summary)
                self.assertNotIn("- This PR:", report)

    def test_config_errors_and_secret_values_never_leak(self):
        for text in ("api_key: [" + SECRET, "gpu_type: " + SECRET, "epochs: inf", "epochs: -2", "gpu_count: nan"):
            with self.subTest(text=text[:10]), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "base.yaml").write_text(BASE)
                (root / "head.yaml").write_text(text)
                code, report, outputs, _, _ = self.invoke(root, "--base-config", str(root / "base.yaml"), "--head-config", str(root / "head.yaml"))
                self.assertIn(code, (0, 2))
                if code == 2:
                    self.assertIn("analysis-status=error", outputs)

    def test_parses_inputs_and_zero_prices(self):
        self.assertEqual(action.parse_gpu_prices("T4=0.5,A10G=1.2"), {"T4": .5, "A10G": 1.2})
        self.assertEqual(action.parse_gpu_prices("T4=0"), {"T4": 0})
        for text in ("T4=-1", "T4=inf", "T4=nan", "T4=x", "=1", "T4=1,t-4=2"):
            with self.assertRaises(action.ConfigError):
                action.parse_gpu_prices(text)
        self.assertEqual(action.parse_warn_increase_percent(""), 50)
        self.assertEqual(action.parse_warn_increase_percent("30"), 30)
        self.assertEqual(action.parse_budget_limit("0"), 0)

    def test_non_pr_is_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            code, _, outputs, _, _ = self.invoke(Path(temp), "--event-name", "push")
        self.assertEqual(code, 0)
        self.assertIn("analysis-status=skipped", outputs)

    def test_missing_local_file_is_error(self):
        with tempfile.TemporaryDirectory() as temp:
            code, _, outputs, _, _ = self.invoke(Path(temp), "--base-config", "/nonexistent/base.yaml", "--head-config", "/nonexistent/head.yaml")
        self.assertEqual(code, 2)
        self.assertIn("analysis-status=error", outputs)

    def test_invalid_yaml_is_reported_without_crashing(self):
        item = action.analyze_config_texts(display_path="config.yaml", base_text=BASE, head_text="epochs: [1, 2",
            file_suffix=".yaml", default_budget_limit_usd=None, gpu_hourly_prices={})
        self.assertEqual(item["report"], "")
        self.assertIn("Invalid YAML", item["notes"][0])

    def test_base_config_unavailable_still_analyzes_head_config(self):
        item = action.analyze_config_texts(display_path="new.yaml", base_text=None, head_text=BASE,
            file_suffix=".yaml", default_budget_limit_usd=None, gpu_hourly_prices={})
        self.assertIn("Low-confidence estimate", item["report"])

    def test_warn_increase_percent_changes_warning_threshold(self):
        item = action.analyze_config_texts(display_path="config.yaml", base_text=BASE,
            head_text=BASE.replace("epochs: 5", "epochs: 7"), file_suffix=".yaml",
            default_budget_limit_usd=None, gpu_hourly_prices={}, cost_increase_threshold_percent=30)
        self.assertIn("more than 30%", item["report"])

    def test_comment_failure_does_not_print_token_or_error_body(self):
        event = {"pull_request": {"comments_url": "https://api.github.com/repos/o/r/issues/1/comments"}}
        with patch.dict(os.environ, {"GITHUB_TOKEN": SECRET}), patch.object(action, "github_json_request", side_effect=urllib.error.URLError(SECRET)), contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertFalse(action.post_or_update_pr_comment(event, "report"))
        self.assertNotIn(SECRET, stdout.getvalue())

    def test_comment_mock_create_and_update(self):
        event = {"pull_request": {"comments_url": "https://api.github.com/repos/o/r/issues/1/comments"}}
        url = "https://api.github.com/repos/o/r/issues/comments/2"
        for existing in ([], [{"body": action.COMMENT_MARKER, "url": url, "user": {"type": "Bot"}}]):
            with patch.dict(os.environ, {"GITHUB_TOKEN": SECRET}), patch.object(action, "github_json_request", side_effect=[existing, {}]) as request:
                self.assertTrue(action.post_or_update_pr_comment(event, "report"))
                self.assertEqual(request.call_args.args[0], "PATCH" if existing else "POST")

    def test_external_api_url_rejected(self):
        with self.assertRaises(ValueError):
            action.github_json_request("POST", "https://example.invalid/steal", SECRET)


class GitIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.write("config.yaml", BASE)
        self.write("unchanged.yaml", BASE)
        self.base = self.commit()

    def git(self, *args):
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        return subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false", *args], cwd=self.root, env=env, check=True, capture_output=True).stdout.decode().strip()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "test")
        return self.git("rev-parse", "HEAD")

    def analyze(self, path="config.yaml", head=None, base=None):
        return action.run_pull_request_analysis(repo_root=self.root,
            event={"pull_request": {"base": {"sha": base or self.base}, "head": {"sha": head or self.git("rev-parse", "HEAD")}}},
            event_name="pull_request", config_path_input=path, default_budget_limit_usd=5,
            gpu_hourly_prices={"T4": .35, "A100": 3.20})

    def test_modified_config_uses_commits_not_worktree(self):
        self.write("config.yaml", RISKY)
        self.commit()
        self.write("config.yaml", "epochs: -999")
        outcome = self.analyze()
        self.assertEqual(outcome.status, "complete")
        self.assertIn("This PR: $21.33", outcome.report)
        self.assertIn("Increase: +48,662%", outcome.report)

    def test_deleted_config_never_estimated(self):
        self.git("rm", "config.yaml")
        self.commit()
        for pattern in ("config.yaml", "*.yaml", ""):
            outcome = self.analyze(pattern)
            self.assertEqual(outcome.status, "skipped")
            self.assertIn("Deleted config excluded", outcome.report)
            self.assertNotIn("- This PR:", outcome.report)
            self.assertNotIn("unchanged.yaml", outcome.report)

    def test_no_changes_and_no_glob_matches(self):
        self.assertEqual(self.analyze("*.yaml").status, "skipped")
        self.write("config.yaml", RISKY)
        self.commit()
        self.assertEqual(self.analyze("other/*.yaml").status, "skipped")

    def test_rename_and_special_paths(self):
        name = "configs/\ud55c\uae00 space\tname.yaml"
        (self.root / "configs").mkdir()
        self.git("mv", "config.yaml", name)
        self.commit()
        outcome = self.analyze("configs/*.yaml")
        self.assertEqual(outcome.status, "complete")
        self.assertIn("Detected rename:", outcome.report)
        self.assertIn("No supported fields changed", outcome.report)
        self.assertNotIn("Low-confidence", outcome.report)

    def test_added_config_explains_base_assumptions(self):
        self.write("added.yaml", BASE)
        self.commit()
        outcome = self.analyze("added.yaml")
        self.assertEqual(outcome.status, "complete")
        self.assertIn("Added config:", outcome.report)
        self.assertIn("Low-confidence", outcome.report)

    def test_multiple_configs_brace_glob_and_totals(self):
        self.write("config.yaml", RISKY)
        self.write("new.json", json.dumps({"epochs": 3}))
        self.commit()
        outcome = self.analyze("**/*.{yaml,json}")
        self.assertEqual(outcome.status, "complete")
        self.assertIn("Analyzed 2 config files", outcome.report)
        self.assertIn("Sum of analyzed configs only", outcome.report)
        self.assertNotIn("unchanged.yaml", outcome.report)

    def test_partial_and_all_invalid(self):
        self.write("config.yaml", "epochs: inf")
        self.write("new.yaml", BASE)
        self.commit()
        partial = self.analyze("*.yaml")
        self.assertEqual(partial.status, "partial")
        self.assertIn("Excluded configs: 1", partial.report)
        self.assertEqual(self.analyze("config.yaml").status, "error")

    def test_missing_sha_is_error_not_added_config(self):
        outcome = self.analyze(base="0" * 40)
        self.assertEqual(outcome.status, "error")
        self.assertIn("fetch-depth: 0", outcome.report)
        self.assertNotIn("- This PR:", outcome.report)

    def test_oversized_utf8_config_is_excluded(self):
        self.write("config.yaml", "model: " + "\ud55c" * 400_000)
        self.commit()
        outcome = self.analyze()
        self.assertEqual(outcome.status, "error")
        self.assertIn("1MB", outcome.report)

    def test_brace_and_path_escape_rejected(self):
        for pattern in ("../*.yaml", "/tmp/*.yaml", "config.{yaml,json"):
            with self.assertRaises(action.ConfigError):
                action.resolve_candidate_paths(pattern, [])

    def test_missing_head_blob_does_not_read_worktree(self):
        self.write("config.yaml", RISKY)
        self.commit()
        with patch.object(action, "read_git_file", side_effect=action.ConfigError("Unreadable Git blob.")):
            outcome = self.analyze()
        self.assertEqual(outcome.status, "error")
        self.assertNotIn("- This PR:", outcome.report)

    def test_git_failure_does_not_become_partial_success(self):
        self.write("config.yaml", RISKY)
        self.write("new.yaml", BASE)
        self.commit()
        read = action.read_git_file
        def fail_one(repo_root, sha, path):
            if path == "new.yaml":
                raise action.GitError("Config could not be read from the requested commit.")
            return read(repo_root, sha, path)
        with patch.object(action, "read_git_file", side_effect=fail_one):
            outcome = self.analyze("*.yaml")
        self.assertEqual(outcome.status, "error")
        self.assertNotIn("- This PR:", outcome.report)

    def test_missing_blob_raises_git_error(self):
        with self.assertRaises(action.GitError):
            action.read_git_file(self.root, self.base, "absent.yaml")


if __name__ == "__main__":
    unittest.main()
