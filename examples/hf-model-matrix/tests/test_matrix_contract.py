"""Offline checks for the real-model protocol and its Action consumer."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "examples/hf-model-matrix"))
import matrix_common as common
spec = importlib.util.spec_from_file_location("matrix_controller", ROOT / "scripts/verify_hf_matrix.py")
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)
SOURCE = "a" * 64


class ProfileTests(unittest.TestCase):
    def test_three_real_architectures_are_immutable(self):
        profiles = common.load_profiles()
        self.assertEqual({p["model_type"] for p in profiles["models"]}, {"distilbert", "bert", "albert"})
        self.assertEqual(profiles["protocol"]["calibration_runs"], 3)
        self.assertEqual(profiles["protocol"]["evaluation_runs"], 3)
        for profile in profiles["models"]:
            self.assertRegex(profile["revision"], r"^[a-f0-9]{40}$")
            self.assertIn("model.safetensors", profile["files"])

    def test_reject_mutable_or_unsafe_profiles(self):
        for field, value in (("revision", "main"), ("key", "../outside"),
                             ("files", ["model.bin", "remote.py"]), ("license", "unknown")):
            with self.subTest(field=field):
                profiles = common.load_profiles()
                profiles["models"][0][field] = value
                with self.assertRaises(ValueError):
                    common.validate_profiles(profiles)
        profiles = common.load_profiles()
        profiles["schema"] = True
        with self.assertRaises(ValueError):
            common.validate_profiles(profiles)

    def test_protocol_cannot_silently_drift(self):
        for field, value in (("train_size", 128), ("calibration_runs", 1), ("run_timeout_seconds", 36000)):
            profiles = common.load_profiles()
            profiles["protocol"][field] = value
            with self.assertRaises(ValueError):
                common.validate_profiles(profiles)
        for epochs in (True, 0, 2, 3.0, float("nan")):
            with self.assertRaises(ValueError):
                common.training_settings(epochs)

    def test_json_rejects_duplicate_and_nonfinite_values(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "value.json"
            for content in ('{"x": 1, "x": 2}', '{"x": NaN}'):
                path.write_text(content)
                with self.assertRaises(ValueError):
                    common.read_json(path)

    def test_new_execution_requires_reviewed_metadata_but_history_can_replay(self):
        legacy = common.load_profiles()
        for profile in legacy["models"]:
            del profile["metadata_sha256"]
        common.validate_profiles(legacy)
        with patch.object(common, "read_json", return_value=legacy), self.assertRaises(ValueError):
            common.load_profiles()
        invalid = common.load_profiles()
        invalid["models"][0]["metadata_sha256"]["config.json"] = "not-a-hash"
        with self.assertRaises(ValueError):
            common.validate_profiles(invalid)


class ControllerTests(unittest.TestCase):
    def test_workspace_is_exclusive_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp).resolve()
            path = controller.claim_workspace(parent / "new")
            with self.assertRaises(FileExistsError):
                controller.claim_workspace(path)
            (parent / "link").symlink_to(path, target_is_directory=True)
            with self.assertRaises(controller.MatrixError):
                controller.claim_workspace(parent / "link" / "child")

    def test_watchdog_kills_and_reaps_process_group(self):
        process = Mock(pid=54321)
        process.wait.side_effect = [subprocess.TimeoutExpired("safe", 1), 0]
        with patch.object(controller.subprocess, "Popen", return_value=process) as launch, \
                patch.object(controller.os, "killpg") as kill:
            with self.assertRaises(subprocess.TimeoutExpired):
                controller.run_process(["python"], {}, 1)
        self.assertTrue(launch.call_args.kwargs["start_new_session"])
        kill.assert_called_once_with(54321, controller.signal.SIGKILL)
        self.assertEqual(process.wait.call_count, 2)

    def test_training_budget_does_not_start_another_worker(self):
        with patch.object(controller, "run_process") as run:
            with self.assertRaises(controller.MatrixError) as error:
                controller.launch(Path("/unused"), common.profile_for("bert"), "train", {"spent": 3600},
                                  phase="base-1", epochs=1)
        self.assertEqual(error.exception.status, "INCONCLUSIVE")
        run.assert_not_called()

    def test_ci_never_claims_workspace_or_launches_training(self):
        with patch.dict(controller.os.environ, {"CI": "true"}), patch.object(controller, "claim_workspace") as claim:
            self.assertEqual(controller.main(["--workspace", "/unused"]), 2)
        claim.assert_not_called()

    def test_calibration_is_frozen_before_evaluation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            seals = controller.seal_calibration(path, common.profile_for("albert"),
                                                [{"training_seconds": x} for x in (10, 12, 11)], "abc")
            self.assertEqual(common.read_json(path / "calibration.json")["median_seconds"], 11)
            controller.check_seals(path, seals)
            with self.assertRaises(FileExistsError):
                controller.seal_calibration(path, common.profile_for("albert"),
                                            [{"training_seconds": 15}] * 3, "abc")
            # The existing evidence must not be modified when new observations arrive.
            (path / "measured-base.json").write_text("{}")
            with self.assertRaises(controller.MatrixError):
                controller.check_seals(path, seals)

    def test_independent_oracle_keeps_failed_time_extrapolation(self):
        result = controller.evaluate_measurements([10, 10, 10], [10, 10, 10], [18, 18, 18])
        self.assertEqual(result["status"], "FAIL")
        self.assertGreater(result["relative_errors"]["pr"], .2)
        self.assertTrue(all(result["repeatable"].values()))

    def test_real_action_outputs_and_decimal_costs_for_all_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp).resolve()
            for profile in common.load_profiles()["models"]:
                with self.subTest(model=profile["key"]):
                    directory = workspace / profile["key"]
                    directory.mkdir()
                    seals = controller.seal_calibration(directory, profile,
                        [{"training_seconds": x} for x in (24, 24, 24)], "fixture-not-gpu")
                    result = controller.action_report(workspace, profile, seals)
                    self.assertEqual(result["status"], "PASS")
                    self.assertAlmostEqual(result["base_usd"], 24 / 3600)
                    self.assertAlmostEqual(result["pr_usd"], 72 / 3600)
                    document = common.read_json(directory / "report.json")
                    report = (directory / "report.md").read_text()
                    document["analyses"][0]["base"]["estimate"]["estimated_cost_usd"] = 0
                    with self.assertRaises(controller.MatrixError):
                        controller.check_report_document(document, report, .4)

    def test_bundle_excludes_data_weights_and_action_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            common.write_json(root / "run-contract.json", {"schema": 1, "source_sha256": SOURCE,
                "profiles": common.load_profiles(), "selected_models": ["bert"]})
            results = {"bert": {"compatibility_status": "INCONCLUSIVE", "report_status": "NOT_RUN",
                                "timing_status": "NOT_RUN", "reason": "TIMEOUT"}}
            outcome = {**controller.aggregate_status(results), "source_sha256": SOURCE,
                       "training_process_seconds": 600, "models": results}
            common.write_json(root / "outcome.json", outcome)
            cache = root / "bert/cache"
            cache.mkdir(parents=True)
            (cache / "model.safetensors").write_bytes(b"not-a-real-weight")
            (root / "bert/action-output.txt").write_text("private-path")
            controller.export_bundle(root, [common.profile_for("bert")], outcome)
            names = set(common.read_json(root / "bundle/manifest.json")["files"])
            self.assertEqual(names, {"run-contract.json", "outcome.json"})
            self.assertEqual(controller.verify_bundle(root / "bundle")["status"], "INCONCLUSIVE")
            (root / "bundle/outcome.json").write_text("{}")
            with self.assertRaises(controller.MatrixError):
                controller.verify_bundle(root / "bundle")

    def test_incomplete_time_is_not_a_measured_failure(self):
        result = {"compatibility_status": "INCONCLUSIVE", "report_status": "NOT_RUN", "timing_status": "NOT_RUN"}
        self.assertEqual(controller.aggregate_status({"bert": result})["timing_status"], "INCONCLUSIVE")
        result.update(compatibility_status="PASS", report_status="PASS", timing_status="FAIL")
        self.assertEqual(controller.aggregate_status({"bert": result})["status"], "FAIL")

    def test_bundle_rejects_extra_sensitive_metadata_fields(self):
        failure = {"compatibility_status": "FAIL", "report_status": "NOT_RUN",
                   "timing_status": "NOT_RUN", "reason": "opaque-private-value"}
        with self.assertRaises(controller.MatrixError):
            controller.validate_export("result.json", failure)
        failure.update(reason="TIMEOUT", compatibility_status="opaque-private-value")
        with self.assertRaises(controller.MatrixError):
            controller.validate_export("result.json", failure)
        value = {"status": "PASS", "environment": {}, "source_sha256": "source", "profile_sha256": "profile",
                 "private_notes": "not necessarily a recognizable credential"}
        with self.assertRaises(controller.MatrixError):
            controller.validate_export("prepare.json", value)
        value.pop("private_notes")
        value["environment"] = {"os": [], "machine": "arm64", "python": "3.12", "device": "mps",
                                "packages": {}, "lock_sha256": "hash", "environment_variables": {}}
        with self.assertRaises(controller.MatrixError):
            controller.validate_export("prepare.json", value)

    def test_full_controller_freezes_calibration_and_rechecks_bundle(self):
        profile = common.profile_for("distilbert")
        env = {"os": ["26.6.2", ["", "", ""], "arm64"], "machine": "arm64", "python": "3.12.8",
               "device": "mps", "lock_sha256": "b" * 64, "packages": {name: "1.0.0" for name in
               ("torch", "transformers", "accelerate", "datasets", "safetensors", "numpy", "huggingface-hub")}}
        selection = {"source_sha256": SOURCE, "profile_sha256": common.digest(profile),
                     "model_files_sha256": {name: "c" * 64 for name in profile["files"]}, "prepare_seconds": 1.0}
        for split in ("train", "test"):
            selection[split] = {"size": 64, "indices": list(range(64)), "indices_sha256": common.digest(list(range(64))),
                                "content_sha256": common.digest(split), "label_counts": [32, 32]}
        order = []
        def launch(workspace, profile, stage, budget, *, phase=None, epochs=None):
            directory = workspace / profile["key"]
            if stage == "prepare":
                directory.mkdir()
                prepared = {"status": "PASS", "environment": env, "source_sha256": SOURCE,
                            "profile_sha256": common.digest(profile)}
                common.write_json(directory / "prepare.json", prepared)
                common.write_json(directory / "selection.json", selection)
                return prepared
            order.append(phase)
            if not phase.startswith("calibration"):
                self.assertTrue((directory / "calibration.json").is_file())
            actual = {**common.training_settings(epochs), "report_to": [], "world_size": 1, "device": "mps"}
            hashes = {split: common.digest(split) for split in ("train", "test")}
            condition = common.digest({"profile": profile, "model_files_sha256": selection["model_files_sha256"],
                "subset_content_sha256": hashes, "environment": env,
                "training_settings": {k: v for k, v in actual.items() if k != "num_train_epochs"},
                "attention_implementation": "eager"})
            run = {"status": "PASS", "phase": phase, "epochs": epochs, "environment": env,
                "model_id": profile["model_id"], "model_revision": profile["revision"], "source_sha256": SOURCE,
                "profile_sha256": common.digest(profile), "condition_sha256": condition,
                "config": common.hf_config(profile, epochs, 6.0, .2), "observed_training_arguments": actual,
                "attention_implementation": "eager", "model_type": profile["model_type"], "parameter_count": 100,
                "encoder_parameter_name": "embeddings.weight", "encoder_updated": True,
                "finite_gradients_checked": 8 * epochs, "updates": 8 * epochs,
                "training_loss": .7, "losses": [.7] * (8 * epochs), "accuracy": .5, "f1": .4,
                "loading_seconds": 1.0, "tokenization_seconds": 1.0, "training_seconds": 24.0 * epochs,
                "parameter_check_seconds": 1.0, "evaluation_seconds": 1.0,
                "sampled_peak_process_rss_bytes": 100, "sampled_peak_mps_allocated_bytes": 100,
                "subset_content_sha256": hashes}
            common.write_json(directory / (phase + ".json"), run)
            return run
        with tempfile.TemporaryDirectory() as temp, patch.object(controller, "launch", side_effect=launch):
            root = Path(temp).resolve()
            common.write_json(root / "run-contract.json", {"schema": 1, "source_sha256": SOURCE,
                "profiles": common.load_profiles(), "selected_models": ["distilbert"]})
            result = controller.run_model(root, profile, SOURCE, {"spent": 0})
            self.assertEqual(order, ["calibration-1", "calibration-2", "calibration-3", "base-1", "pr-1",
                                     "pr-2", "base-2", "base-3", "pr-3"])
            common.write_json(root / "distilbert/result.json", result)
            outcome = {**controller.aggregate_status({"distilbert": result}), "source_sha256": SOURCE,
                       "training_process_seconds": 100, "models": {"distilbert": result}}
            common.write_json(root / "outcome.json", outcome)
            controller.export_bundle(root, [profile], outcome)
            self.assertEqual(controller.verify_bundle(root / "bundle")["status"], "PASS")
            report = common.read_json(root / "distilbert/report.json")
            report["analyses"][0]["unexpected_private_note"] = "opaque-private-value"
            (root / "distilbert/report.json").write_text(json.dumps(report))
            with self.assertRaises(controller.MatrixError):
                controller.reproduce_report(root / "distilbert")

    def test_nested_subset_metadata_cannot_carry_arbitrary_values(self):
        subset = {"size": 64, "indices": list(range(64)), "indices_sha256": common.digest(list(range(64))),
                  "content_sha256": "b" * 64, "label_counts": [32, 32]}
        value = {"model_files_sha256": {"model.safetensors": "c" * 64}, "source_sha256": SOURCE,
                 "profile_sha256": "d" * 64, "prepare_seconds": 1.0,
                 "train": deepcopy(subset), "test": deepcopy(subset)}
        controller.validate_export("selection.json", value)
        for key, bad in (("label_counts", {"private_note": "opaque-value"}),
                         ("indices", ["opaque-value"] * 64), ("content_sha256", "opaque-value")):
            mutated = deepcopy(value)
            mutated["train"][key] = bad
            with self.subTest(key=key), self.assertRaises(controller.MatrixError):
                controller.validate_export("selection.json", mutated)


if __name__ == "__main__":
    unittest.main()
