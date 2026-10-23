"""Test the shared gate, not a production language implementation."""

import concurrent.futures
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "contract_gate", ROOT / "check_contract.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
VERSION = "0.3.1"
DIGEST = "9be133120a0fc9baf286110131f70c9dc193ed14957f9461d431ca159b798538"


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="contract-test-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.root = self.work / "contracts/log-correlation"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__"))
        self.manifest, self.vectors, _ = gate.load_bundle(VERSION, self.root, DIGEST)
        self.result = {
            "adapter_protocol": 1,
            "contract_version": VERSION,
            "contract_sha256": DIGEST,
            "results": [],
        }
        # Synthetic observations test the checker. Package evidence is separate.
        for case in self.vectors["record_cases"]:
            self.result["results"].append(
                {"kind": "record", "id": case["id"], "errors": case["errors"]}
            )
        for index, case in enumerate(self.vectors["context_cases"]):
            trace_id = (
                case["traceparent"].split("-")[1]
                if case["preserve_trace"]
                else f"{index + 1:032x}"
            )
            self.result["results"].append(
                {
                    "kind": "context",
                    "id": case["id"],
                    "trace_id": trace_id,
                    "outgoing_traceparent": f"00-{trace_id}-2222222222222222-00",
                    "after_trace_id": None,
                }
            )
        self.path = self.work / "results.json"

    def check(self, value=None):
        self.path.write_text(json.dumps(self.result if value is None else value))
        return gate.check_results(VERSION, DIGEST, self.path, self.root)

    def test_current_artifact_identity_and_complete_result_set(self):
        self.assertEqual(self.manifest["record_cases"], 56)
        self.assertEqual(self.manifest["context_cases"], 10)
        self.assertEqual(self.check(), 66)

    def test_environment_is_required_in_each_current_profile(self):
        manifest, vectors, snapshots = gate.load_bundle(
            "0.3.1",
            self.root,
            "9be133120a0fc9baf286110131f70c9dc193ed14957f9461d431ca159b798538",
        )
        schema = json.loads(snapshots[gate.ARTIFACTS[0]])
        for name, profile in schema["$defs"].items():
            self.assertIn("environment", profile["required"])
            self.assertEqual(
                profile["properties"]["environment"],
                {
                    "type": "string",
                    "enum": ["development", "staging", "prod"],
                    "title": "Environment",
                },
            )
            cases = [
                case
                for case in vectors["record_cases"]
                if case["id"].startswith("environment_" + name + "_")
            ]
            self.assertEqual(len(cases), 9)
            self.assertEqual(sum(case["errors"] == [] for case in cases), 3)
            self.assertEqual(
                sum(case["errors"] == ["schema_invalid"] for case in cases), 6
            )
        self.assertEqual(manifest["record_cases"], 56)

    def test_current_results_reject_accepting_invalid_environment(self):
        manifest, vectors, _ = gate.load_bundle("0.3.1", self.root)
        result = copy.deepcopy(self.result)
        result["contract_version"] = manifest["version"]
        result["contract_sha256"] = manifest["sha256"]
        result["results"] = [
            {"kind": "record", "id": case["id"], "errors": case["errors"]}
            for case in vectors["record_cases"]
        ] + result["results"][len(self.vectors["record_cases"]) :]
        self.path.write_text(json.dumps(result))
        self.assertEqual(
            gate.check_results(
                manifest["version"], manifest["sha256"], self.path, self.root
            ),
            66,
        )
        for item in result["results"]:
            if item["id"].startswith("environment_") and item.get("errors"):
                with self.subTest(case=item["id"]):
                    item["errors"] = []
                    self.path.write_text(json.dumps(result))
                    with self.assertRaisesRegex(
                        gate.ContractError, "record_result_mismatch"
                    ):
                        gate.check_results(
                            manifest["version"],
                            manifest["sha256"],
                            self.path,
                            self.root,
                        )
                    item["errors"] = ["schema_invalid"]

    def test_current_contract_is_packaged_and_explicitly_selected(self):
        manifest, _, _ = gate.load_bundle("0.3.1", self.root)
        output = self.work / "current.tgz"
        gate.build_archive(manifest["version"], manifest["sha256"], output, self.root)
        with tarfile.open(output) as archive:
            schema = json.load(archive.extractfile("schema.json"))
            self.assertIn("environment", schema["$defs"]["common"]["required"])
        result = subprocess.run(
            [
                sys.executable,
                str(self.root / "check_contract.py"),
                "verify",
                "--version",
                VERSION,
                "--expected-digest",
                manifest["sha256"],
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["contract_version"], "0.3.1")

    def test_wrong_trusted_pin_or_version_rejected(self):
        with self.assertRaises(gate.ContractError):
            gate.load_bundle(VERSION, self.root, "0" * 64)
        for value in ("../0.3.1", "", "/tmp", "latest"):
            with self.subTest(version=value), self.assertRaises(gate.ContractError):
                gate.load_bundle(value, self.root)

    def test_tampered_artifact_rejected(self):
        for name in gate.ARTIFACTS:
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                with self.assertRaisesRegex(
                    gate.ContractError, "artifact_digest_mismatch"
                ):
                    gate.load_bundle(VERSION, self.root, DIGEST)
                path.write_bytes(original)

    def test_missing_duplicate_unknown_or_skipped_cases_fail(self):
        for mode in ("missing", "duplicate", "unknown", "skip"):
            result = copy.deepcopy(self.result)
            if mode == "missing":
                result["results"].pop()
            elif mode == "duplicate":
                result["results"][1] = result["results"][0]
            elif mode == "unknown":
                result["results"][0]["id"] = "unknown"
            else:
                result["results"][0]["errors"] = ["skipped"]
            with self.subTest(mode=mode), self.assertRaises(gate.ContractError):
                self.check(result)

    def test_positive_and_negative_record_observations_must_match(self):
        for index in (0, 4):
            result = copy.deepcopy(self.result)
            result["results"][index]["errors"] = (
                ["schema_invalid"] if index == 0 else []
            )
            with (
                self.subTest(index=index),
                self.assertRaisesRegex(gate.ContractError, "record_result_mismatch"),
            ):
                self.check(result)

    def test_context_errors_are_detected(self):
        for mode in (
            "zero",
            "public_preserved",
            "trusted_changed",
            "reused",
            "bad_parent",
            "not_cleared",
        ):
            result = copy.deepcopy(self.result)
            contexts = result["results"][len(self.vectors["record_cases"]) :]
            if mode == "zero":
                contexts[0]["trace_id"] = "0" * 32
            elif mode == "public_preserved":
                contexts[3]["trace_id"] = "1" * 32
            elif mode == "trusted_changed":
                contexts[8]["trace_id"] = "a" * 32
            elif mode == "reused":
                contexts[1]["trace_id"] = contexts[0]["trace_id"]
            elif mode == "bad_parent":
                contexts[0]["outgoing_traceparent"] = "invalid"
            else:
                contexts[0]["after_trace_id"] = "a" * 32
            with self.subTest(mode=mode), self.assertRaises(gate.ContractError):
                self.check(result)

    def test_result_identity_must_match(self):
        for field, value in [
            ("contract_version", "1.0.0"),
            ("contract_sha256", "0" * 64),
            ("adapter_protocol", 2),
        ]:
            result = copy.deepcopy(self.result)
            result[field] = value
            with self.subTest(field=field), self.assertRaises(gate.ContractError):
                self.check(result)

    def test_json_limits_and_duplicate_keys(self):
        for value in (
            b'{"a": 1, "a": 2}',
            b'{"a": NaN}',
            b'{"a": Infinity}',
            b'{"a": 1e400}',
        ):
            with self.subTest(value=value), self.assertRaises(gate.ContractError):
                gate.parse_json(value)
        self.path.write_bytes(b"x" * (gate.MAX_BYTES + 1))
        with self.assertRaises(gate.ContractError):
            gate.read_bytes(self.path)

    def test_symlink_artifacts_are_rejected(self):
        path = self.root / gate.ARTIFACTS[0]
        data = path.read_bytes()
        path.unlink()
        outside = self.work / "outside.json"
        outside.write_bytes(data)
        path.symlink_to(outside)
        with self.assertRaises(gate.ContractError):
            gate.load_bundle(VERSION, self.root, DIGEST)

    def test_archive_reproducible_and_not_overwritten(self):
        paths = [self.work / "first.tgz", self.work / "second.tgz"]
        hashes = [
            gate.build_archive(VERSION, DIGEST, path, self.root) for path in paths
        ]
        self.assertEqual(hashes[0], hashes[1])
        self.assertEqual(paths[0].read_bytes()[9], 255)  # OS-independent gzip header
        self.assertEqual(hashes[0], hashlib.sha256(paths[0].read_bytes()).hexdigest())
        with self.assertRaises(FileExistsError):
            gate.build_archive(VERSION, DIGEST, paths[0], self.root)
        extracted = self.work / "extracted"
        with tarfile.open(paths[0]) as archive:
            for member in archive.getmembers():
                self.assertFalse(
                    member.name.startswith("/") or ".." in Path(member.name).parts
                )
                target = extracted / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
        self.assertTrue((extracted / "design-and-validation.md").is_file())
        result = subprocess.run(
            [
                sys.executable,
                str(extracted / "check_contract.py"),
                "verify",
                "--version",
                VERSION,
                "--expected-digest",
                DIGEST,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["gate"], "PASS")

    def test_concurrent_archive_creation_has_one_winner(self):
        output = self.work / "shared.tgz"
        barrier = threading.Barrier(2, timeout=5)

        def build():
            barrier.wait()
            try:
                return gate.build_archive(VERSION, DIGEST, output, self.root)
            except FileExistsError:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: build(), range(2)))
        winners = [result for result in results if result is not None]
        self.assertEqual(winners, [hashlib.sha256(output.read_bytes()).hexdigest()])

    def test_r28_build_uses_verified_bytes_when_source_changes(self):
        original = gate.load_bundle
        expected = (self.root / gate.ARTIFACTS[1]).read_bytes()

        def change_after_read(*args):
            result = original(*args)
            (self.root / gate.ARTIFACTS[1]).write_bytes(b"{}")
            return result

        output = self.work / "snapshot.tgz"
        with patch.object(gate, "load_bundle", side_effect=change_after_read):
            gate.build_archive(VERSION, DIGEST, output, self.root)
        with tarfile.open(output) as archive:
            self.assertEqual(
                archive.extractfile(gate.ARTIFACTS[1]).read(),
                expected,
            )

    def test_cli_requires_pin_and_redacts_bad_results(self):
        self.path.write_text('{"private-data-marker": "must-not-echo"}')
        for extra in ([], ["--expected-digest", DIGEST]):
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.root / "check_contract.py"),
                    "check-results",
                    "--version",
                    VERSION,
                    "--results",
                    str(self.path),
                    *extra,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("must-not-echo", result.stdout + result.stderr)
            self.assertNotIn("private-data-marker", result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["gate"], "FAIL")

    def test_release_workflow_rejects_wrong_tag_and_off_main_commit(self):
        # Execute the actual workflow shell, with real local Git ancestry.
        workflow = (
            ROOT.parents[1] / ".github/workflows/log-contract-release.yml"
        ).read_text()
        step = workflow.split("      - name: Require a version tag on main\n", 1)[1]
        shell = textwrap.dedent(
            step.split("        run: |\n", 1)[1].split("      - name:", 1)[0]
        )

        def git(*args):
            return (
                subprocess.check_output(
                    ["git", *args], cwd=self.work, stderr=subprocess.STDOUT, timeout=10
                )
                .decode()
                .strip()
            )

        git("init", "-q")
        git("config", "user.name", "Contract test")
        git("config", "user.email", "test@example.invalid")
        git("add", "contracts")
        git("commit", "-qm", "reviewed contract")
        git("update-ref", "refs/remotes/origin/main", "HEAD")
        output = self.work / "github-output"

        def run(tag):
            output.write_text("")
            result = subprocess.run(
                ["bash", "-c", shell],
                cwd=self.work,
                env={**os.environ, "TAG": tag, "GITHUB_OUTPUT": str(output)},
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return result.returncode, output.read_text()

        self.assertEqual(run("log-correlation-v0.3.1"), (0, "version=0.3.1\n"))
        for tag in ("log-correlation-v0.3.2", "v0.3.1", "log-correlation-vlatest"):
            with self.subTest(tag=tag):
                code, emitted = run(tag)
                self.assertNotEqual(code, 0)
                self.assertEqual(emitted, "")
        git("commit", "--allow-empty", "-qm", "not merged")
        code, emitted = run("log-correlation-v0.3.1")
        self.assertNotEqual(code, 0)
        self.assertEqual(emitted, "")

    def test_wrong_release_version_cannot_build(self):
        output = self.work / "wrong.tgz"
        with self.assertRaisesRegex(gate.ContractError, "contract_version_mismatch"):
            gate.build_archive("0.3.2", DIGEST, output, self.root)
        self.assertFalse(output.exists())

    def test_archive_verifies_independently_after_source_changes(self):
        output = self.work / "release.tgz"
        gate.build_archive(VERSION, DIGEST, output, self.root)
        (self.root / "schema.json").write_bytes(b"{}")
        extracted = self.work / "release"
        extracted.mkdir()
        with tarfile.open(output) as archive:
            self.assertEqual(
                set(archive.getnames()),
                {
                    "schema.json",
                    "vectors.json",
                    "manifest.json",
                    "check_contract.py",
                    "README.md",
                    "design-and-validation.md",
                },
            )
            for member in archive.getmembers():
                (extracted / member.name).write_bytes(
                    archive.extractfile(member).read()
                )
        gate.load_bundle(VERSION, extracted, DIGEST)
        with self.assertRaisesRegex(gate.ContractError, "artifact_digest_mismatch"):
            gate.load_bundle(VERSION, self.root, DIGEST)


if __name__ == "__main__":
    unittest.main(verbosity=2)
