"""Bind measurements to immutable Git source without executing historical code."""
from __future__ import annotations

import hashlib
import os
from pathlib import PurePosixPath
import re
import subprocess

from matrix_common import ROOT, SOURCE_POLICIES, SOURCE_POLICY_VERSION, digest, execution_paths, source_manifest


def git_bytes(root, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    result = subprocess.run(["git", "--no-replace-objects", "-C", str(root), *args],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=15, check=False)
    if result.returncode:
        raise ValueError("Measured Git source is unavailable; use a full checkout")
    return result.stdout


def validate_snapshot(snapshot):
    if (not isinstance(snapshot, dict)
            or set(snapshot) != {"schema", "inventory_version", "commit", "source_sha256", "files"}
            or type(snapshot["schema"]) is not int or snapshot["schema"] != 1
            or not isinstance(snapshot["commit"], str)
            or not re.fullmatch(r"[a-f0-9]{40}", snapshot["commit"])
            or not isinstance(snapshot["files"], dict) or not 1 <= len(snapshot["files"]) <= 256):
        raise ValueError("Invalid measured source snapshot")
    for name, sha in snapshot["files"].items():
        path = PurePosixPath(name)
        if (not re.fullmatch(r"[a-zA-Z0-9_./-]{1,240}", name) or path.is_absolute()
                or str(path) != name or ".." in path.parts
                or not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha)):
            raise ValueError("Invalid measured source path or hash")
    if snapshot["source_sha256"] != digest(snapshot["files"]):
        raise ValueError("Measured source digest does not match its files")
    execution_paths(snapshot["files"], snapshot["inventory_version"])


def verify_snapshot(snapshot, *, root=ROOT):
    validate_snapshot(snapshot)
    commit = snapshot["commit"]
    resolved = git_bytes(root, "rev-parse", "--verify", commit + "^{commit}").decode().strip()
    if resolved != commit:
        raise ValueError("Measurement revision is not a commit")
    tree = {}
    for entry in git_bytes(root, "ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if entry:
            metadata, name = entry.split(b"\t", 1)
            mode, kind, oid = metadata.split()
            tree[name.decode("utf-8")] = (mode, kind, oid)
    if set(snapshot["files"]) != set(execution_paths(tree, snapshot["inventory_version"])):
        raise ValueError("Measured source inventory is incomplete")
    directories = SOURCE_POLICIES[snapshot["inventory_version"]][1]
    if any(mode not in (b"100644", b"100755")
           and any(name.startswith(directory + "/") for directory in directories)
           for name, (mode, _, _) in tree.items()):
        raise ValueError("Measured source is not a regular tracked file")
    for name, expected in snapshot["files"].items():
        if name not in tree or tree[name][:2] not in {(b"100644", b"blob"), (b"100755", b"blob")}:
            raise ValueError("Measured source is not a regular tracked file")
        content = git_bytes(root, "cat-file", "blob", tree[name][2].decode("ascii"))
        if len(content) > 1_000_000 or hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Measured source differs from its commit")
    return snapshot


def capture_snapshot():
    files = source_manifest()
    snapshot = {"schema": 1, "inventory_version": SOURCE_POLICY_VERSION,
                "commit": git_bytes(ROOT, "rev-parse", "HEAD").decode().strip(),
                "source_sha256": digest(files), "files": files}
    verify_snapshot(snapshot, root=ROOT)
    return snapshot
