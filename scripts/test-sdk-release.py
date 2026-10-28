#!/usr/bin/env python3
"""Regression checks for the single SDK release gate and artifact versions."""

from email.message import EmailMessage
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "artifacts", Path(__file__).with_name("verify-sdk-artifacts.py")
)
artifacts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artifacts)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def wheels(self, version="0.4.0", dependency=None):
        for name in artifacts.EXPECTED["python"]:
            m = EmailMessage()
            m["Name"] = name.replace("_", "-")
            m["Version"] = version
            if dependency and name == "onenexus_observability_python":
                m["Requires-Dist"] = dependency
            with zipfile.ZipFile(
                self.root / f"{name}-0.4.0-py3-none-any.whl", "w"
            ) as z:
                z.writestr(f"{name}-0.4.0.dist-info/METADATA", m.as_bytes())
                if name == "onenexus_observability_python":
                    z.writestr("onenexus_observability/schema.json", "{}")

    def test_expected_version_and_no_separate_dependency(self):
        self.wheels()
        self.assertEqual(artifacts.verify("python", "0.4.0", self.root), 4)

    def test_wrong_metadata_version_is_rejected(self):
        self.wheels(version="0.3.3")
        with self.assertRaisesRegex(ValueError, "version_or_name"):
            artifacts.verify("python", "0.4.0", self.root)

    def test_contract_dependency_is_rejected(self):
        self.wheels(dependency="onenexus-log-contract==0.3.2")
        with self.assertRaisesRegex(ValueError, "contract_dependency"):
            artifacts.verify("python", "0.4.0", self.root)

    def test_missing_extra_or_old_artifacts_are_rejected(self):
        self.wheels()
        (self.root / "stale.whl").write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError, "inventory"):
            artifacts.verify("python", "0.4.0", self.root)

    def test_publication_requires_all_language_builds(self):
        release = (ROOT / ".github/workflows/sdk-release.yml").read_text()
        self.assertIn("needs: [prepare, build]", release)
        self.assertIn("uses: ./.github/workflows/sdk-build.yml", release)
        self.assertIn("overwrite_files: false", release)
        self.assertNotIn("skip-duplicate", release)
        self.assertNotIn("log-correlation-v", release)
        self.assertNotIn("REQUIRE_PUBLISHED_LOG_CONTRACT", release)
        build = (ROOT / ".github/workflows/sdk-build.yml").read_text()
        self.assertIn("language: [python, typescript, dotnet, go]", build)
        self.assertIn("bash scripts/build-sdk-artifacts.sh", build)
        self.assertNotIn("npm publish", build)
        self.assertNotIn("packages: write", build)
        check = (ROOT / ".github/workflows/sdk-checks.yml").read_text()
        self.assertIn("uses: ./.github/workflows/sdk-build.yml", check)

    def test_invalid_version_cannot_be_used_as_path(self):
        for version in ["../0.4.0", "v0.4.0", "01.0.0", "0.4.0-rc.1"]:
            with self.assertRaisesRegex(ValueError, "invalid_sdk_version"):
                artifacts.verify("go", version, self.root)


if __name__ == "__main__":
    unittest.main()
