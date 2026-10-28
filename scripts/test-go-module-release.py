#!/usr/bin/env python3
"""Go publication safety: source identity, immutable tags and fail-closed probes."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location("release", Path(__file__).with_name("go-module-release.py"))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class GoReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.patch = patch.object(release, "ROOT", self.root)
        self.patch.start(); self.addCleanup(self.patch.stop)
        folder = self.root / release.MODULE_PATH
        folder.mkdir(parents=True)
        (folder / "go.mod").write_text("module " + release.PREFIX + release.MODULE_PATH + "\n\ngo 1.26.0\n")
        (folder / "package.go").write_text("package example\n")
        self.out = self.root / "out"

    def test_deterministic_archive_and_source_identity(self):
        a = release.archive("0.3.4")
        self.assertEqual(a, release.archive("0.3.4"))
        path = release.build("0.3.4", self.out)
        release.verify("0.3.4", path)
        (self.root / "go/observability/package.go").write_text("changed")
        with self.assertRaisesRegex(ValueError, "source_mismatch"):
            release.verify("0.3.4", path)

    def test_duplicate_archive_paths_rejected(self):
        path = release.build("0.3.4", self.out)
        with zipfile.ZipFile(path, "a") as z:
            z.writestr("unlisted-file", "bad")
        with self.assertRaisesRegex(ValueError, "inventory_mismatch"):
            release.verify("0.3.4", path)

    def test_local_replace_or_wrong_module_not_publishable(self):
        p = self.root / "go/observability/go.mod"
        for value in ["module bad\n", p.read_text()+"\nreplace x => ../x\n"]:
            p.write_text(value)
            with self.assertRaises(ValueError): release.archive("0.3.4")

    def test_bad_versions_rejected_before_paths(self):
        for value in ["../0.3.4", "00.3.4", "0.3.4-rc.1", "v0.3.4", "2.0.0"]:
            with self.assertRaises(ValueError): release.identity(value)

    def test_preflight_rejects_dirty_wrong_version_existing_or_newer(self):
        with patch.object(release, "git", return_value="dirty"):
            with self.assertRaisesRegex(ValueError,"uncommitted"): release.preflight("0.3.4")
        for suffix, error in [("0.3.4","tag_exists"),("0.3.5","newer_go_module")]:
            with patch.object(release,"git",side_effect=["","","a"*40+"\trefs/tags/go/observability/v"+suffix]):
                with self.assertRaisesRegex(ValueError,error): release.preflight("0.3.4")

    def test_missing_tag_is_not_auth_failure(self):
        with patch.object(release,"git",side_effect=["","",subprocess.CalledProcessError(1,["git"])]):
            with self.assertRaises(subprocess.CalledProcessError): release.preflight("0.3.4")

    def test_publish_only_atomic_create_of_verified_source(self):
        path=release.build("0.3.4",self.out)
        with patch.object(release,"preflight") as gate, patch.object(release,"git",return_value="c"*40), patch.object(release.subprocess,"run") as command:
            release.publish("0.3.4",path)
            gate.assert_called_once_with("0.3.4")
            args=command.call_args.args[0]
            self.assertIn("POST",args)
            self.assertIn("ref=refs/tags/go/observability/v0.3.4",args)
            self.assertIn("sha="+"c"*40,args)
            self.assertNotIn("--force",args)

    def test_go_tag_must_point_to_sdk_release_commit(self):
        path=release.build("0.3.4",self.out)
        with patch.object(release,"preflight"), patch.object(release,"git",side_effect=["a"*40,"b"*40]), patch.object(release.subprocess,"run") as command:
            with self.assertRaisesRegex(ValueError,"match_sdk_release"): release.publish("0.3.4",path)
            command.assert_not_called()

    def test_failed_gate_or_racing_create_never_retries_or_deletes(self):
        path=release.build("0.3.4",self.out)
        with patch.object(release,"preflight",side_effect=ValueError("occupied")), patch.object(release.subprocess,"run") as command:
            with self.assertRaises(ValueError): release.publish("0.3.4",path)
            command.assert_not_called()
        with patch.object(release,"preflight"), patch.object(release,"git",return_value="c"*40), patch.object(release.subprocess,"run",side_effect=subprocess.CalledProcessError(1,["gh"])) as command:
            with self.assertRaises(subprocess.CalledProcessError): release.publish("0.3.4",path)
            self.assertEqual(command.call_count,1)


if __name__ == "__main__": unittest.main()
