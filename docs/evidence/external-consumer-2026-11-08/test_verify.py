"""Regression checks for confusing an ordinary PR with the real fork run."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("consumer_archive", Path(__file__).with_name("verify.py"))
ARCHIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ARCHIVE)


class ArchiveIdentityTests(unittest.TestCase):
    def test_both_archives_pass(self):
        ARCHIVE.verify()
        ARCHIVE.verify(fork=True)

    def test_fork_identity_and_contract_mutations_are_rejected(self):
        cases = (
            ("run.json", lambda data: data.update(id=42403549313)),
            ("run.json", lambda data: data.update(run_attempt=1)),
            ("run.json", lambda data: data["head_repository"].update(id=1449646378)),
            ("pr.json", lambda data: data.update(number=1)),
            ("pr.json", lambda data: data["head"].update(id=1449646378)),
            ("reports/verification.json", lambda data: data.update(pr_number=1)),
            ("reports/verification.json", lambda data: data.update(head_is_fork=False)),
            ("reports/verification.json", lambda data: data.update(distinct_head_repository=False)),
            ("reports/verification.json", lambda data: data.update(candidate_sha="0" * 40)),
            ("permissions.json", lambda data: data["permissions"].update(Contents="write")),
            ("reports/modified.json", lambda data: data["analyses"][0].update(increase_percent=201)),
            ("workflow.json", lambda data: data.update(sha="0" * 40)),
        )
        original = Path.read_text
        for index, (relative, mutate) in enumerate(cases):
            target = ARCHIVE.ROOT / "fork" / relative

            def changed(path, *args, **kwargs):
                text = original(path, *args, **kwargs)
                if path == target:
                    data = json.loads(text)
                    mutate(data)
                    return json.dumps(data)
                return text

            with self.subTest(index=index, file=relative):
                with patch.object(Path, "read_text", changed):
                    with self.assertRaises(AssertionError):
                        ARCHIVE.verify(fork=True)


if __name__ == "__main__":
    unittest.main()
