"""Independent output boundary tests using synthetic temporary files."""

import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
TOKEN = "hf_" + "C" * 36


class OutputSafetyAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tc-output-review-")
        self.addCleanup(self.temp.cleanup)
        self.outer = Path(self.temp.name).resolve()
        self.workspace = self.outer / "checkout"
        self.workspace.mkdir()
        self.safety = importlib.import_module("traincost_ci_core.output_safety")

    def write(self, report, machine, *, protected=()):
        return self.safety.write_report_files(report, machine, "# Test report\n", '{"status":"complete"}\n',
                                              protected_paths=protected, workspace_root=self.workspace)

    def test_normal_and_explicit_outside_outputs_are_supported(self):
        for directory in (self.workspace, self.outer / "explicit-output"):
            directory.mkdir(exist_ok=True)
            report, machine = directory / "report.md", directory / "report.json"
            with self.subTest(directory=directory):
                self.safety.validate_report_paths(report, machine, workspace_root=self.workspace)
                self.write(report, machine)
                self.assertEqual(report.read_text(), "# Test report\n")
                self.assertEqual(json.loads(machine.read_text()), {"status": "complete"})

    def test_leaf_symlink_never_overwrites_outside_or_first_output(self):
        for linked in ("report", "json"):
            with self.subTest(linked=linked):
                directory = self.workspace / linked
                directory.mkdir()
                sentinel = self.outer / f"{linked}-sentinel"
                sentinel.write_bytes(b"preserve outside\n")
                report, machine = directory / "report.md", directory / "report.json"
                path = report if linked == "report" else machine
                other = machine if linked == "report" else report
                other.write_bytes(b"preserve first output\n")
                path.symlink_to(sentinel)
                with self.assertRaises(self.safety.OutputPathError):
                    self.write(report, machine)
                self.assertEqual(sentinel.read_bytes(), b"preserve outside\n")
                self.assertEqual(other.read_bytes(), b"preserve first output\n")
                self.assertTrue(path.is_symlink())

    def test_parent_symlink_inside_checkout_is_rejected(self):
        outside = self.outer / "outside"
        outside.mkdir()
        sentinel = outside / "report.json"
        sentinel.write_bytes(b"preserve outside\n")
        (self.workspace / "redirect").symlink_to(outside, target_is_directory=True)
        report = self.workspace / "report.md"
        report.write_bytes(b"preserve first output\n")
        with self.assertRaises(self.safety.OutputPathError):
            self.write(report, self.workspace / "redirect" / "report.json")
        self.assertEqual(sentinel.read_bytes(), b"preserve outside\n")
        self.assertEqual(report.read_bytes(), b"preserve first output\n")

    def test_writer_rechecks_when_parent_changes_after_preflight(self):
        directory = self.workspace / "reports"
        directory.mkdir()
        report, machine = directory / "report.md", directory / "report.json"
        self.safety.validate_report_paths(report, machine, workspace_root=self.workspace)
        outside = self.outer / "outside-after-check"
        outside.mkdir()
        sentinel = outside / "report.json"
        sentinel.write_bytes(b"preserve outside\n")
        directory.rename(self.workspace / "old-reports")
        directory.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(self.safety.OutputPathError):
            self.write(report, machine)
        self.assertEqual(sentinel.read_bytes(), b"preserve outside\n")
        self.assertFalse((outside / "report.md").exists())

    @unittest.skipUnless(sys.platform == "darwin", "macOS system directory aliases")
    def test_standard_var_alias_is_allowed(self):
        private_var = Path("/private/var")
        if not self.workspace.is_relative_to(private_var):
            self.skipTest("temporary directory does not use the macOS /var alias")
        alias = Path("/var") / self.workspace.relative_to(private_var)
        report, machine = alias / "alias.md", alias / "alias.json"
        self.write(report, machine)
        self.assertEqual((self.workspace / "alias.md").read_text(), "# Test report\n")
        self.assertEqual(json.loads((self.workspace / "alias.json").read_text()), {"status": "complete"})

    def test_hardlinked_output_never_modifies_other_file(self):
        sentinel = self.outer / "hardlink-sentinel"
        sentinel.write_bytes(b"preserve outside\n")
        machine = self.workspace / "report.json"
        os.link(sentinel, machine)
        try:
            self.write(self.workspace / "report.md", machine)
        except self.safety.OutputPathError:
            pass
        self.assertEqual(sentinel.read_bytes(), b"preserve outside\n")
        if machine.exists() and machine.read_bytes() != b"preserve outside\n":
            self.assertFalse(machine.samefile(sentinel))

    def test_input_collisions_and_equal_outputs_are_rejected(self):
        source = self.workspace / "input.json"
        source.write_bytes(b"original config\n")
        alias = self.workspace / "hardlink.json"
        os.link(source, alias)
        for report, machine in ((source, self.workspace / "new.json"),
                                (self.workspace / "new.md", alias),
                                (self.workspace / "same", self.workspace / "same")):
            with self.subTest(report=report, machine=machine), self.assertRaises(self.safety.OutputPathError):
                self.write(report, machine, protected=(source,))
        self.assertEqual(source.read_bytes(), b"original config\n")

    def test_bad_output_diagnostic_never_echoes_path_or_secret(self):
        target = self.workspace / TOKEN
        target.symlink_to(self.outer / "secret-target")
        with self.assertRaises(self.safety.OutputPathError) as error:
            self.write(target, self.workspace / "safe.json")
        self.assertNotIn(TOKEN, str(error.exception))
        self.assertNotIn(str(self.outer), str(error.exception))


if __name__ == "__main__":
    unittest.main()
