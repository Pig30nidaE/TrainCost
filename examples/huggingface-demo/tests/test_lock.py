from pathlib import Path
import re
import unittest


DEMO = Path(__file__).resolve().parents[1]


class LockTests(unittest.TestCase):
    def test_transitive_lock_entries_are_pinned_and_hashed(self):
        text = (DEMO / "requirements.lock").read_text()
        records = []
        for raw in text.replace("\\\n", " ").splitlines():
            line = raw.strip()
            if line and not line.startswith(("#", "--index-url", "--extra-index-url")):
                records.append(line)
        self.assertGreaterEqual(len(records), 60, "expected transitive dependencies, not only direct pins")
        pins = {}
        for record in records:
            with self.subTest(record=record[:80]):
                if record.startswith("torch @ "):
                    self.assertIn("torch-2.9.1%2Bcu126-cp312-cp312-manylinux_2_28_x86_64.whl", record)
                    self.assertRegex(record, r"#sha256=[0-9a-f]{64}")
                    self.assertRegex(record, r"--hash=sha256:[0-9a-f]{64}")
                    pins["torch"] = "2.9.1+cu126"
                    continue
                pin = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", record)
                self.assertIsNotNone(pin, "lock entry must have an exact version")
                hashes = re.findall(r"--hash=sha256:([0-9a-f]+)", record)
                self.assertTrue(hashes, "lock entry lacks hashes")
                self.assertTrue(all(len(value) == 64 for value in hashes))
                pins[pin.group(1).lower()] = pin.group(2)
        self.assertEqual(pins["torch"], "2.9.1+cu126")
        self.assertEqual(pins["transformers"], "4.57.6")
        self.assertEqual(pins["accelerate"], "1.15.0")
        self.assertEqual(pins["datasets"], "4.8.5")
        self.assertIn("huggingface-hub", pins)
        self.assertIn("pyyaml", pins)


if __name__ == "__main__":
    unittest.main()
