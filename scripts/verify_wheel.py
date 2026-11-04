"""Install the built wheel into a fresh environment outside the repository."""
from pathlib import Path
import subprocess
import sys
import tempfile

wheel, = Path(sys.argv[1]).resolve().glob("traincost_ci_core-*.whl")
with tempfile.TemporaryDirectory(prefix="traincost-wheel-") as temp:
    env = Path(temp) / "venv"
    subprocess.run([sys.executable, "-I", "-m", "venv", str(env)], check=True)
    python = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run([str(python), "-I", "-m", "pip", "--isolated", "install", "--disable-pip-version-check", str(wheel)], cwd=temp, check=True)
    subprocess.run([str(python), "-I", "-c", "from traincost_ci_core import __version__, analyze_config_dicts, parse_config_text; assert __version__ == '0.2.0b1'; c=parse_config_text('epochs: 2.9', 'yaml'); r=analyze_config_dicts(c,c); assert r.pr_config.epochs == 2.9; print('Installed wheel import and analysis outside repository: passed')"], cwd=temp, check=True)
