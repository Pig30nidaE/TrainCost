"""All verification inputs are fingerprinted; output cannot replace one."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_upgrade


class FingerprintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.paths = [
            "docs/evidence/consumer/verify.py",
            "docs/evidence/consumer/reports/report.json",
            "docs/evidence/consumer/reports/report.md",
            "docs/evidence/consumer/workflow.yml",
            "docs/evidence/local-result.json",
        ]
        for name in self.paths:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("original")
        self.output = self.root / self.paths[-1]
        self.root_patch = patch.object(verify_upgrade, "ROOT", self.root)
        self.git_patch = patch.object(verify_upgrade.subprocess, "check_output",
            return_value=("\0".join(self.paths) + "\0").encode())
        self.root_patch.start()
        self.git_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.git_patch.stop)

    def fingerprint(self):
        return verify_upgrade.fingerprint()

    def test_archive_code_and_inputs_change_fingerprint(self):
        initial, files = self.fingerprint()
        for name in self.paths[:-1]:
            with self.subTest(path=name):
                self.assertIn(name, files)
                path = self.root / name
                path.write_text("changed")
                self.assertNotEqual(initial, self.fingerprint()[0])
                path.write_text("original")

    def test_previous_records_are_fingerprinted_too(self):
        initial, files = self.fingerprint()
        self.assertIn(self.paths[-1], files)
        self.output.write_text("new verification result")
        self.assertNotEqual(initial, self.fingerprint()[0])

    def test_source_destinations_and_external_aliases_are_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            outside = Path(outside).resolve()
            link = outside / "link.json"
            link.symlink_to(self.output)
            hardlink = outside / "hardlink.json"
            os.link(self.output, hardlink)
            parent_alias = outside / "checkout"
            parent_alias.symlink_to(self.root, target_is_directory=True)
            for path in (self.output, self.root / "new.json", link, hardlink,
                         parent_alias / "new.json"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    verify_upgrade.validate_destination(path)
            self.assertEqual(self.output.read_text(), "original")

    def test_new_external_file_is_allowed_but_never_replaced(self):
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside).resolve() / "result.json"
            self.assertEqual(verify_upgrade.validate_destination(path), path)
            path.write_text("existing")
            with self.assertRaises(ValueError):
                verify_upgrade.validate_destination(path)


if __name__ == "__main__":
    unittest.main()
