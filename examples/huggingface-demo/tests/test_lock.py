from pathlib import Path
import re
import unittest


DEMO = Path(__file__).resolve().parents[1]


class LockTests(unittest.TestCase):
    def parse_lock(self, filename, minimum):
        text = (DEMO / filename).read_text()
        records = []
        for raw in text.replace("\\\n", " ").splitlines():
            line = raw.strip()
            if line and not line.startswith(("#", "--index-url", "--extra-index-url")):
                records.append(line)
        self.assertGreaterEqual(len(records), minimum, "expected transitive dependencies, not only direct pins")
        pins = {}
        for record in records:
            with self.subTest(lock=filename, record=record[:80]):
                if record.startswith("torch @ "):
                    expected_url = ("https://download.pytorch.org/whl/cu130/"
                                    "torch-2.14.1%2Bcu130-cp312-cp312-manylinux_2_28_x86_64.whl")
                    sha = "5359b255ac68c0cabb8293952b38e00f0d1a570815cd87f19b61af702c071410"
                    self.assertIn(expected_url + "#sha256=" + sha, record)
                    self.assertIn("--hash=sha256:" + sha, record)
                    pins["torch"] = "2.14.1+cu130"
                    continue
                pin = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", record)
                self.assertIsNotNone(pin, "lock entry must have an exact version")
                hashes = re.findall(r"--hash=sha256:([0-9a-f]+)", record)
                self.assertTrue(hashes, "lock entry lacks hashes")
                self.assertTrue(all(len(value) == 64 for value in hashes))
                pins[pin.group(1).lower()] = pin.group(2)
        self.assertEqual(pins["transformers"], "5.22.2")
        self.assertEqual(pins["accelerate"], "1.15.0")
        self.assertEqual(pins["datasets"], "5.1.0")
        self.assertEqual(pins["fsspec"], "2026.7.0")
        self.assertEqual(pins["huggingface-hub"], "1.31.0")
        self.assertEqual(pins["pyyaml"], "6.0.3")
        return pins

    def test_cuda_lock_is_pinned_and_hashed(self):
        pins = self.parse_lock("requirements.lock", 60)
        self.assertEqual(pins["torch"], "2.14.1+cu130")
        self.assertIn("nvidia-cuda-runtime", pins)

    def test_macos_lock_is_pinned_and_hashed(self):
        pins = self.parse_lock("macos-requirements.lock", 45)
        self.assertEqual(pins["torch"], "2.14.1")
        self.assertNotIn("nvidia-cuda-runtime", pins)

    def test_input_files_match_reviewed_direct_pins(self):
        for name in ("requirements.in", "macos-requirements.in"):
            with self.subTest(input=name):
                text = (DEMO / name).read_text()
                for pin in ("transformers==5.22.2", "accelerate==1.15.0", "datasets==5.1.0",
                            "huggingface-hub==1.31.0", "fsspec==2026.7.0", "PyYAML==6.0.3"):
                    self.assertIn(pin, text)
        self.assertIn("torch==2.14.1", (DEMO / "macos-requirements.in").read_text())
        self.assertIn("torch-2.14.1%2Bcu130-cp312-cp312-manylinux_2_28_x86_64.whl",
                      (DEMO / "requirements.in").read_text())


if __name__ == "__main__":
    unittest.main()
