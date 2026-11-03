import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/sync-logging-schema.py"
spec = importlib.util.spec_from_file_location("schema_sync", SCRIPT)
schema_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schema_sync)


class SchemaSyncTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / schema_sync.SOURCE
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b'{"type": "object"}\n')

    def test_generation_updates_every_package_and_is_idempotent(self):
        self.assertEqual(schema_sync.sync_schema(self.root), list(schema_sync.TARGETS))
        self.source.write_bytes(b'{"type": "object", "required": ["trace_id"]}\n')
        self.assertEqual(schema_sync.sync_schema(self.root), list(schema_sync.TARGETS))
        for target in schema_sync.TARGETS:
            self.assertEqual((self.root / target).read_bytes(), self.source.read_bytes())
        self.assertEqual(schema_sync.sync_schema(self.root), [])

    def test_check_detects_missing_and_edited_copies_without_writing(self):
        schema_sync.sync_schema(self.root)
        missing, edited = schema_sync.TARGETS[:2]
        (self.root / missing).unlink()
        (self.root / edited).write_bytes(b"{}")
        self.assertEqual(schema_sync.sync_schema(self.root, check=True), [missing, edited])
        self.assertFalse((self.root / missing).exists())
        self.assertEqual((self.root / edited).read_bytes(), b"{}")

    def test_invalid_source_does_not_overwrite_package_copies(self):
        schema_sync.sync_schema(self.root)
        before = self.source.read_bytes()
        self.source.write_bytes(b"invalid json")
        with self.assertRaises(json.JSONDecodeError):
            schema_sync.sync_schema(self.root)
        for target in schema_sync.TARGETS:
            self.assertEqual((self.root / target).read_bytes(), before)

    def test_cli_check_fails_until_copies_are_generated(self):
        script = self.root / "scripts" / SCRIPT.name
        script.parent.mkdir()
        shutil.copyfile(SCRIPT, script)
        for args, expected in [(["--check"], 1), ([], 0), (["--check"], 0)]:
            result = subprocess.run(
                [sys.executable, str(script), *args],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
