"""Exercise main's state and bundle failure paths without GPU work."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO))
SPEC = importlib.util.spec_from_file_location("hf_outcome_runner", DEMO / "run_validation.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
SECRET = "hf_" + "A" * 36


def snapshot(workspace):
    return {str(path.relative_to(workspace)): path.read_bytes() for path in workspace.rglob("*") if path.is_file()}


def existing_preflight(workspace):
    environment = {
        "python": "3.12.0", "system": "Linux", "machine": "x86_64", "kernel_release": "WSL2",
        "packages": {key: "test" for key in ("torch", "transformers", "accelerate", "datasets", "safetensors")},
        "all_packages_sha256": "test", "gpu": "RTX 3060", "driver": "test", "cuda_runtime": "test",
        "compute_capability": [8, 6], "total_vram_bytes": 12 * 1024**3,
    }
    runner.write_json(workspace / "preflight.json", environment)
    (workspace / "static-report.md").write_text("Estimated cost: illustrative input.\n")
    state = {"schema": 1, "stage": "preflight", "spent_seconds": 0.0, "source_sha256": "test-source",
             "environment_sha256": runner.digest(environment), "artifacts": {}}
    runner.seal(workspace, state, workspace / "preflight.json")
    runner.seal(workspace, state, workspace / "static-report.md")
    runner.save_state(workspace, state)
    return environment


class MainOutcomeTests(unittest.TestCase):
    def invoke(self, stage, workspace):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = runner.main([stage, "--workspace", str(workspace)])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_rerunning_preflight_preserves_completed_workspace_bytes(self):
        for completed in (False, True):
            with self.subTest(completed=completed), tempfile.TemporaryDirectory() as temp:
                workspace = Path(temp).resolve()
                (workspace / "existing.md").write_bytes(b"existing evidence\n")
                if completed:
                    (workspace / "state.json").write_bytes(b'{"stage":"verify","status":"PASS","artifacts":{}}\n')
                    (workspace / "outcome.json").write_bytes(b'{"prior":"unchanged"}\n')
                before = snapshot(workspace)
                with patch.dict(os.environ, {"CI": "", "GITHUB_ACTIONS": ""}), patch.object(runner, "worker") as worker:
                    code, _, _ = self.invoke("preflight", workspace)
                self.assertEqual(code, 1)
                worker.assert_not_called()
                self.assertEqual(snapshot(workspace), before)

    def test_environment_mismatch_records_safe_failure_and_bundles(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp).resolve()
            existing_preflight(workspace)
            with patch.dict(os.environ, {"CI": "", "GITHUB_ACTIONS": ""}), \
                    patch.object(runner, "source_fingerprint", return_value="test-source"), \
                    patch.object(runner, "worker", return_value={"unexpected": SECRET}):
                code, out, err = self.invoke("prepare", workspace)
                self.assertEqual(code, 1)
                outcome = json.loads((workspace / "outcome.json").read_text())
                self.assertEqual(outcome, {"stage": "prepare", "status": "FAIL", "reason": "VALIDATION_FAILED"})
                self.assertNotIn(SECRET, out + err + (workspace / "outcome.json").read_text())
                self.assertEqual(json.loads((workspace / "state.json").read_text())["stage"], "failed")
                code, out, err = self.invoke("bundle", workspace)
                self.assertEqual(code, 0, err)
            self.assertEqual(json.loads((workspace / "bundle/outcome.json").read_text()), outcome)
            manifest = json.loads((workspace / "bundle/bundle-manifest.json").read_text())
            self.assertEqual(manifest["status"], "FAIL")
            self.assertNotIn(SECRET, "".join(path.read_text() for path in (workspace / "bundle").iterdir()))

    def test_timeout_failure_bundle_preserves_inconclusive_status(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp).resolve()
            environment = existing_preflight(workspace)
            def fake_worker(_workspace, stage, *_args, **_kwargs):
                if stage == "preflight":
                    return environment
                raise runner.DemoError(SECRET, "INCONCLUSIVE", "TIMEOUT")
            with patch.dict(os.environ, {"CI": "", "GITHUB_ACTIONS": ""}), \
                    patch.object(runner, "source_fingerprint", return_value="test-source"), \
                    patch.object(runner, "worker", side_effect=fake_worker):
                code, out, err = self.invoke("prepare", workspace)
                self.assertEqual(code, 2)
                self.assertNotIn(SECRET, out + err)
                outcome = json.loads((workspace / "outcome.json").read_text())
                self.assertEqual(outcome, {"stage": "prepare", "status": "INCONCLUSIVE", "reason": "TIMEOUT"})
                code, out, err = self.invoke("bundle", workspace)
                self.assertEqual(code, 0, err)
            self.assertEqual(json.loads((workspace / "bundle/outcome.json").read_text()), outcome)
            self.assertEqual(json.loads((workspace / "bundle/bundle-manifest.json").read_text())["status"], "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
