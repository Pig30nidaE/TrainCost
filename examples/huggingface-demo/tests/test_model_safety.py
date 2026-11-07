import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO))
from model_safety import DISTILBERT_METADATA, read_metadata, validate_local_model


class ModelMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = self.root / "config.json"
        self.tokenizer = self.root / "tokenizer_config.json"
        self.config.write_text('{"model_type":"bert"}')
        self.tokenizer.write_text('{"model_max_length":512}')

    def validate(self, directory, architecture):
        hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in (self.config, self.tokenizer)}
        validate_local_model(directory, architecture, hashes=hashes)

    def test_plain_reviewed_metadata_passes(self):
        for architecture in ("bert", "distilbert", "albert"):
            self.config.write_text(json.dumps({"model_type": architecture}))
            self.validate(self.root, architecture)

    def test_nested_remote_code_and_kernel_fields_are_rejected(self):
        for key in ("auto_map", "custom_pipelines", "trust_remote_code", "custom_generate",
                    "_attn_implementation_internal", "_attn_implementation", "attn_implementation"):
            self.config.write_text(json.dumps({"model_type": "bert", "nested": [{key: "synthetic-secret"}]}))
            with self.subTest(key=key), self.assertRaises(ValueError) as raised:
                self.validate(self.root, "bert")
            self.assertNotIn("synthetic-secret", str(raised.exception))

    def test_tokenizer_external_paths_and_templates_are_rejected(self):
        for key in ("tokenizer_file", "fast_tokenizer_files", "vocab_file", "chat_template", "processor_class"):
            self.tokenizer.write_text(json.dumps({key: "../synthetic"}))
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(self.root, "bert")

    def test_malformed_duplicate_and_nonfinite_metadata_are_value_free(self):
        for text in ('{"private-value":', '{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', '[]'):
            self.config.write_text(text)
            with self.assertRaises(ValueError) as raised:
                self.validate(self.root, "bert")
            self.assertNotIn("private-value", str(raised.exception))

    def test_bounds_and_architecture_mismatch_fail(self):
        with self.assertRaises(ValueError):
            self.validate(self.root, "albert")
        for text in ('{"x":"' + 'a' * 100_000 + '"}', '{"x":' + '[' * 40 + '0' + ']' * 40 + '}'):
            self.config.write_text(text)
            with self.assertRaises(ValueError):
                read_metadata(self.config)

    def test_symlinked_metadata_or_model_directory_fails(self):
        self.config.unlink()
        self.config.symlink_to(self.tokenizer)
        with self.assertRaises(ValueError):
            self.validate(self.root, "bert")
        link = self.root / "linked"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.validate(link, "bert")

    def test_actual_upstream_metadata_matches_reviewed_profiles(self):
        profiles = json.loads((DEMO.parent / "hf-model-matrix/profiles.json").read_text())["models"]
        for profile in profiles:
            directory = DEMO / "tests/fixtures/model-metadata" / profile["key"]
            with self.subTest(model=profile["key"]):
                validate_local_model(directory, profile["model_type"], hashes=profile["metadata_sha256"])
                if profile["key"] == "distilbert":
                    self.assertEqual(profile["metadata_sha256"], DISTILBERT_METADATA)

    def test_model_dimension_changes_cannot_reuse_reviewed_hash(self):
        directory = DEMO / "tests/fixtures/model-metadata/distilbert"
        self.config.write_bytes((directory / "config.json").read_bytes())
        self.tokenizer.write_bytes((directory / "tokenizer_config.json").read_bytes())
        value = json.loads(self.config.read_text())
        value["vocab_size"] = 10**100
        self.config.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "differs from reviewed"):
            validate_local_model(self.root, "distilbert", hashes=DISTILBERT_METADATA)


if __name__ == "__main__":
    unittest.main()
