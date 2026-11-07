"""Real Git and subprocess regression tests for release boundaries."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
ACTION = ROOT / "packages/github-action/traincost_action.py"
CORE_SRC = ROOT / "packages/core/src"
TOKEN = "hf_" + "D" * 36
HF = {"num_train_epochs": 1, "per_device_train_batch_size": 8, "gpu_type": "T4", "gpu_count": 1,
      "estimated_minutes_per_epoch": 6, "bf16": True}
CANONICAL = {"epochs": 1, "batch_size": 8, "gpu_type": "T4", "gpu_count": 1,
             "estimated_minutes_per_epoch": 6, "precision": "bf16"}


class RealGitAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tc-git-review-")
        self.addCleanup(self.temp.cleanup)
        self.outer = Path(self.temp.name).resolve()
        self.repo = self.outer / "consumer"
        self.repo.mkdir()
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                    "GITHUB_OUTPUT": str(self.outer / "outputs"), "GITHUB_STEP_SUMMARY": str(self.outer / "summary"),
                    "GITHUB_TOKEN": TOKEN}
        self.git("init", "-q")
        (self.repo / "existing.json").write_text(json.dumps(HF), encoding="utf-8")
        self.base = self.commit("base")

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                               "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                              cwd=self.repo, env=self.env, check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def run_action(self, head, path, adapter="huggingface"):
        event = self.outer / "event.json"
        event.write_text(json.dumps({"pull_request": {"base": {"sha": self.base}, "head": {"sha": head}}}))
        cmd = [sys.executable, "-I", str(ACTION), "--repo-root", str(self.repo), "--event-path", str(event),
               "--event-name", "pull_request", "--config-path", path, "--config-adapter", adapter,
               "--gpu-prices", "T4=1", "--comment-mode", "false"]
        run = subprocess.run(cmd, cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=30)
        report, machine = self.repo / "report.md", self.repo / "report.json"
        self.assertTrue(machine.exists(), run.stdout + run.stderr)
        data = json.loads(machine.read_text())
        self.assertNotIn(TOKEN, run.stdout + run.stderr + report.read_text() + machine.read_text())
        self.assertEqual(report.read_text(), (self.outer / "summary").read_text())
        return run, data, report.read_text()

    def test_added_hf_config_is_analyzed_with_explicit_absent_base(self):
        (self.repo / "new.json").write_text(json.dumps({**HF, "num_train_epochs": 3}))
        head = self.commit("add HF training config")
        run, data, report = self.run_action(head, "new.json")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(data["analysis_status"], "complete")
        self.assertEqual(data["summary"]["analyzed_count"], 1)
        self.assertEqual(data["summary"]["excluded_count"], 0)
        self.assertAlmostEqual(data["summary"]["base_cost_usd"], 0.5)
        self.assertAlmostEqual(data["summary"]["pr_cost_usd"], 0.3)
        self.assertEqual(data["analyses"][0]["confidence"]["level"], "Low")
        self.assertIsNone(data["analyses"][0]["base"]["config"]["epochs"])
        self.assertEqual(data["analyses"][0]["pr"]["config"]["epochs"], 3)
        self.assertTrue(any("added config" in note.lower() for note in data["diagnostics"]))
        self.assertIn("base", report.lower())
        self.assertTrue(any(word in report.lower() for word in ("added config", "no base", "absent base")))
        self.assertNotIn("model-only configs are unsupported", report)

    def test_added_modified_and_invalid_hf_configs_give_honest_partial_totals(self):
        (self.repo / "existing.json").write_text(json.dumps({**HF, "num_train_epochs": 4}))
        (self.repo / "new.json").write_text(json.dumps({**HF, "num_train_epochs": 3}))
        (self.repo / "invalid.json").write_text('{"num_train_epochs": ')
        head = self.commit("mixed configs")
        run, data, report = self.run_action(head, "*.json")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(data["analysis_status"], "partial")
        self.assertEqual(data["summary"]["analyzed_count"], 2)
        self.assertEqual(data["summary"]["excluded_count"], 1)
        self.assertEqual({x["path"] for x in data["analyses"]}, {"existing.json", "new.json"})
        self.assertAlmostEqual(data["summary"]["base_cost_usd"], 0.6)
        self.assertAlmostEqual(data["summary"]["pr_cost_usd"], 0.7)
        self.assertEqual(data["summary"]["scope"], "analyzed_configs_only")
        self.assertIn("invalid.json", report)
        self.assertIn("Excluded configs: 1", report)

    def test_new_model_metadata_is_not_treated_as_training_config(self):
        (self.repo / "model-only.json").write_text(json.dumps({"model_type": "distilbert", "architectures": ["DistilBertModel"]}))
        head = self.commit("add model metadata")
        run, data, report = self.run_action(head, "model-only.json")
        self.assertEqual(run.returncode, 2)
        self.assertEqual(data["analysis_status"], "error")
        self.assertEqual(data["summary"]["analyzed_count"], 0)
        self.assertIsNone(data["summary"]["pr_cost_usd"])

    def test_committed_default_output_symlink_cannot_overwrite_outside_file(self):
        sentinel = self.outer / "outside-sentinel.json"
        sentinel.write_bytes(b"outside sentinel\n")
        (self.repo / "existing.json").write_text(json.dumps({**HF, "num_train_epochs": 3}))
        (self.repo / "report.json").symlink_to("../outside-sentinel.json")
        head = self.commit("config and report symlink")
        first_output = self.repo / "report.md"
        first_output.write_bytes(b"preserve first output\n")
        event = self.outer / "event.json"
        event.write_text(json.dumps({"pull_request": {"base": {"sha": self.base}, "head": {"sha": head}}}))
        run = subprocess.run([sys.executable, "-I", str(ACTION), "--repo-root", str(self.repo),
                              "--event-path", str(event), "--event-name", "pull_request", "--config-path", "existing.json",
                              "--config-adapter", "huggingface", "--comment-mode", "false"],
                             cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertEqual(sentinel.read_bytes(), b"outside sentinel\n")
        self.assertEqual(first_output.read_bytes(), b"preserve first output\n")
        self.assertTrue((self.repo / "report.json").is_symlink())
        self.assertNotIn(TOKEN, run.stdout + run.stderr)

    def test_pre_git_error_never_overwrites_config_selected_by_glob(self):
        source = self.repo / "existing.json"
        original = source.read_bytes()
        run = subprocess.run([sys.executable, "-I", str(ACTION), "--repo-root", str(self.repo),
                              "--event-path", "", "--event-name", "pull_request", "--config-path", "*.json",
                              "--report-json-path", "existing.json", "--comment-mode", "false"],
                             cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertEqual(source.read_bytes(), original, "error diagnostics overwrote an input matched by the glob")

    def test_bootstrap_setup_error_never_overwrites_globbed_config(self):
        source = self.repo / "existing.json"
        original = source.read_bytes()
        bootstrap = ROOT / "packages/github-action/bootstrap.py"
        code = (
            "import importlib.util,pathlib,subprocess,sys\n"
            "from unittest.mock import patch\n"
            "s=importlib.util.spec_from_file_location('bootstrap_glob_review',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
            "root=pathlib.Path(sys.argv[2]);sys.argv=[str(sys.argv[1]),'--repo-root',str(root),'--config-path','*.json','--report-json-path','existing.json']\n"
            "with patch.object(m.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'synthetic')):\n"
            " raise SystemExit(m.main())\n")
        env = {**self.env, "RUNNER_TEMP": str(self.outer)}
        run = subprocess.run([sys.executable, "-I", "-c", code, str(bootstrap), str(self.repo)],
                             cwd=self.repo, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertEqual(source.read_bytes(), original, "setup diagnostics overwrote an input matched by the glob")


class OutputRoutingAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tc-route-review-")
        self.addCleanup(self.temp.cleanup)
        self.outer = Path(self.temp.name).resolve()
        self.repo = self.outer / "consumer"
        self.repo.mkdir()
        self.base, self.head = self.repo / "base.json", self.repo / "head.json"
        self.base.write_text(json.dumps(CANONICAL))
        self.head.write_text(json.dumps({**CANONICAL, "epochs": 3}))
        self.original_inputs = (self.base.read_bytes(), self.head.read_bytes())

    def run_tool(self, tool, *, report=None, machine=None, invalid=False):
        if tool == "action":
            cmd = [sys.executable, "-I", str(ACTION), "--repo-root", str(self.repo),
                   "--base-config", str(self.base), "--head-config", str(self.head), "--comment-mode", "false"]
            if invalid: cmd += ["--config-adapter", "invalid"]
            if report is not None: cmd += ["--report-path", str(report)]
            if machine is not None: cmd += ["--report-json-path", str(machine)]
        else:
            cmd = [sys.executable, "-B", "-m", "traincost_ci_core", "--base-config", str(self.base),
                   "--head-config", str(self.head)]
            if invalid: cmd += ["--adapter", "invalid"]
            if report is not None: cmd += ["--report-path", str(report)]
            if machine is not None: cmd += ["--json-path", str(machine)]
        env = {**os.environ, "PYTHONPATH": str(CORE_SRC), "GITHUB_TOKEN": TOKEN,
               "GITHUB_OUTPUT": str(self.outer / "outputs"), "GITHUB_STEP_SUMMARY": str(self.outer / "summary")}
        run = subprocess.run(cmd, cwd=self.repo, env=env, capture_output=True, text=True, timeout=30)
        self.assertNotIn(TOKEN, run.stdout + run.stderr)
        self.assertEqual((self.base.read_bytes(), self.head.read_bytes()), self.original_inputs)
        return run

    def test_default_leaf_symlinks_preserve_sentinel_and_other_output(self):
        for tool in ("action", "cli"):
            for linked in ("report.md", "report.json"):
                with self.subTest(tool=tool, linked=linked), tempfile.TemporaryDirectory(prefix="tc-case-", dir=self.outer) as case:
                    previous_repo = self.repo
                    self.repo = Path(case)
                    self.base = self.repo / "base.json"
                    self.head = self.repo / "head.json"
                    self.base.write_bytes(self.original_inputs[0])
                    self.head.write_bytes(self.original_inputs[1])
                    self.addCleanup(setattr, self, "repo", previous_repo)
                    sentinel = self.outer / (tool + linked + ".sentinel")
                    sentinel.write_bytes(b"outside sentinel\n")
                    (self.repo / linked).symlink_to(sentinel)
                    other = self.repo / ("report.json" if linked == "report.md" else "report.md")
                    other.write_bytes(b"preserve first output\n")
                    run = self.run_tool(tool)
                    self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
                    self.assertEqual(sentinel.read_bytes(), b"outside sentinel\n")
                    self.assertEqual(other.read_bytes(), b"preserve first output\n")

    def test_explicit_leaf_parent_symlinks_and_failure_diagnostics_are_safe(self):
        for tool in ("action", "cli"):
            for shape, invalid in (("leaf", False), ("parent", False), ("leaf", True), ("parent", True)):
                with self.subTest(tool=tool, shape=shape, invalid=invalid), tempfile.TemporaryDirectory(prefix="tc-case-", dir=self.outer) as case:
                    case = Path(case)
                    outside = case / "outside"
                    outside.mkdir()
                    sentinel = outside / "result.json"
                    sentinel.write_bytes(b"outside sentinel\n")
                    report = case / "report.md"
                    report.write_bytes(b"preserve first output\n")
                    if shape == "leaf":
                        machine = self.repo / f"leaf-{tool}-{invalid}.json"
                        machine.symlink_to(sentinel)
                    else:
                        redirect = self.repo / f"parent-{tool}-{invalid}"
                        redirect.symlink_to(outside, target_is_directory=True)
                        machine = redirect / "result.json"
                    run = self.run_tool(tool, report=report, machine=machine, invalid=invalid)
                    self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
                    self.assertEqual(sentinel.read_bytes(), b"outside sentinel\n")
                    self.assertEqual(report.read_bytes(), b"preserve first output\n")

    def test_hardlinked_json_never_mutates_sentinel(self):
        for tool in ("action", "cli"):
            with self.subTest(tool=tool), tempfile.TemporaryDirectory(prefix="tc-case-", dir=self.outer) as case:
                case = Path(case)
                sentinel = case / "outside"
                sentinel.write_bytes(b"outside sentinel\n")
                machine = self.repo / f"hardlink-{tool}.json"
                os.link(sentinel, machine)
                report = case / "report.md"
                run = self.run_tool(tool, report=report, machine=machine)
                self.assertIn(run.returncode, (0, 2), run.stdout + run.stderr)
                self.assertEqual(sentinel.read_bytes(), b"outside sentinel\n")
                if run.returncode == 0:
                    self.assertFalse(machine.samefile(sentinel))
                    self.assertEqual(json.loads(machine.read_text())["analysis_status"], "complete")

    def test_explicit_non_symlink_outputs_outside_checkout_work(self):
        for tool in ("action", "cli"):
            with self.subTest(tool=tool), tempfile.TemporaryDirectory(prefix="tc-outside-", dir=self.outer) as case:
                report, machine = Path(case) / "report.md", Path(case) / "report.json"
                run = self.run_tool(tool, report=report, machine=machine)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertEqual(json.loads(machine.read_text())["analysis_status"], "complete")
                self.assertIn("Estimated cost", report.read_text())

    def test_bootstrap_failure_diagnostic_rechecks_output_symlink(self):
        sentinel = self.outer / "bootstrap-sentinel"
        sentinel.write_bytes(b"outside sentinel\n")
        report = self.repo / "report.md"
        report.write_bytes(b"preserve first output\n")
        machine = self.repo / "report.json"
        bootstrap = ROOT / "packages/github-action/bootstrap.py"
        code = (
            "import importlib.util,pathlib,subprocess,sys\n"
            "from unittest.mock import patch\n"
            "s=importlib.util.spec_from_file_location('bootstrap_review',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
            "root=pathlib.Path(sys.argv[2]);sentinel=pathlib.Path(sys.argv[3]);sys.argv=[str(sys.argv[1]),'--repo-root',str(root),'--base-config',str(root/'base.json'),'--head-config',str(root/'head.json')]\n"
            "def fail(*args,**kwargs):\n"
            " (root/'report.json').symlink_to(sentinel)\n"
            " raise subprocess.CalledProcessError(1,'synthetic')\n"
            "with patch.object(m.subprocess,'run',side_effect=fail):\n"
            " raise SystemExit(m.main())\n")
        env = {**os.environ, "RUNNER_TEMP": str(self.outer), "GITHUB_TOKEN": TOKEN,
               "GITHUB_OUTPUT": str(self.outer / "outputs"), "GITHUB_STEP_SUMMARY": str(self.outer / "summary")}
        run = subprocess.run([sys.executable, "-I", "-c", code, str(bootstrap), str(self.repo), str(sentinel)],
                             cwd=self.repo, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertEqual(sentinel.read_bytes(), b"outside sentinel\n")
        self.assertEqual(report.read_bytes(), b"preserve first output\n")
        self.assertTrue(machine.is_symlink())
        self.assertNotIn(TOKEN, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
