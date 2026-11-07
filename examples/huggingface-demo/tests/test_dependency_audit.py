from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.audit_ml_dependencies import audit_complete, audit_requirements


class DependencyAuditTests(unittest.TestCase):
    digest = "a" * 64

    def test_exact_hashed_pins(self):
        record = "# lock\n--index-url https://pypi.org/simple\nPyYAML==6.0.3 " + "\\" + "\n" + f" --hash=sha256:{self.digest}\n"
        self.assertEqual(audit_requirements(record), {"pyyaml": "6.0.3"})

    def test_cuda_public_version_without_fetching_wheel(self):
        text = ("torch @ https://download.pytorch.org/whl/cu130/"
                f"torch-2.14.1%2Bcu130-cp312-cp312-manylinux_2_28_x86_64.whl#sha256={self.digest}"
                f" --hash=sha256:{self.digest}")
        self.assertEqual(audit_requirements(text), {"torch": "2.14.1"})
        for old, new in (("download.pytorch.org", "example.org"), ("cu130", "cu126"),
                         ("cp312", "cp311"), ("#sha256=" + self.digest, "#sha256=" + "b" * 64)):
            with self.subTest(replacement=new), self.assertRaises(ValueError):
                audit_requirements(text.replace(old, new))

    def test_invalid_or_ambiguous_locks_fail(self):
        with self.assertRaises(ValueError):
            audit_requirements("pkg==1.0")
        for text in ("", "pkg>=1", "pkg==1.*", "pkg[x]==1",
                     "pkg==1; python_version > '3'", "--extra-index-url https://example.org"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                audit_requirements(text + (f" --hash=sha256:{self.digest}" if text else ""))
        record = f"pkg==1 --hash=sha256:{self.digest}\n"
        with self.assertRaises(ValueError):
            audit_requirements(record + record)

    def test_missing_skipped_or_duplicate_results_fail(self):
        item = {"name": "pkg", "version": "1", "vulns": []}
        self.assertTrue(audit_complete({"dependencies": [item]}, {"pkg": "1"}))
        for records in ([], [item, item], [{**item, "skip_reason": "unknown"}],
                        [{**item, "version": "2"}], [{"name": "pkg", "version": "1"}]):
            self.assertFalse(audit_complete({"dependencies": records}, {"pkg": "1"}))


if __name__ == "__main__":
    unittest.main()
