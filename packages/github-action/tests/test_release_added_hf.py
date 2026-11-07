"""Real-Git coverage for added Hugging Face configurations."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ACTION = Path(__file__).resolve().parents[1] / "traincost_action.py"
HF_BASE = {"num_train_epochs": 1, "per_device_train_batch_size": 8,
           "world_size": 1, "gpu_type": "T4", "estimated_minutes_per_epoch": 6}


class AddedHuggingFaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git("init", "-q")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test",
                               "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false", *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "test", "--allow-empty")
        return self.git("rev-parse", "HEAD")

    def invoke(self, base, head):
        event = self.root / "event.json"
        event.write_text(json.dumps({"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}))
        env = {**os.environ, "GITHUB_OUTPUT": str(self.root / "outputs"),
               "GITHUB_STEP_SUMMARY": str(self.root / "summary"), "GITHUB_EVENT_NAME": "pull_request",
               "GITHUB_EVENT_PATH": str(event), "GITHUB_WORKSPACE": str(self.root)}
        run = subprocess.run([sys.executable, "-I", str(ACTION), "--config-path", "configs/*.json",
                              "--config-adapter", "huggingface", "--gpu-prices", "T4=1",
                              "--comment-mode", "false"], cwd=self.root, env=env,
                             capture_output=True, text=True, timeout=30)
        report = (self.root / "report.md").read_text(encoding="utf-8")
        document = json.loads((self.root / "report.json").read_text(encoding="utf-8"))
        outputs = (self.root / "outputs").read_text(encoding="utf-8")
        self.assertEqual(report, (self.root / "summary").read_text(encoding="utf-8"))
        self.assertIn("comment-posted=false", outputs)
        self.assertIn("analysis-status=" + document["analysis_status"], outputs)
        return run, report, document

    def test_added_hf_config_uses_illustrative_absent_base(self):
        base = self.commit()
        self.write("configs/added.json", {**HF_BASE, "num_train_epochs": 3})
        head = self.commit()
        run, report, document = self.invoke(base, head)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(document["analysis_status"], "complete")
        self.assertEqual(document["summary"]["analyzed_count"], 1)
        self.assertEqual(document["summary"]["excluded_count"], 0)
        self.assertAlmostEqual(document["summary"]["base_cost_usd"], 0.5)
        self.assertAlmostEqual(document["summary"]["pr_cost_usd"], 0.3)
        self.assertIn("no base file exists", report)
        self.assertIn("illustrative", report)
        self.assertIn("no base file exists", " ".join(document["diagnostics"]))

    def test_added_modified_and_invalid_configs_are_partial_with_correct_totals(self):
        self.write("configs/modified.json", HF_BASE)
        base = self.commit()
        self.write("configs/modified.json", {**HF_BASE, "num_train_epochs": 2})
        self.write("configs/added.json", {**HF_BASE, "num_train_epochs": 3})
        self.write("configs/invalid.json", {"model_type": "distilbert"})
        head = self.commit()
        run, report, document = self.invoke(base, head)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(document["analysis_status"], "partial")
        self.assertEqual(document["summary"]["analyzed_count"], 2)
        self.assertEqual(document["summary"]["excluded_count"], 1)
        self.assertAlmostEqual(document["summary"]["base_cost_usd"], 0.6)
        self.assertAlmostEqual(document["summary"]["pr_cost_usd"], 0.5)
        self.assertEqual({item["path"] for item in document["analyses"]},
                         {"configs/added.json", "configs/modified.json"})
        self.assertIn("Excluded configs: 1", report)
        self.assertIn("model-only", " ".join(document["diagnostics"]))

    def test_existing_or_added_empty_and_model_only_heads_remain_invalid(self):
        for existing in (False, True):
            for invalid in ({}, {"model_type": "distilbert"}):
                with self.subTest(existing=existing, invalid=invalid), tempfile.TemporaryDirectory() as temp:
                    root = self.root
                    self.root = Path(temp).resolve()
                    try:
                        self.git("init", "-q")
                        if existing:
                            self.write("configs/config.json", HF_BASE)
                        base = self.commit()
                        self.write("configs/config.json", invalid)
                        head = self.commit()
                        run, _, document = self.invoke(base, head)
                        self.assertEqual(run.returncode, 2)
                        self.assertEqual(document["analysis_status"], "error")
                        self.assertEqual(document["analyses"], [])
                        self.assertIsNone(document["summary"]["base_cost_usd"])
                    finally:
                        self.root = root


if __name__ == "__main__":
    unittest.main()
