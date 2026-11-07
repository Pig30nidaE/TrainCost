import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO))
SPEC = importlib.util.spec_from_file_location("hf_demo_runner", DEMO / "run_validation.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def process_terminated(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    if sys.platform != "linux":
        return False
    # A successful kill(0) does not keep /proc alive until the subsequent read.
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except ProcessLookupError:
        return True
    except FileNotFoundError:
        # Missing procfs is not proof of exit. Confirm that the PID also vanished.
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        raise AssertionError("Live process is not observable through procfs")
    return state == "Z"


class ProcessObservationTests(unittest.TestCase):
    def test_missing_pid_is_terminated(self):
        with patch.object(os, "kill", side_effect=ProcessLookupError), patch.object(Path, "read_text") as read:
            self.assertTrue(process_terminated(123))
            read.assert_not_called()

    def test_exit_between_probe_and_stat_read_is_terminated(self):
        for error in (FileNotFoundError, ProcessLookupError):
            with self.subTest(error=error), patch.object(sys, "platform", "linux"), \
                    patch.object(os, "kill", side_effect=[None, ProcessLookupError]), \
                    patch.object(Path, "read_text", side_effect=error):
                self.assertTrue(process_terminated(123))

    def test_missing_procfs_does_not_prove_a_live_process_exited(self):
        with patch.object(sys, "platform", "linux"), patch.object(os, "kill"), \
                patch.object(Path, "read_text", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(AssertionError, "not observable"):
                process_terminated(123)

    def test_linux_live_and_zombie_states(self):
        for state, expected in (("S", False), ("R", False), ("Z", True)):
            with self.subTest(state=state), patch.object(sys, "platform", "linux"), \
                    patch.object(os, "kill"), patch.object(Path, "read_text", return_value=f"123 (worker (test)) {state} 1 2"):
                self.assertEqual(process_terminated(123), expected)

    def test_permission_and_unexpected_read_errors_are_not_success(self):
        for error in (PermissionError, OSError):
            with self.subTest(error=error), patch.object(sys, "platform", "linux"), \
                    patch.object(os, "kill"), patch.object(Path, "read_text", side_effect=error):
                with self.assertRaises(error):
                    process_terminated(123)

    def test_non_linux_live_process_does_not_use_procfs(self):
        with patch.object(sys, "platform", "darwin"), patch.object(os, "kill"), patch.object(Path, "read_text") as read:
            self.assertFalse(process_terminated(123))
            read.assert_not_called()


class RunnerTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "linux", "Linux parent-death signal required")
    def test_sigkill_parent_triggers_actual_linux_parent_death_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            child_code = (
                "import os,pathlib,sys,time\n"
                "sys.path.insert(0,sys.argv[1]); import worker\n"
                "worker.arm_parent_death_signal(os.getppid())\n"
                "pathlib.Path(sys.argv[2]).write_text(str(os.getpid()))\n"
                "time.sleep(60)\n")
            parent_code = (
                "import subprocess,sys,time\n"
                "subprocess.Popen([sys.executable,'-B','-c',sys.argv[1],sys.argv[2],sys.argv[3]])\n"
                "time.sleep(60)\n")
            proc = subprocess.Popen([sys.executable, "-B", "-c", parent_code, child_code, str(DEMO), str(root / "child.pid")],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            child = None
            try:
                deadline = time.monotonic() + 8
                while not (root / "child.pid").exists() and time.monotonic() < deadline and proc.poll() is None:
                    time.sleep(0.02)
                self.assertTrue((root / "child.pid").exists(), "worker failed to arm parent-death signal")
                child = int((root / "child.pid").read_text())
                proc.kill()
                proc.wait(timeout=5)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if process_terminated(child):
                        break
                    time.sleep(0.02)
                else:
                    self.fail("worker survived SIGKILL of its parent")
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
                if child is not None:
                    try:
                        os.kill(child, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                proc.communicate(timeout=5)

    @unittest.skipUnless(hasattr(os, "killpg"), "requires POSIX process groups")
    def test_parent_sigterm_terminates_worker_group_and_records_inconclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / "state.json").write_text(json.dumps({"schema": 1, "stage": "preflight", "spent_seconds": 0,
                "source_sha256": "test", "environment_sha256": "test", "artifacts": {}}))
            (root / "worker.py").write_text(
                "import os,pathlib,subprocess,sys,time\n"
                "w=pathlib.Path(sys.argv[3])\n"
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
                "(w/'child.pid').write_text(str(p.pid))\n"
                "(w/'worker.pid').write_text(str(os.getpid()))\n"
                "time.sleep(60)\n")
            parent_code = (
                "import importlib.util,os,pathlib,sys\n"
                "sys.path.insert(0,sys.argv[1]); os.environ['CI']=''; os.environ['GITHUB_ACTIONS']=''\n"
                "spec=importlib.util.spec_from_file_location('test_runner_parent',pathlib.Path(sys.argv[1])/'run_validation.py')\n"
                "r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)\n"
                "r.HERE=pathlib.Path(sys.argv[2]); r.source_fingerprint=lambda:'test'\n"
                "r.checked_environment=lambda *args:None\n"
                "raise SystemExit(r.main(['prepare','--workspace',sys.argv[2]]))\n")
            proc = subprocess.Popen([sys.executable, "-B", "-c", parent_code, str(DEMO), str(root)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            worker_pid = None
            try:
                deadline = time.monotonic() + 8
                while not (root / "worker.pid").exists() and time.monotonic() < deadline and proc.poll() is None:
                    time.sleep(0.02)
                self.assertTrue((root / "worker.pid").exists(), "fake worker did not start")
                worker_pid = int((root / "worker.pid").read_text())
                child_pid = int((root / "child.pid").read_text())
                proc.send_signal(signal.SIGTERM)
                stdout, stderr = proc.communicate(timeout=8)
                self.assertEqual(proc.returncode, 2, stdout + stderr)
                deadline = time.monotonic() + 4
                for pid in (worker_pid, child_pid):
                    while time.monotonic() < deadline:
                        if process_terminated(pid):
                            break
                        time.sleep(0.02)
                    else:
                        self.fail(f"process {pid} survived parent termination")
                outcome = json.loads((root / "outcome.json").read_text())
                self.assertEqual(outcome["status"], "INCONCLUSIVE")
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate(timeout=5)
                if worker_pid is not None:
                    try:
                        os.killpg(worker_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    @unittest.skipUnless(hasattr(os, "killpg"), "requires POSIX process groups")
    def test_actual_watchdog_kills_worker_and_child_process_group(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "worker.py").write_text(
                "import pathlib,subprocess,sys,time\n"
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
                "pathlib.Path(sys.argv[3], 'child.pid').write_text(str(p.pid))\n"
                "time.sleep(60)\n")
            with patch.object(runner, "HERE", root):
                with self.assertRaises(runner.DemoError) as error:
                    runner.worker(root, "train", root / "output.json", timeout=1.0)
            self.assertEqual(error.exception.status, "INCONCLUSIVE")
            child = int((root / "child.pid").read_text())
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if process_terminated(child):
                    break
                time.sleep(0.05)
            else:
                os.kill(child, signal.SIGKILL)
                self.fail("watchdog left a child process running")

    def test_training_budget_is_reserved_to_disk_before_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = {"spent_seconds": 3599.5, "artifacts": {}}
            config = json.loads((DEMO / "fixtures/base.json").read_text())
            def fake_worker(*args, **kwargs):
                self.assertEqual(kwargs["timeout"], 0.5)
                self.assertEqual(json.loads((root / "state.json").read_text())["spent_seconds"], 3600)
                raise runner.DemoError("timeout", "INCONCLUSIVE")
            with patch.object(runner, "worker", side_effect=fake_worker):
                with self.assertRaises(runner.DemoError):
                    runner.timed_training(root, state, "base", 1, config)
            self.assertGreaterEqual(json.loads((root / "state.json").read_text())["spent_seconds"], 3599.5)
            state["spent_seconds"] = 3600
            with patch.object(runner, "worker") as mocked:
                with self.assertRaises(runner.DemoError) as error:
                    runner.timed_training(root, state, "base", 2, config)
                self.assertEqual(error.exception.status, "INCONCLUSIVE")
                mocked.assert_not_called()

    def test_evidence_and_environment_mutations_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "evidence.json"
            evidence.write_text("original")
            state = {"artifacts": {}, "environment_sha256": runner.digest({"gpu": "expected"})}
            runner.seal(root, state, evidence)
            runner.check_seals(root, state)
            evidence.write_text("altered")
            with self.assertRaises(runner.DemoError):
                runner.check_seals(root, state)
            with patch.object(runner, "worker", return_value={"gpu": "different"}):
                with self.assertRaises(runner.DemoError):
                    runner.checked_environment(root, state)

    def test_calibration_propagates_fixed_inputs_and_verify_alternates_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = {"artifacts": {}, "spent_seconds": 0}
            samples = iter([59, 60, 61])
            calls = []
            def calibration(_root, _state, kind, index, config):
                calls.append((kind, index, dict(config)))
                result = {"training_seconds": next(samples), "loading_seconds": 1, "tokenization_seconds": 1}
                (_root / f"run-calibration-{index}.json").write_text(json.dumps(result))
                return result
            with patch.object(runner, "timed_training", side_effect=calibration):
                runner.calibrate(root, state)
            base = json.loads((root / "measured-base.json").read_text())
            pr = json.loads((root / "measured-pr.json").read_text())
            self.assertEqual([x[0] for x in calls], ["calibration"] * 3)
            self.assertEqual(base["estimated_minutes_per_epoch"], 1)
            self.assertAlmostEqual(base["budget_limit_usd"], 2 / 60)
            self.assertEqual(pr, {**base, "epochs": 3})
            self.assertIn("This PR: $0.05", (root / "report.md").read_text())
            calls.clear()
            def measured(_root, _state, kind, index, config):
                calls.append((kind, index, dict(config)))
                return {"training_seconds": 60 if kind == "base" else 180}
            with patch.object(runner, "timed_training", side_effect=measured):
                runner.verify(root, state)
            self.assertEqual([x[0] for x in calls], ["base", "pr", "pr", "base", "base", "pr"])
            for kind, _, config in calls:
                self.assertEqual(config, base if kind == "base" else pr)
            self.assertEqual(json.loads((root / "verification.json").read_text())["status"], "PASS")

    def test_unrepeatable_calibration_stops_before_generating_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = {"artifacts": {}}
            samples = iter([30, 60, 100])
            with patch.object(runner, "timed_training", side_effect=lambda *args: {"training_seconds": next(samples)}):
                with self.assertRaises(runner.DemoError):
                    runner.calibrate(root, state)
            self.assertFalse((root / "measured-base.json").exists())

    def test_bundle_rejects_non_allowlisted_secret_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact = root / "private.json"
            artifact.write_text(json.dumps({"token": "hf_" + "A" * 36}))
            state = {"artifacts": {}, "source_sha256": "test"}
            runner.seal(root, state, artifact)
            with self.assertRaises(runner.DemoError):
                runner.bundle(root, state)

    def test_bundle_rejects_secret_in_allowlisted_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact = root / "preflight.json"
            artifact.write_text(json.dumps({"gpu": "hf_" + "A" * 36}))
            state = {"artifacts": {}, "source_sha256": "test"}
            runner.seal(root, state, artifact)
            with self.assertRaises(runner.DemoError):
                runner.bundle(root, state)


if __name__ == "__main__":
    unittest.main()
