"""Replay registered real-model evidence without downloads, training, or GitHub."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_hf_matrix as matrix

INDEX = ROOT / "examples/hf-model-matrix/evidence-index.json"
STUDY_KEYS = {"id", "bundle", "manifest_sha256", "measured_source_sha256", "measured_commit",
              "source_snapshot_available", "models", "expected_status"}


def verify(index_path=INDEX, *, root=ROOT):
    index = matrix.read_json(index_path)
    if (not isinstance(index, dict) or set(index) != {"schema", "studies"}
            or type(index["schema"]) is not int or index["schema"] != 1
            or not isinstance(index["studies"], list) or not index["studies"]):
        raise ValueError("Invalid evidence index")
    profiles = {p["key"]: p for p in matrix.load_profiles()["models"]}
    seen, covered, summaries = set(), set(), []
    for study in index["studies"]:
        if not isinstance(study, dict) or set(study) != STUDY_KEYS:
            raise ValueError("Invalid study registration")
        if (not isinstance(study["id"], str) or not re.fullmatch(r"[a-z0-9-]{1,100}", study["id"])
                or study["id"] in seen):
            raise ValueError("Invalid or duplicate study identity")
        seen.add(study["id"])
        for field in ("manifest_sha256", "measured_source_sha256"):
            if not isinstance(study[field], str) or not re.fullmatch(r"[a-f0-9]{64}", study[field]):
                raise ValueError("Invalid study hash")
        commit = study["measured_commit"]
        if commit is not None and (not isinstance(commit, str) or not re.fullmatch(r"[a-f0-9]{40}", commit)):
            raise ValueError("A measured commit must be an immutable SHA")
        if type(study["source_snapshot_available"]) is not bool:
            raise ValueError("Invalid source availability flag")
        if (not isinstance(study["models"], list) or not study["models"]
                or any(not isinstance(key, str) or key not in profiles for key in study["models"])
                or len(study["models"]) != len(set(study["models"]))):
            raise ValueError("Invalid model coverage")
        relative = study["bundle"]
        if (not isinstance(relative, str)
                or not re.fullmatch(r"docs/evidence/[a-z0-9-]+/bundle", relative)):
            raise ValueError("Evidence must use a repository-local bundle")
        directory = root / relative
        if any(p.is_symlink() for p in (directory, *directory.parents)):
            raise ValueError("Evidence paths cannot contain symlinks")
        if matrix.file_digest(directory / "manifest.json") != study["manifest_sha256"]:
            raise ValueError("Registered manifest changed")
        manifest = matrix.read_json(directory / "manifest.json")
        actual_files = set()
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ValueError("Evidence cannot contain symlinks")
            if path.is_file():
                actual_files.add(path.relative_to(directory).as_posix())
        if actual_files != set(manifest["files"]) | {"manifest.json"}:
            raise ValueError("Bundle contains missing or unregistered artifacts")
        outcome = matrix.verify_bundle(directory)
        contract = matrix.read_json(directory / "run-contract.json")
        expected = study["expected_status"]
        status_keys = {"status", "compatibility_status", "report_status", "timing_status"}
        if (not isinstance(expected, dict) or set(expected) != status_keys
                or any(expected[key] != outcome[key] for key in status_keys)
                or outcome["source_sha256"] != study["measured_source_sha256"]
                or set(contract["selected_models"]) != set(study["models"])):
            raise ValueError("Study outcome or identity changed")
        observed_hashes = None
        for key in study["models"]:
            result = matrix.read_json(directory / key / "result.json")
            if result != outcome["models"][key]:
                raise ValueError("Per-model and aggregate results disagree")
            if (result["compatibility_status"] != "PASS" or result["report_status"] != "PASS"
                    or result["training_runs"] != 9 or result["model_id"] != profiles[key]["model_id"]
                    or result["revision"] != profiles[key]["revision"]):
                raise ValueError("Registered study lacks completed training/report evidence")
            first = matrix.read_json(directory / key / "calibration-1.json")
            if result["condition_sha256"] != first["condition_sha256"]:
                raise ValueError("Model condition identity differs")
            hashes = first["subset_content_sha256"]
            if observed_hashes is not None and hashes != observed_hashes:
                raise ValueError("Matrix models did not use the same dataset subsets")
            observed_hashes = hashes
            covered.add(key)
        summaries.append({"id": study["id"], "models": len(study["models"]),
                          "training_runs": 9 * len(study["models"]),
                          "timing_status": outcome["timing_status"],
                          "measured_commit": commit,
                          "source_snapshot_available": study["source_snapshot_available"]})
    if covered != set(profiles):
        raise ValueError("A supported matrix profile has no registered real-model evidence")
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        summaries = verify()
    except (OSError, ValueError, KeyError, TypeError, matrix.MatrixError):
        print("Registered HF evidence: FAIL; artifacts or expectations do not agree.", file=sys.stderr)
        return 1
    for result in summaries:
        print(f"{result['id']}: {result['models']} models, {result['training_runs']} recorded runs; "
              f"timing={result['timing_status']}; measured commit={'recorded' if result['measured_commit'] else 'unavailable'}; "
              f"source snapshot={'recorded' if result['source_snapshot_available'] else 'unavailable'}")
    print("Evidence replay: PASS. This checks historical artifacts, not fresh training or release readiness.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
