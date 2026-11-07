"""Local known-pattern scan of reachable Git blobs and current source files.

Never prints matching values. This is not proof that arbitrary credentials are absent.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/core/src"))
from traincost_ci_core.safety import looks_sensitive, safe_text


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def main():
    objects = set(line.split(b" ", 1)[0] for line in git("rev-list", "--objects", "--all").splitlines())
    failures = []
    scanned = 0
    for oid in sorted(objects):
        oid = oid.decode("ascii")
        if git("cat-file", "-t", oid).strip() != b"blob":
            continue
        scanned += 1
        if looks_sensitive(git("cat-file", "blob", oid).decode("utf-8", errors="replace")):
            failures.append("Git blob " + oid)
    files = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")
    for item in files:
        if not item:
            continue
        name = item.decode("utf-8")
        path = ROOT / name
        if path.is_file() and not path.is_symlink() and looks_sensitive(path.read_text(encoding="utf-8", errors="replace")):
            failures.append("Worktree file " + safe_text(name))
    for location in failures:
        print("Credential-shaped content detected in " + location)
    print(f"Scanned {scanned} reachable blobs and {len(files)-1} worktree entries; findings: {len(failures)}.")
    print("Known-pattern scan only; manually review confidential content before making the repository public.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
