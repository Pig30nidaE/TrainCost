"""Run offline upgrade checks and record the exact code/fixture fingerprint."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    ("core", ["-m", "unittest", "discover", "packages/core/tests"]),
    ("action", ["-m", "unittest", "discover", "packages/github-action/tests"]),
    ("hf_demo", ["-m", "unittest", "discover", "examples/huggingface-demo/tests"]),
    ("hf_model_matrix", ["-m", "unittest", "discover", "examples/hf-model-matrix/tests"]),
    ("hf_matrix_profiles", ["scripts/verify_hf_matrix.py", "--list"]),
    ("hf_registered_evidence", ["scripts/verify_hf_evidence.py"]),
    ("corpus_evaluator", ["-m", "unittest", "discover", "examples/hf-config-corpus/tests"]),
    ("release_fixtures", ["scripts/verify_release.py"]),
    ("hosted_archives", ["docs/evidence/external-consumer-2026-11-08/verify.py"]),
    ("fixed_hosted_archives", ["docs/evidence/final-consumer-2026-11-08/verify.py"]),
    ("hosted_archive_regressions", ["-m", "unittest", "discover", "-s", "docs/evidence/external-consumer-2026-11-08", "-p", "test_verify.py"]),
    ("verification_fingerprint", ["-m", "unittest", "discover", "-s", "scripts/tests"]),
    ("hf_static_demo", ["scripts/verify_hf_demo.py"]),
    ("hf_corpus", ["scripts/verify_hf_corpus.py"]),
    ("independent_consumer", ["scripts/verify_external_consumer.py", "--direct-only"]),
    ("missing_yaml", ["-I", "-S", "scripts/verify_no_yaml.py"]),
)


def fingerprint():
    output = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT)
    files = {}
    for raw in sorted(set(output.split(b"\0")) - {b""}):
        relative = raw.decode("utf-8")
        path = ROOT / relative
        if not path.is_file():
            continue
        if not relative.startswith("docs/evidence/") and path.suffix not in {".py", ".json", ".yaml", ".yml", ".toml", ".txt", ".lock"}:
            continue
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest(), files


def validate_destination(value):
    path = Path(value).absolute()
    if path.exists() or path.is_symlink():
        raise ValueError("Verification output must be a new file.")
    # Keep generated records outside the checkout instead of excluding inputs.
    # samefile also catches case aliases on case-insensitive filesystems.
    if any(parent.exists() and parent.samefile(ROOT) for parent in path.parents):
        raise ValueError("Verification output must be outside the source checkout.")
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT.resolve()):
        raise ValueError("Verification output must be outside the source checkout.")
    return resolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--output", required=True, help="New JSON file outside the source checkout; existing files are never replaced.")
    args = parser.parse_args()
    try:
        destination = validate_destination(args.output)
    except (ValueError, OSError, RuntimeError) as error:
        parser.error(str(error))
    started_hash, files = fingerprint()
    version = subprocess.check_output([args.python, "-I", "-c", "import platform; print(platform.python_version())"], text=True).strip()
    records = []
    for name, command in CHECKS:
        try:
            run = subprocess.run([args.python, *command], cwd=ROOT, capture_output=True, text=True, timeout=300)
            record = {"name": name, "command": ["python", *command], "exit_code": run.returncode}
            tests = re.search(r"Ran (\d+) tests? in", run.stderr)
            skipped = re.search(r"skipped=(\d+)", run.stderr)
            if tests:
                record.update(tests_run=int(tests[1]), skipped=int(skipped[1]) if skipped else 0)
            if name == "hf_corpus":
                count = re.search(r"HF corpus: (\d+)/(\d+) labeled cases passed", run.stdout)
                if count:
                    record.update(cases_passed=int(count[1]), cases_total=int(count[2]))
        except subprocess.TimeoutExpired:
            record = {"name": name, "command": ["python", *command], "exit_code": None, "timeout_seconds": 300}
        records.append(record)
        # Logs may include untrusted config values on failure. Save only structured outcomes.
        print(f"{version} {name}: {'PASS' if record['exit_code'] == 0 else 'FAIL'}", flush=True)
    ended_hash, _ = fingerprint()
    success = started_hash == ended_hash and all(item["exit_code"] == 0 for item in records)
    result = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree_included": True, "python_version": version,
        "os": platform.system(), "os_release": platform.release(), "architecture": platform.machine(),
        "code_fixture_sha256": started_hash, "files_sha256": files,
        "source_unchanged_during_checks": started_hash == ended_hash,
        "checks": records, "passed": success,
        "scope": "Local offline checks; no hosted PR permissions, model training, or release validation.",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("Source unchanged:", started_hash == ended_hash)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
