"""Audit both optional ML locks without installing GPU packages."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlparse

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]
LOCKS = {"macos": "macos-requirements.lock", "cuda": "requirements.lock"}


def audit_requirements(text):
    """Map exact, hashed lock entries to public advisory database versions."""
    pins = {}
    for line in text.replace("\\\n", " ").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tokens = shlex.split(line)
        if tokens == ["--index-url", "https://pypi.org/simple"]:
            continue
        hashes = [token for token in tokens if token.startswith("--hash=")]
        if not hashes or any(not re.fullmatch(r"--hash=sha256:[0-9a-f]{64}", item) for item in hashes):
            raise ValueError("Every lock entry must have SHA-256 hashes")
        requirement = Requirement(" ".join(token for token in tokens if token not in hashes))
        name = canonicalize_name(requirement.name)
        if name in pins or requirement.marker or requirement.extras:
            raise ValueError("Duplicate or conditional lock entry")
        if requirement.url:
            url = urlparse(requirement.url)
            wheel_name, version, _, tags = parse_wheel_filename(Path(unquote(url.path)).name)
            if (name != "torch" or canonicalize_name(wheel_name) != name
                    or url.scheme != "https" or url.netloc != "download.pytorch.org"
                    or not url.path.startswith("/whl/cu130/") or url.query
                    or not re.fullmatch(r"sha256=[0-9a-f]{64}", url.fragment)
                    or "--hash=" + url.fragment.replace("=", ":", 1) not in hashes
                    or version.local != "cu130"
                    or {str(tag) for tag in tags} != {"cp312-cp312-manylinux_2_28_x86_64"}):
                raise ValueError("Unexpected direct dependency URL")
            # CUDA wheels share the public torch advisory version. Their separately
            # pinned CUDA dependencies are also audited; this is not a wheel scan.
            public = version.public
        else:
            specs = list(requirement.specifier)
            if len(specs) != 1 or specs[0].operator != "==" or "*" in specs[0].version:
                raise ValueError("Exact versions are required")
            public = specs[0].version
        pins[name] = public
    if not pins:
        raise ValueError("Empty lock")
    return pins


def audit_complete(result, expected):
    dependencies = result.get("dependencies", [])
    observed = {}
    for item in dependencies:
        if "skip_reason" in item or not isinstance(item.get("vulns"), list):
            return False
        name = canonicalize_name(item["name"])
        if name in observed:
            return False
        observed[name] = item.get("version")
    return observed == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", choices=LOCKS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lock = ROOT / "examples/huggingface-demo" / LOCKS[args.lock]
    lock_bytes = lock.read_bytes()
    pins = audit_requirements(lock_bytes.decode("utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="traincost-advisories-") as directory:
        requirements = Path(directory) / "requirements.txt"
        report = Path(directory) / "audit.json"
        requirements.write_text("".join(f"{name}=={version}\n" for name, version in sorted(pins.items())))
        run = subprocess.run([sys.executable, "-m", "pip_audit", "-r", str(requirements),
                              "--no-deps", "--disable-pip", "--strict", "--progress-spinner", "off",
                              "--format", "json", "--output", str(report)], timeout=540)
        if not report.is_file():
            print("Dependency audit did not produce evidence", file=sys.stderr)
            return 2
        result = json.loads(report.read_text())
        result["traincost_audit"] = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "lock": lock.relative_to(ROOT).as_posix(),
            "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
            "pip_audit_version": importlib.metadata.version("pip-audit"),
            "advisory_service": "pypi", "ignored_vulnerabilities": [],
            "scope": "Exact public versions, including transitive packages; no installation or binary scan.",
        }
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if lock.read_bytes() != lock_bytes or not audit_complete(result, pins):
        print("Dependency audit did not cover the complete lock", file=sys.stderr)
        return 2
    count = sum(len(item["vulns"]) for item in result["dependencies"])
    print(f"{args.lock}: {len(pins)} packages, {count} advisory entries")
    return 0 if run.returncode == 0 and count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
