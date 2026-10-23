"""Packaging failures must stop before a consumable artifact is published."""

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "package_builder", ROOT.parents[1] / "scripts/build-log-contract-package.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class PythonPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.source = self.work / "source"
        shutil.copytree(ROOT, self.source)
        self.manifest = json.loads((self.source / "manifest.json").read_text())
        self.version = self.manifest["version"]
        self.digest = self.manifest["sha256"]

    def test_bad_version_digest_and_source_do_not_stage(self):
        for version, digest in [("99.0.0", self.digest), (self.version, "0" * 64)]:
            with self.assertRaises(ValueError):
                builder.stage(self.source, self.work / "staged", version, digest)
            self.assertFalse((self.work / "staged").exists())
        (self.source / "schema.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "artifact_digest_mismatch"):
            builder.stage(self.source, self.work / "staged", self.version, self.digest)
        self.assertFalse((self.work / "staged").exists())

    def test_stage_uses_verified_snapshot_after_source_mutation(self):
        original = builder.gate.load_bundle
        schema = (self.source / "schema.json").read_bytes()

        def mutate(*args):
            verified = original(*args)
            (self.source / "schema.json").write_text("{}")
            (self.source / "manifest.json").write_text("{}")
            return verified

        with patch.object(builder.gate, "load_bundle", side_effect=mutate):
            builder.stage(self.source, self.work / "staged", self.version, self.digest)
        package = self.work / "staged/src/onenexus_log_contract"
        self.assertEqual((package / "schema.json").read_bytes(), schema)
        self.assertEqual(
            json.loads((package / "manifest.json").read_text()), self.manifest
        )
        builder.gate.load_bundle(self.version, package, self.digest)

    def test_failed_build_leaves_no_output(self):
        with patch.object(
            builder.subprocess, "run", side_effect=RuntimeError("build failed")
        ):
            with self.assertRaises(RuntimeError):
                builder.build(
                    self.source, self.work / "output", self.version, self.digest
                )
        self.assertFalse((self.work / "output").exists())

    def test_completed_wheel_is_never_overwritten(self):
        def fake_build(command, **kwargs):
            dist = Path(command[-1])
            dist.mkdir()
            (dist / "test.whl").write_bytes(b"test wheel")

        output = self.work / "output"
        with patch.object(builder.subprocess, "run", side_effect=fake_build):
            artifact = builder.build(self.source, output, self.version, self.digest)
            with self.assertRaises(FileExistsError):
                builder.build(self.source, output, self.version, self.digest)
        self.assertEqual(artifact.read_bytes(), b"test wheel")
