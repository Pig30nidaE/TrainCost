from __future__ import annotations

import json
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from traincost_ci_core.output_safety import OutputPathError, validate_report_paths, write_report_files
from traincost_ci_core import analyze_config_dicts
from traincost_ci_core.cli import main
from traincost_ci_core.safety import ConfigError

CORE_SRC = Path(__file__).resolve().parents[1] / "src"
CONFIG = {"epochs": 1, "gpu_count": 1, "gpu_type": "T4", "estimated_minutes_per_epoch": 3}


class OutputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.outside = self.root / "outside"
        self.outside.mkdir()
        self.sentinel = self.outside / "sentinel"
        self.sentinel.write_text("untouched")
        self.report = self.workspace / "report.md"
        self.json = self.workspace / "report.json"

    def write(self, report=None, json_path=None, **kwargs):
        return write_report_files(report or self.report, json_path or self.json, "markdown", "json",
                                  workspace_root=self.workspace, **kwargs)

    def assert_sentinel(self):
        self.assertEqual(self.sentinel.read_text(), "untouched")

    def cli(self, *extra, invalid=False):
        base, head = self.workspace / "base.json", self.workspace / "head.json"
        base.write_text(json.dumps(CONFIG))
        head.write_text("{" if invalid else json.dumps(CONFIG))
        env = {**os.environ, "PYTHONPATH": str(CORE_SRC)}
        return subprocess.run([sys.executable, "-B", "-m", "traincost_ci_core", "--base-config", str(base),
                               "--head-config", str(head), *extra], cwd=self.workspace, env=env,
                              capture_output=True, text=True)

    def test_valid_destinations_and_external_explicit_paths(self):
        outside_report = self.outside / "nested" / "report.md"
        outside_json = self.outside / "nested" / "report.json"
        validate_report_paths(outside_report, outside_json, workspace_root=self.workspace)
        self.assertFalse(outside_report.parent.exists())
        self.write(outside_report, outside_json)
        self.assertEqual(outside_report.read_text(), "markdown")
        self.assertEqual(outside_json.read_text(), "json")
        self.assert_sentinel()

    def test_symlink_leaf_and_parent_are_rejected(self):
        self.json.symlink_to(self.sentinel)
        self.report.write_text("existing")
        with self.assertRaises(OutputPathError):
            self.write()
        self.assertEqual(self.report.read_text(), "existing")
        self.assert_sentinel()
        self.json.unlink()
        (self.workspace / "redirect").symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(OutputPathError):
            self.write(json_path=self.workspace / "redirect" / "sentinel")
        self.assertEqual(self.report.read_text(), "existing")
        self.assert_sentinel()

    def test_hardlinks_and_input_collisions_are_rejected(self):
        os.link(self.sentinel, self.json)
        with self.assertRaises(OutputPathError):
            self.write()
        self.assert_sentinel()
        self.json.unlink()
        with self.assertRaises(OutputPathError):
            self.write(report=self.sentinel, protected_paths=(self.sentinel,))
        with self.assertRaises(OutputPathError):
            self.write(json_path=self.report)
        self.assert_sentinel()

    def test_directory_and_pathological_path_are_rejected(self):
        for path in (self.outside, self.workspace / ".." / "outside" / "new"):
            with self.subTest(path=path), self.assertRaises(OutputPathError):
                self.write(json_path=path)
        self.assertFalse(self.report.exists())

    def test_error_messages_do_not_reveal_path_or_secrets(self):
        secret = "ghp_" + "x" * 36
        with self.assertRaises(OutputPathError) as caught:
            self.write(json_path=self.workspace / secret)
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn(str(self.workspace), str(caught.exception))

    def test_leaf_swap_after_preflight_does_not_follow_link(self):
        original_replace = os.replace
        def swap(src, dst, **kwargs):
            if dst == "report.json":
                os.symlink(self.sentinel, dst, dir_fd=kwargs["dst_dir_fd"])
            return original_replace(src, dst, **kwargs)
        with patch("traincost_ci_core.output_safety.os.replace", side_effect=swap):
            self.write()
        self.assert_sentinel()
        self.assertFalse(self.json.is_symlink())
        self.assertEqual(self.json.read_text(), "json")

    def test_parent_swap_after_preflight_uses_open_directory(self):
        folder = self.workspace / "out"
        folder.mkdir()
        original_replace = os.replace
        swapped = False
        def swap(src, dst, **kwargs):
            nonlocal swapped
            if not swapped:
                swapped = True
                folder.rename(self.workspace / "moved")
                folder.symlink_to(self.outside, target_is_directory=True)
            return original_replace(src, dst, **kwargs)
        with patch("traincost_ci_core.output_safety.os.replace", side_effect=swap):
            self.write(folder / "report.md", folder / "report.json")
        self.assert_sentinel()
        self.assertEqual((self.workspace / "moved" / "report.json").read_text(), "json")
        self.assertFalse((self.outside / "report.json").exists())

    def test_cli_success_and_invalid_input_diagnostics_reject_symlink(self):
        for invalid in (False, True):
            with self.subTest(invalid=invalid):
                self.json.symlink_to(self.sentinel)
                run = self.cli(invalid=invalid)
                self.assertEqual(run.returncode, 2, run.stderr)
                self.assert_sentinel()
                self.assertFalse(self.report.exists())
                self.json.unlink()

    def test_cli_valid_and_error_reports_and_input_collision(self):
        success = self.cli()
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertEqual(json.loads(self.json.read_text())["analysis_status"], "complete")
        error = self.cli(invalid=True)
        self.assertEqual(error.returncode, 2, error.stderr)
        self.assertEqual(json.loads(self.json.read_text())["analysis_status"], "error")
        collision = self.cli("--json-path", "base.json")
        self.assertEqual(collision.returncode, 2)
        self.assertEqual(json.loads((self.workspace / "base.json").read_text()), CONFIG)

    def test_cli_rechecks_symlink_inserted_during_analysis_and_error(self):
        base, head = self.workspace / "base.json", self.workspace / "head.json"
        for path in (base, head):
            path.write_text(json.dumps(CONFIG))
        result = analyze_config_dicts(CONFIG, CONFIG)
        for error in (False, True):
            def analyze(*args, **kwargs):
                self.json.symlink_to(self.sentinel)
                if error:
                    raise ConfigError("Invalid config.")
                return result
            with self.subTest(error=error), patch("traincost_ci_core.cli.analyze_config_files", side_effect=analyze):
                with contextlib.redirect_stderr(io.StringIO()):
                    status = main(["--base-config", str(base), "--head-config", str(head),
                                   "--report-path", str(self.report), "--json-path", str(self.json)])
                self.assertEqual(status, 2)
                self.assertFalse(self.report.exists())
                self.assert_sentinel()
                self.json.unlink()

    @unittest.skipUnless(sys.platform == "darwin", "macOS root alias")
    def test_macos_tmp_alias(self):
        tmp = Path("/tmp")
        with tempfile.TemporaryDirectory(dir=tmp) as directory:
            self.write(Path(directory) / "report.md", Path(directory) / "report.json")
            self.assertEqual((Path(directory) / "report.json").read_text(), "json")

    @unittest.skipUnless(sys.platform == "darwin", "macOS var alias")
    def test_macos_var_alias(self):
        physical = str(self.workspace.resolve())
        if not physical.startswith("/private/var/"):
            self.skipTest("temporary workspace is not under /private/var")
        alias = Path(physical.removeprefix("/private"))
        self.write(alias / "report.md", alias / "report.json")
        self.assertEqual((self.workspace / "report.json").read_text(), "json")

    @unittest.skipUnless(sys.platform == "darwin", "macOS case folding")
    def test_macos_case_variant_outputs_do_not_collide(self):
        with self.assertRaises(OutputPathError):
            self.write(self.workspace / "report.md", self.workspace / "REPORT.MD")
