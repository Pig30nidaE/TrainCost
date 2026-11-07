"""CPU-only checks for the optional Mac real-model smoke orchestration."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("mac_smoke", ROOT / "scripts/verify_hf_macos.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class MacSmokeTests(unittest.TestCase):
    def test_artifacts_are_exclusive_and_phase_refuses_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "base.json"
            smoke.write_json(path, {"original": True})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                smoke.write_json(path, {"replacement": True})
            with patch.object(smoke.os, "getppid", return_value=123), patch.object(smoke.os, "getpid", return_value=456), patch.object(smoke.os, "getpgrp", return_value=456):
                with self.assertRaises(ValueError):
                    smoke.check_phase(root, "base", 123)
            self.assertEqual(path.read_bytes(), before)

    def test_phase_requires_supervisor_and_unchanged_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            smoke.write_json(root / "run-contract.json", {"source_sha256": "before"})
            with self.assertRaises(ValueError):
                smoke.check_phase(root, "base", None)
            with patch.object(smoke.os, "getppid", return_value=123), patch.object(smoke.os, "getpid", return_value=456), patch.object(smoke.os, "getpgrp", return_value=456), patch.object(smoke, "execution_fingerprint", return_value="after"):
                with self.assertRaises(ValueError):
                    smoke.check_phase(root, "base", 123)

    def test_fingerprint_covers_imported_code_and_mac_lock(self):
        before = smoke.execution_fingerprint()
        with patch.object(smoke, "source_fingerprint", return_value="changed-core-or-worker"):
            self.assertNotEqual(before, smoke.execution_fingerprint())
        with patch.object(smoke, "file_digest", return_value="changed-mac-file"):
            self.assertNotEqual(before, smoke.execution_fingerprint())

    def test_explicit_device_and_small_subset(self):
        for device in ("mps", "cpu"):
            base, pr = (smoke.smoke_config(device, epochs) for epochs in (1, 3))
            self.assertEqual(base["dataset_size"], 64)
            self.assertNotEqual(base["gpu_type"], "RTX3060")
            self.assertEqual(pr, {**base, "epochs": 3})
        for device, epochs in (("cuda", 1), ("auto", 1), ("cpu", True), ("mps", 2)):
            with self.subTest(device=device, epochs=epochs), self.assertRaises(ValueError):
                smoke.smoke_config(device, epochs)

    def test_trainer_settings_preserve_contract(self):
        args = smoke.training_settings(smoke.smoke_config("mps", 3))
        self.assertEqual(args["num_train_epochs"], 3)
        self.assertEqual(args["per_device_train_batch_size"], 8)
        self.assertEqual(args["max_steps"], -1)
        self.assertEqual(args["gradient_accumulation_steps"], 1)
        for key in ("fp16", "bf16", "tf32", "push_to_hub"):
            self.assertFalse(args[key])
        self.assertEqual(args["report_to"], "none")
        self.assertEqual(args["save_strategy"], "no")

    def test_real_core_report_uses_same_measured_assumption_and_disclaimer(self):
        base = {"training_seconds": 60, "environment": {"device": "mps"}, "subset_content_sha256": {"train": "same"}}
        pr = {**base, "training_seconds": 140}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            result = smoke.check_report(path, "mps", base, pr)
            self.assertEqual(result["predicted_pr_seconds_from_single_base_run"], 180)
            self.assertAlmostEqual(result["cost_increase_percent"], 200)
            report = (path / "report.md").read_text()
            self.assertIn("not billing or CUDA evidence", report)
            self.assertIn("This PR: $0.05", report)
            measured = json.loads((path / "measured-pr.json").read_text())
            self.assertEqual(measured["estimated_minutes_per_epoch"], 1)
            self.assertEqual(measured["epochs"], 3)

    def test_pair_environment_or_data_drift_is_rejected(self):
        base = {"environment": {"device": "mps"}, "subset_content_sha256": {"train": "original"}}
        for changed in ({"environment": {"device": "cpu"}}, {"subset_content_sha256": {"train": "different"}}):
            with self.assertRaises(ValueError):
                smoke.check_report(Path("unused"), "mps", base, {**base, **changed})

    def test_timeout_kills_process_group(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(smoke.subprocess, "Popen") as spawn, patch.object(smoke.os, "killpg") as kill:
            process = spawn.return_value
            process.pid = 12345
            process.wait.side_effect = [subprocess.TimeoutExpired("safe-command", 600), 0]
            with self.assertRaises(subprocess.TimeoutExpired):
                smoke.run_child(Path(temp), "base", "mps")
            kill.assert_called_once_with(12345, smoke.signal.SIGKILL)
            self.assertEqual(spawn.call_args.kwargs["env"]["PYTORCH_ENABLE_MPS_FALLBACK"], "0")
            self.assertEqual(spawn.call_args.kwargs["env"]["HF_HUB_OFFLINE"], "1")


if __name__ == "__main__":
    unittest.main()
