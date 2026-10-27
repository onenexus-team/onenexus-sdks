#!/usr/bin/env python3
"""Release guards: no publication with missing, stale, conflicting or corrupt inputs."""

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location("release", Path(__file__).with_name("log-contract-release.py"))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / "artifacts"
        self.out.mkdir()
        canonical = self.root / "contracts/log-correlation"
        canonical.mkdir(parents=True)
        (canonical / "manifest.json").write_text(json.dumps({"version": "1.2.3", "sha256": "d" * 64}))
        self.version = "1.2.3"
        for method in ("verify", "preflight", "publish"):
            mock = patch.object(release.go_modules, method)
            mock.start()
            self.addCleanup(mock.stop)
        self.patch = patch.object(release, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        names = release.names(self.version)
        (self.out / names[0]).write_bytes(b"archive")
        (self.out / names[1]).write_bytes(b"wheel")
        self.npm_name = names[2]
        self.nuget_name = names[3]
        (self.out / names[4]).write_bytes(b"go module archive")
        self.write_npm()
        with zipfile.ZipFile(self.out / self.nuget_name, "w") as package:
            package.writestr("OneNexus.LogContract.nuspec", '<package><metadata><id>OneNexus.LogContract</id><version>1.2.3</version></metadata></package>')
        self.checksums()

    def write_npm(self, name="@onenexus-team/log-contract", version="1.2.3"):
        with tarfile.open(self.out / self.npm_name, "w:gz") as package:
            data = json.dumps({"name": name, "version": version}).encode()
            info = tarfile.TarInfo("package/package.json")
            info.size = len(data)
            package.addfile(info, io.BytesIO(data))

    def checksums(self):
        artifacts = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.out.iterdir()
                     if p.name not in {"release-manifest.json", "SHA256SUMS"}}
        metadata = {"version": self.version, "contract_sha256": "d" * 64,
                    "source_commit": "c" * 40, "artifacts": artifacts}
        (self.out / "release-manifest.json").write_text(json.dumps(metadata))
        (self.out / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(artifacts.items())))

    def verify(self):
        with patch.object(release, "run", return_value=subprocess.CompletedProcess([], 0, "c" * 40)):
            return release.verify(self.out, self.version)

    def test_complete_artifact_set(self):
        self.assertEqual(len(self.verify()["artifacts"]), 5)

    def test_missing_language_blocks_release(self):
        (self.out / self.nuget_name).unlink()
        self.checksums()
        with self.assertRaisesRegex(ValueError, "incomplete_language_artifacts"):
            self.verify()

    def test_missing_go_module_blocks_release(self):
        (self.out / release.names(self.version)[4]).unlink()
        self.checksums()
        with self.assertRaisesRegex(ValueError, "incomplete_language_artifacts"):
            self.verify()

    def test_go_failure_after_registry_writes_is_not_ignored(self):
        with patch.dict(os.environ, {"NUGET_AUTH_TOKEN": "unit-test-placeholder"}):
            with patch.object(release, "verify"), patch.object(release, "ensure_available"), patch.object(release, "run") as command:
                with patch.object(release.go_modules, "publish", side_effect=ValueError("tag_race")):
                    with self.assertRaisesRegex(ValueError, "tag_race"):
                        release.publish(self.out, self.version)
                    self.assertEqual(command.call_count, 2)

    def test_changed_bytes_block_release(self):
        (self.out / self.npm_name).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "artifact_hash_mismatch"):
            self.verify()

    def test_unlisted_asset_cannot_be_uploaded_with_contract_release(self):
        (self.out / "unrelated-sdk.tgz").write_bytes(b"unrelated")
        with self.assertRaisesRegex(ValueError, "unexpected_release_files"):
            self.verify()

    def test_wrong_npm_identity_blocked_even_with_matching_checksums(self):
        self.write_npm(name="@onenexus-team/observability")
        self.checksums()
        with self.assertRaisesRegex(ValueError, "npm_identity_mismatch"):
            self.verify()

    def test_wrong_nuget_identity_blocked(self):
        with zipfile.ZipFile(self.out / self.nuget_name, "w") as package:
            package.writestr("OneNexus.LogContract.nuspec", '<package><id>OneNexus.Observability</id><version>1.2.3</version></package>')
        self.checksums()
        with self.assertRaisesRegex(ValueError, "nuget_identity_mismatch"):
            self.verify()

    def test_stale_source_blocked(self):
        with patch.object(release, "run", return_value=subprocess.CompletedProcess([], 0, "a" * 40)):
            with self.assertRaisesRegex(ValueError, "release_source_mismatch"):
                release.verify(self.out, self.version)

    def test_version_and_digest_mismatch_blocked(self):
        path = self.out / "release-manifest.json"
        original = json.loads(path.read_text())
        for key, value, error in [("version", "1.2.4", "contract_version_mismatch"),
                                  ("contract_sha256", "e" * 64, "contract_digest_mismatch")]:
            path.write_text(json.dumps({**original, key: value}))
            with self.assertRaisesRegex(ValueError, error):
                self.verify()

    def test_unsafe_or_noncanonical_versions_rejected(self):
        for value in ["../1.2.3", "01.2.3", "1.2.3;echo", "1.2.3-rc.1", "v1.2.3"]:
            with self.assertRaises(ValueError):
                release.names(value)

    def preflight(self, npm, nuget):
        with patch.object(release.subprocess, "run", return_value=npm):
            with patch.object(release, "run", side_effect=nuget):
                release.ensure_available(self.version)

    def test_available_version(self):
        self.preflight(subprocess.CompletedProcess([], 0, '["1.2.2"]'),
                       [subprocess.CompletedProcess([], 0, '[{"name":"1.2.2"}]')])

    def test_existing_npm_or_nuget_version_blocked(self):
        for npm, nuget, error in [('["1.2.3"]', '[]', "npm_version_already_exists"),
                                   ('[]', '[{"name":"1.2.3"}]', "nuget_version_already_exists")]:
            with self.assertRaisesRegex(ValueError, error):
                self.preflight(subprocess.CompletedProcess([], 0, npm), [subprocess.CompletedProcess([], 0, nuget)])

    def test_older_release_cannot_move_latest_backwards(self):
        for npm, nuget in [('["1.2.4"]', '[]'), ('[]', '[{"name":"1.3.0"}]')]:
            with self.assertRaisesRegex(ValueError, "newer_version_exists"):
                self.preflight(subprocess.CompletedProcess([], 0, npm), [subprocess.CompletedProcess([], 0, nuget)])

    def test_auth_failure_is_not_treated_as_missing_package(self):
        with self.assertRaisesRegex(ValueError, "npm_preflight_failed"):
            self.preflight(subprocess.CompletedProcess([], 1, '{"error":{"code":"E401"}}'), [])
        with self.assertRaises(subprocess.CalledProcessError):
            self.preflight(subprocess.CompletedProcess([], 0, '[]'), [subprocess.CalledProcessError(1, ["gh"])])

    def test_registry_scan_is_bounded(self):
        rows = json.dumps([{"name": "1.0.0"}] * 100)
        with self.assertRaisesRegex(ValueError, "scan_limit"):
            self.preflight(subprocess.CompletedProcess([], 0, '[]'), [subprocess.CompletedProcess([], 0, rows)] * 10)

    def test_no_write_until_all_preconditions_pass(self):
        with patch.dict(os.environ, {"NUGET_AUTH_TOKEN": "unit-test-placeholder"}):
            with patch.object(release, "verify"), patch.object(release, "ensure_available", side_effect=ValueError("collision")), patch.object(release, "run") as command:
                with self.assertRaises(ValueError):
                    release.publish(self.out, self.version)
                command.assert_not_called()

    def test_first_publish_failure_stops_later_writes(self):
        with patch.dict(os.environ, {"NUGET_AUTH_TOKEN": "unit-test-placeholder"}):
            with patch.object(release, "verify"), patch.object(release, "ensure_available"), patch.object(release, "run", side_effect=subprocess.CalledProcessError(1, ["npm"])) as command:
                with self.assertRaises(subprocess.CalledProcessError):
                    release.publish(self.out, self.version)
                self.assertEqual(command.call_count, 1)

    def test_partial_publish_fails_without_overwrite_or_delete(self):
        with patch.dict(os.environ, {"NUGET_AUTH_TOKEN": "unit-test-placeholder"}):
            with patch.object(release, "verify"), patch.object(release, "ensure_available"), patch.object(release, "run", side_effect=[None, subprocess.CalledProcessError(1, ["dotnet"])]) as command:
                with self.assertRaises(subprocess.CalledProcessError):
                    release.publish(self.out, self.version)
                self.assertEqual(command.call_count, 2)
                self.assertEqual(command.call_args_list[0].args[0][:2], ["npm", "publish"])
                self.assertEqual(command.call_args_list[1].args[0][:3], ["dotnet", "nuget", "push"])

    def test_failed_build_restores_package_sources(self):
        package = self.root / "ts/packages/log-contract/package.json"
        package.parent.mkdir(parents=True)
        original = '{"version":"0.3.3"}'
        package.write_text(original)
        lockfile = self.root / "ts/pnpm-lock.yaml"
        lockfile.write_text("original lockfile")
        def fail_after_validation(args, **kwargs):
            if args[2] == "build":
                package.write_text('{"version":"1.2.3"}')
                lockfile.write_text("temporary release lockfile")
                raise subprocess.CalledProcessError(1, args)
        with patch.object(release, "run", side_effect=fail_after_validation):
            with self.assertRaises(subprocess.CalledProcessError):
                release.build(self.root / "failed-output", self.version)
        self.assertEqual(package.read_text(), original)
        self.assertEqual(lockfile.read_text(), "original lockfile")

    def version_sync_project(self, contract_version="0.3.3"):
        scripts = self.root / "scripts"
        scripts.mkdir()
        source = Path(__file__).with_name("sync-ts-package-versions.mjs")
        (scripts / source.name).write_bytes(source.read_bytes())
        (self.root / "VERSION").write_text("9.8.7\n")
        for name in ["log-contract", "observability", "sdk-core", "cas-client", "cas-support-client"]:
            folder = self.root / "ts/packages" / name
            folder.mkdir(parents=True)
            (folder / "package.json").write_text(json.dumps({"name": name, "version": contract_version, "dependencies": {"@onenexus-team/log-contract": "workspace:" + contract_version}}))
        return scripts / source.name

    def test_sdk_version_does_not_change_contract_pin(self):
        script = self.version_sync_project()
        env = {k: v for k, v in os.environ.items() if k not in {"SDK_PACKAGE_VERSION", "LOG_CONTRACT_PACKAGE_VERSION"}}
        subprocess.run(["node", str(script)], check=True, capture_output=True, env=env)
        contract = json.loads((self.root / "ts/packages/log-contract/package.json").read_text())
        logging = json.loads((self.root / "ts/packages/observability/package.json").read_text())
        self.assertEqual(contract["version"], "0.3.3")
        self.assertEqual(logging["version"], "9.8.7")
        self.assertEqual(logging["dependencies"]["@onenexus-team/log-contract"], "workspace:0.3.3")


    def test_contract_override_changes_only_local_lockfile_link(self):
        source_root = Path(__file__).resolve().parents[1]
        pin = json.loads((source_root / "ts/packages/log-contract/package.json").read_text())["version"]
        script = self.version_sync_project(pin)
        lockfile = self.root / "ts/pnpm-lock.yaml"
        # Real checked-in lockfile: all external resolution/integrity data must survive byte-for-byte.
        original = (source_root / "ts/pnpm-lock.yaml").read_text()
        lockfile.write_text(original)
        subprocess.run(["node", str(script)], check=True, capture_output=True,
                       env={**os.environ, "LOG_CONTRACT_PACKAGE_VERSION": "1.2.3"})
        expected = original.replace("specifier: workspace:" + pin, "specifier: workspace:1.2.3")
        self.assertNotEqual(expected, original)
        self.assertEqual(lockfile.read_text(), expected)
        logging = json.loads((self.root / "ts/packages/observability/package.json").read_text())
        self.assertEqual(logging["dependencies"]["@onenexus-team/log-contract"], "workspace:1.2.3")
        contract = json.loads((self.root / "ts/packages/log-contract/package.json").read_text())
        self.assertEqual(contract["version"], "1.2.3")

    def test_unknown_workspace_lockfile_layout_fails_closed(self):
        script = self.version_sync_project()
        lockfile = self.root / "ts/pnpm-lock.yaml"
        lockfile.write_text("unknown layout")
        result = subprocess.run(["node", str(script)], capture_output=True,
                                env={**os.environ, "LOG_CONTRACT_PACKAGE_VERSION": "1.2.3"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(lockfile.read_text(), "unknown layout")
        contract = json.loads((self.root / "ts/packages/log-contract/package.json").read_text())
        self.assertEqual(contract["version"], "0.3.3")


if __name__ == "__main__":
    unittest.main()
