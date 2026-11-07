"""Real Git objects must reproduce the measured execution-source hashes."""
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "examples/hf-model-matrix"))
import matrix_common as common
import provenance


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Synthetic provenance test")
        names = common.SOURCE_POLICIES[common.SOURCE_POLICY_VERSION][0] | {"examples/hf-model-matrix/matrix_common.py",
                                       "packages/core/src/traincost_ci_core/core.py"}
        files = {}
        for name in names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic source only\n")
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic source")
        self.snapshot = {"schema": 1, "inventory_version": common.SOURCE_POLICY_VERSION, "commit": self.git("rev-parse", "HEAD"),
                         "files": files, "source_sha256": common.digest(files)}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args],
                                       stderr=subprocess.DEVNULL).decode().strip()

    def test_committed_snapshot_survives_worktree_changes(self):
        target = self.root / "examples/hf-model-matrix/matrix_common.py"
        target.write_text("different current worktree\n")
        self.assertEqual(provenance.verify_snapshot(self.snapshot, root=self.root), self.snapshot)

    def test_unknown_commit_and_changed_blob_are_rejected(self):
        for field in ("commit", "files"):
            snapshot = deepcopy(self.snapshot)
            if field == "commit":
                snapshot[field] = "0" * 40
            else:
                snapshot[field]["examples/hf-model-matrix/matrix_common.py"] = "0" * 64
                snapshot["source_sha256"] = common.digest(snapshot["files"])
            with self.subTest(field=field), self.assertRaises(ValueError):
                provenance.verify_snapshot(snapshot, root=self.root)

    def test_missing_source_cannot_be_hidden_by_rehashing(self):
        del self.snapshot["files"]["examples/hf-model-matrix/matrix_common.py"]
        self.snapshot["source_sha256"] = common.digest(self.snapshot["files"])
        with self.assertRaisesRegex(ValueError, "inventory"):
            provenance.verify_snapshot(self.snapshot, root=self.root)

    def test_unsafe_path_mutable_revision_and_schema_fail(self):
        for change in ({"commit": "main"}, {"schema": True}, {"inventory_version": 99},
                       {"inventory_version": True}, {"files": {"../secret": "a" * 64}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                provenance.validate_snapshot({**self.snapshot, **change})

    def test_capture_rejects_uncommitted_execution_changes(self):
        with patch.object(provenance, "ROOT", self.root), \
                patch.object(provenance, "source_manifest", return_value=self.snapshot["files"]):
            self.assertEqual(provenance.capture_snapshot(), self.snapshot)
        modified = {**self.snapshot["files"], "examples/hf-model-matrix/matrix_common.py": "0" * 64}
        with patch.object(provenance, "ROOT", self.root), \
                patch.object(provenance, "source_manifest", return_value=modified), \
                self.assertRaises(ValueError):
            provenance.capture_snapshot()

    def test_tracked_symlink_is_not_an_execution_source(self):
        path = self.root / "examples/hf-model-matrix/matrix_common.py"
        path.unlink()
        path.symlink_to("profiles.json")
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic symlink")
        self.snapshot["commit"] = self.git("rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "regular tracked"):
            provenance.verify_snapshot(self.snapshot, root=self.root)

    def test_nested_runtime_module_is_included_but_tests_are_not(self):
        name = "packages/core/src/traincost_ci_core/adapters/nested.py"
        path = self.root / name
        path.parent.mkdir()
        path.write_bytes(b"nested original source\n")
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "Nested source")
        self.snapshot["commit"] = self.git("rev-parse", "HEAD")
        self.snapshot["files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.snapshot["source_sha256"] = common.digest(self.snapshot["files"])
        provenance.verify_snapshot(self.snapshot, root=self.root)
        with patch.object(common, "ROOT", self.root):
            self.assertIn(name, common.source_manifest())
            path.write_bytes(b"uncommitted nested change\n")
            self.snapshot["files"] = common.source_manifest()
        self.snapshot["source_sha256"] = common.digest(self.snapshot["files"])
        with self.assertRaisesRegex(ValueError, "differs"):
            provenance.verify_snapshot(self.snapshot, root=self.root)
        self.assertNotIn("examples/hf-model-matrix/tests/example.py", common.execution_paths(
            set(self.snapshot["files"]) | {"examples/hf-model-matrix/tests/example.py"}))

    def test_future_inventory_policy_does_not_invalidate_old_snapshot(self):
        with patch.dict(common.SOURCE_POLICIES, {99: (common.SOURCE_FIXED | {"future.py"}, common.SOURCE_DIRS)}):
            provenance.verify_snapshot(self.snapshot, root=self.root)
            with self.assertRaises(ValueError):
                common.execution_paths(self.snapshot["files"], version=99)

    def test_inventory_v1_survives_v2_helper_addition(self):
        self.snapshot["inventory_version"] = 1
        del self.snapshot["files"]["examples/huggingface-demo/model_safety.py"]
        self.snapshot["source_sha256"] = common.digest(self.snapshot["files"])
        provenance.verify_snapshot(self.snapshot, root=self.root)

    def test_symlinked_module_directory_cannot_hide_sources(self):
        target = self.root / "external"
        target.mkdir()
        (target / "hidden.py").write_text("synthetic module\n")
        link = self.root / "examples/hf-model-matrix/linked"
        link.symlink_to(target, target_is_directory=True)
        with patch.object(common, "ROOT", self.root), self.assertRaisesRegex(ValueError, "symlinks"):
            common.source_manifest()
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic directory symlink")
        self.snapshot["commit"] = self.git("rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "regular tracked"):
            provenance.verify_snapshot(self.snapshot, root=self.root)


if __name__ == "__main__":
    unittest.main()
