"""Registered results must survive replay without hiding failed measurements."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_hf_evidence as evidence


class RegisteredEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.index = deepcopy(evidence.matrix.read_json(evidence.INDEX))
        self.index["studies"] = self.index["studies"][:1]
        self.original_index = deepcopy(self.index)
        self.bundle = self.root / self.index["studies"][0]["bundle"]
        shutil.copytree(ROOT / self.index["studies"][0]["bundle"], self.bundle)
        self.path = self.root / "index.json"

    def check(self):
        if self.path.exists():
            self.path.unlink()
        evidence.matrix.write_json(self.path, self.index)
        with redirect_stdout(io.StringIO()):
            return evidence.verify(self.path, root=self.root)

    def test_recorded_failure_is_preserved_not_promoted_to_pass(self):
        results = self.check()
        self.assertEqual(results[0]["models"], 3)
        self.assertEqual(results[0]["training_runs"], 27)
        self.assertEqual(results[0]["timing_status"], "FAIL")
        self.assertIsNone(results[0]["measured_commit"])
        self.assertFalse(results[0]["source_snapshot_available"])

    def test_cli_exposes_both_provenance_limits(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["verify_hf_evidence.py"]), redirect_stdout(output):
            self.assertEqual(evidence.main(), 0)
        self.assertIn("measured commit=unavailable", output.getvalue())
        self.assertIn("source snapshot=unavailable", output.getvalue())
        self.assertIn("not fresh training or release readiness", output.getvalue())

    def test_changed_report_or_missing_run_fails(self):
        for relative in ("bert/report.md", "albert/pr-3.json"):
            with self.subTest(relative=relative):
                original = (self.bundle / relative).read_bytes()
                (self.bundle / relative).write_bytes(b"changed")
                with self.assertRaises(evidence.matrix.MatrixError):
                    self.check()
                (self.bundle / relative).write_bytes(original)

    def test_unregistered_weights_cannot_enter_shared_bundle(self):
        (self.bundle / "model.safetensors").write_bytes(b"synthetic-not-real-weights")
        with self.assertRaises(ValueError):
            self.check()

    def test_historical_source_cannot_be_claimed_available(self):
        study = self.index["studies"][0]
        study["source_snapshot_available"] = True
        with self.assertRaises(ValueError):
            self.check()
        study["measured_commit"] = "a" * 40
        with self.assertRaises(ValueError):
            self.check()

    def test_model_coverage_and_expected_outcome_cannot_be_reduced(self):
        original = deepcopy(self.index)
        for mutation in ("coverage", "outcome", "identity"):
            self.index = deepcopy(original)
            study = self.index["studies"][0]
            if mutation == "coverage":
                study["models"] = ["bert"]
            elif mutation == "outcome":
                study["expected_status"]["timing_status"] = "PASS"
            else:
                study["measured_source_sha256"] = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.check()

    def test_unapproved_location_and_symlinks_are_rejected(self):
        self.index["studies"][0]["bundle"] = "../outside"
        with self.assertRaises(ValueError):
            self.check()
        self.index = deepcopy(self.original_index)
        (self.bundle / "extra.md").symlink_to(self.bundle / "bert/report.md")
        with self.assertRaises(ValueError):
            self.check()

    def test_committed_study_replays_source_and_all_runs(self):
        with redirect_stdout(io.StringIO()):
            studies = evidence.verify()
        committed = [study for study in studies if study["measured_commit"]]
        self.assertEqual({study["measured_commit"] for study in committed}, {
            "01ddafcda9a2545460f067dbb7c154f9661c2b97",
            "26613f604b9a25cecd65a6f8835dfd3ca8f5997e",
            "a907b78423cd18b5e7a8f53f5d092fcba6df77e9",
        })
        for study in committed:
            self.assertEqual(study["training_runs"], 27)
            self.assertEqual(study["timing_status"], "PASS")
            self.assertTrue(study["source_snapshot_available"])


if __name__ == "__main__":
    unittest.main()
