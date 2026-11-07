import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "packages/core/src"
sys.path.insert(0, str(SRC))
from traincost_ci_core import analyze_config_dicts
from traincost_ci_core.serialization import analysis_to_dict, make_document


class JsonContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / "docs/schemas/report-v1.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(cls.schema)

    def test_complete_schema_exact_subcent_values(self):
        base = {"epochs": 1, "estimated_minutes_per_epoch": .06, "gpu_type": "T4", "gpu_count": 1}
        result = analyze_config_dicts(base, {**base, "epochs": 3}, gpu_hourly_prices={"T4": 1})
        document = make_document("complete", [{"path": "training.json", **analysis_to_dict(result)}])
        jsonschema.validate(document, self.schema)
        self.assertEqual(document["summary"]["base_cost_usd"], .001)
        self.assertEqual(document["summary"]["pr_cost_usd"], .003)

    def test_all_statuses_schema_and_exclusions(self):
        result = analyze_config_dicts({"epochs": 1}, {"epochs": 2})
        for status in ("complete", "partial", "skipped", "error"):
            entries = [{"path": "config.yaml", **analysis_to_dict(result)}] if status in {"complete", "partial"} else []
            document = make_document(status, entries, excluded_count=1, diagnostics=["Excluded invalid config."])
            jsonschema.validate(document, self.schema)
            self.assertEqual(document["summary"]["excluded_count"], 1)
            if not entries:
                self.assertIsNone(document["summary"]["pr_cost_usd"])

    def test_secret_and_raw_mapping_not_serialized(self):
        secret = "ghp_" + "A" * 30
        result = analyze_config_dicts({"epochs": 1, "password": secret}, {"epochs": 2, "model_name": secret})
        document = make_document("complete", [{"path": secret, **analysis_to_dict(result)}], diagnostics=[secret])
        encoded = json.dumps(document, allow_nan=False)
        self.assertNotIn(secret, encoded)
        self.assertNotIn("raw_fields", encoded)
        jsonschema.validate(document, self.schema)

    def run_cli(self, cwd, *args):
        # Insert the package path explicitly so cwd remains an unrelated directory.
        return subprocess.run([sys.executable, "-I", "-c",
            f"import sys; sys.path.insert(0, {str(SRC)!r}); from traincost_ci_core.cli import main; raise SystemExit(main())",
            *args], cwd=cwd, text=True, capture_output=True)

    def test_cli_complete_error_and_safe_argument_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "base.json").write_text('{"epochs":1}')
            (root / "head.json").write_text('{"epochs":3}')
            args = ("--base-config", "base.json", "--head-config", "head.json")
            run = self.run_cli(temp, *args)
            self.assertEqual(run.returncode, 0, run.stderr)
            document = json.loads((root / "report.json").read_text())
            jsonschema.validate(document, self.schema)
            self.assertEqual(document["analysis_status"], "complete")
            (root / "head.json").write_text('{"epochs":-1}')
            run = self.run_cli(temp, *args)
            self.assertEqual(run.returncode, 2)
            document = json.loads((root / "report.json").read_text())
            jsonschema.validate(document, self.schema)
            self.assertIsNone(document["summary"]["pr_cost_usd"])
            secret = "ghp_" + "B" * 30
            run = self.run_cli(temp, *args, "--unknown", secret)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn(secret, run.stdout + run.stderr + (root / "report.md").read_text() + (root / "report.json").read_text())

    def test_cli_output_collision_preserves_input(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.md"
            original = '{"epochs":1}'
            path.write_text(original)
            run = self.run_cli(temp, "--base-config", "report.md", "--head-config", "report.md")
            self.assertEqual(run.returncode, 2)
            self.assertEqual(path.read_text(), original)

    def test_invalid_cli_arguments_do_not_write_fallback_over_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = '{"epochs":1}'
            (root / "report.json").write_text(original)
            run = self.run_cli(temp, "--base-config", "report.json", "--head-config", "report.json", "--unsupported")
            self.assertEqual(run.returncode, 2)
            self.assertEqual((root / "report.json").read_text(), original)
            self.assertFalse((root / "report.md").exists())

    def test_hardlinked_output_does_not_overwrite_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = '{"epochs":1}'
            (root / "base.json").write_text(original)
            os.link(root / "base.json", root / "linked.json")
            run = self.run_cli(temp, "--base-config", "base.json", "--head-config", "base.json",
                               "--json-path", "linked.json")
            self.assertEqual(run.returncode, 2)
            self.assertEqual((root / "base.json").read_text(), original)


if __name__ == "__main__":
    unittest.main()
