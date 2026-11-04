"""Run with python -I -S to prove missing dependencies fail explicitly."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/core/src"))
from traincost_ci_core import parse_config_text

try:
    parse_config_text("epochs: 5", "yaml")
except ValueError as exc:
    assert "requires PyYAML==6.0.3" in str(exc)
    print("Missing PyYAML produces an explicit diagnostic: passed")
else:
    raise AssertionError("Expected dependency error")
