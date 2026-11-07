import importlib.util
from pathlib import Path
import sys
import unittest


DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO))
SPEC = importlib.util.spec_from_file_location("hf_demo_worker", DEMO / "worker.py")
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class FakeDataset:
    def __init__(self, labels):
        self.labels = labels

    def __getitem__(self, key):
        if key == "label":
            return self.labels
        raise KeyError(key)


class BalancedTests(unittest.TestCase):
    def test_balanced_selection_is_exact_unique_and_seeded(self):
        data = FakeDataset([0] * 700 + [1] * 700)
        selected = worker.balanced_indices(data, 1024, 42)
        self.assertEqual(len(selected), 1024)
        self.assertEqual(len(set(selected)), 1024)
        self.assertEqual(sum(data.labels[index] for index in selected), 512)
        self.assertEqual(selected, worker.balanced_indices(data, 1024, 42))
        self.assertNotEqual(selected, worker.balanced_indices(data, 1024, 43))

    def test_unbalanced_or_odd_sample_rejected(self):
        for data, count in ((FakeDataset([0] * 4 + [1] * 3), 8),
                            (FakeDataset([0] * 8 + [1] * 8), 7)):
            with self.subTest(count=count), self.assertRaises(ValueError):
                worker.balanced_indices(data, count, 42)

    def test_train_text_is_excluded_from_balanced_test_selection(self):
        data = {"label": [0, 0, 1, 1], "text": ["duplicate", "test-0", "test-1", "test-2"]}
        selected = worker.balanced_indices(data, 2, 42, {worker.text_hash("duplicate")})
        self.assertNotIn(0, selected)
        self.assertEqual({data["label"][i] for i in selected}, {0, 1})
        with self.assertRaises(ValueError):
            worker.balanced_indices(data, 4, 42, {worker.text_hash("duplicate")})


if __name__ == "__main__":
    unittest.main()
