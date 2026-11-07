"""Install a built wheel or sdist outside the repository in a fresh environment."""
import argparse
from pathlib import Path
import json
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("directory")
parser.add_argument("--sdist", action="store_true")
args = parser.parse_args()
pattern = "traincost_ci_core-*.tar.gz" if args.sdist else "traincost_ci_core-*.whl"
distribution, = Path(args.directory).resolve().glob(pattern)
with tempfile.TemporaryDirectory(prefix="traincost-wheel-") as temp:
    env = Path(temp) / "venv"
    subprocess.run([sys.executable, "-I", "-m", "venv", str(env)], check=True)
    python = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run([str(python), "-I", "-m", "pip", "--isolated", "install", "--disable-pip-version-check", str(distribution)], cwd=temp, check=True)
    subprocess.run([str(python), "-I", "-c", "from traincost_ci_core import __version__, analyze_config_dicts, parse_config_text; assert __version__ == '0.2.0b1'; c=parse_config_text('epochs: 2.9', 'yaml'); r=analyze_config_dicts(c,c); assert r.pr_config.epochs == 2.9; print('Installed distribution import and analysis outside repository: passed')"], cwd=temp, check=True)
    root = Path(temp)
    base = {"num_train_epochs": 1, "per_device_train_batch_size": 8, "gpu_count": 1,
            "gpu_type": "T4", "estimated_minutes_per_epoch": .06}
    (root / "base.json").write_text(json.dumps(base))
    (root / "head.json").write_text(json.dumps({**base, "num_train_epochs": 3}))
    cli = env / ("Scripts/traincost-ci.exe" if sys.platform == "win32" else "bin/traincost-ci")
    subprocess.run([str(cli), "--adapter", "huggingface", "--base-config", "base.json",
                    "--head-config", "head.json", "--gpu-prices", "T4=1"], cwd=temp, check=True)
    document = json.loads((root / "report.json").read_text())
    assert document["schema_version"] == "1.0" and document["analysis_status"] == "complete"
    assert document["summary"]["base_cost_usd"] == .001
    assert document["summary"]["pr_cost_usd"] == .003
    assert "$0.003" in (root / "report.md").read_text()
    print("Installed console CLI, HF adapter, subcent Markdown and JSON outside repository: passed")
    print("Verified distribution:", distribution.name)
