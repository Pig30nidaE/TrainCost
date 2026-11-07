"""Replay the fixed candidate's public branch and real fork runs."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("consumer_archive",
    ROOT.parent / "external-consumer-2026-11-08/verify.py")
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def verify():
    for fork in (False, True):
        archive.verify(fork=fork, root=ROOT,
            candidate="a907b78423cd18b5e7a8f53f5d092fcba6df77e9",
            head_sha="fe7e9778257a24a5efa884c94fb08d7b5068281d",
            branch_run=42406963444, fork_run=42406970081, fork_job=128506846257,
            workflow_blob="dbd81fc78d2599db80973b1179041cd8f8856cc8")
        directory = ROOT / "fork" if fork else ROOT
        report = (directory / "reports/modified.md").read_text()
        assert "Merge-base estimate: $0.10" in report
        assert "PR-head estimate: $0.30" in report
        assert "Base branch:" not in report
        data = json.loads((directory / "reports/modified.json").read_text())
        assert "Comparison baseline: merge base bb0b5b974e7e702a9232ea3434dfb62da30b3c70." in data["diagnostics"]


if __name__ == "__main__":
    verify()
    print("Fixed-candidate branch and real fork archives: PASS. Not a fresh hosted run.")
