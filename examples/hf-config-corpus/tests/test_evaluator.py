"""Regression checks for corpus metadata and the offline evaluator."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("verify_hf_corpus", ROOT / "scripts/verify_hf_corpus.py")
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)


class CorpusEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.corpus = evaluator.load_corpus()
        self.source = self.corpus["sources"]["transformers"]

    def test_sources_and_labels_cover_the_declared_corpus(self):
        cases = self.corpus["cases"]
        self.assertEqual(len(cases), 50)
        self.assertEqual(len({case["source"] for case in cases}), 3)
        self.assertEqual({case["label"] for case in cases}, {"accept", "reject", "stale", "unsupported", "redact"})

    def test_pair_mutations_do_not_modify_the_source_or_base(self):
        original = deepcopy(self.source)
        case = {"set": {"num_train_epochs": 9}, "top": {"gpu_type": "T4"}}
        base, head, _ = evaluator.pair_for(case, self.source)
        self.assertEqual(base, self.source["template"])
        self.assertEqual(head["training_args"]["num_train_epochs"], 9)
        self.assertEqual(head["gpu_type"], "T4")
        self.assertEqual(self.source, original)

    def test_unsafe_or_unpinned_source_is_rejected(self):
        broken = deepcopy(self.corpus)
        broken["sources"]["transformers"]["source_url"] = "https://example.invalid/unpinned"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "corpus.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            with patch.object(evaluator, "CORPUS", path), self.assertRaises(ValueError):
                evaluator.load_corpus()

    def test_positive_steps_must_explain_override(self):
        case = next(case for case in self.corpus["cases"] if case["id"] == "t06-positive-steps")
        with patch.object(evaluator, "normalize_training_config", side_effect=ValueError("Positive max_steps overrides epochs")):
            self.assertIsNone(evaluator.evaluate(case, self.source))
        with patch.object(evaluator, "normalize_training_config", side_effect=ValueError("Invalid max_steps")):
            self.assertIsNotNone(evaluator.evaluate(case, self.source))

    def test_epoch_only_false_stale_warning_is_detected(self):
        case = next(case for case in self.corpus["cases"] if case["id"] == "t02-fractional-epochs")
        normalized = SimpleNamespace(epochs=1.5)
        result = SimpleNamespace(pr_config=normalized, confidence=SimpleNamespace(level="High"),
                                 warnings=[SimpleNamespace(code="stale_runtime_assumption")], markdown_report="")
        with patch.object(evaluator, "normalize_training_config", return_value=normalized), \
                patch.object(evaluator, "analyze_config_dicts", return_value=result):
            self.assertEqual(evaluator.evaluate(case, self.source), "unexpected stale-runtime warning")

    def test_secret_in_error_is_rejected(self):
        source = self.corpus["sources"]["trl"]
        case = next(case for case in self.corpus["cases"] if case["id"] == "r17-secret-invalid-steps")
        _, _, secret = evaluator.pair_for(case, source)
        with patch.object(evaluator, "normalize_training_config", side_effect=ValueError(secret)):
            self.assertEqual(evaluator.evaluate(case, source), "sensitive value appeared in error")


if __name__ == "__main__":
    unittest.main()
