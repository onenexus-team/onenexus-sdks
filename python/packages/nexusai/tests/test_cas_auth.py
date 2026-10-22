import base64
import contextlib
import io
import importlib
import json
import unittest
from argparse import Namespace
from datetime import UTC, datetime
from importlib.util import find_spec
from unittest.mock import patch

from nexusai.auth import decode_jwt_payload, token_profile
from nexusai.cas import create_cas_client_with_credentials, credentials_from_token
from nexusai.client import OneNexusClient
from nexusai.cli import build_parser
from nexusai.cli_handlers import handle_login
from nexusai.config import CAS_BASE_URL, PLATFORM_BASE_URL
from nexusai._internal.http import APIClient


def fake_jwt(payload: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}
    parts = []
    for item in (header, payload):
        raw = json.dumps(item, separators=(",", ":")).encode("utf-8")
        parts.append(base64.urlsafe_b64encode(raw).decode("ascii").rstrip("="))
    return f"{parts[0]}.{parts[1]}.signature"


class CasAuthTest(unittest.TestCase):
    @patch("nexusai.cas.CasClient")
    def test_cas_client_accepts_refreshable_credentials(self, cas_client_cls):
        credentials = object()
        expected = object()
        cas_client_cls.return_value = expected

        result = create_cas_client_with_credentials(
            credentials,
            base_url="https://cas.example.test",
        )

        self.assertIs(result, expected)
        cas_client_cls.assert_called_once_with(
            base_url="https://cas.example.test",
            credentials=credentials,
            context=None,
            http_client=None,
        )

    def test_decode_jwt_payload_without_verifying_signature(self):
        token = fake_jwt(
            {
                "iss": "https://cas.test",
                "sub": "user-1",
                "tid": "tenant-1",
                "email": "user@example.com",
                "exp": 1_893_456_000,
            }
        )

        self.assertEqual(decode_jwt_payload(token)["tid"], "tenant-1")
        profile = token_profile(token)
        self.assertEqual(profile["tenant_id"], "tenant-1")
        self.assertEqual(profile["email"], "user@example.com")
        self.assertEqual(profile["token_type"], "jwt")

    def test_cas_credentials_forward_token_without_local_expiry_gate(self):
        token = fake_jwt({"exp": 1})

        credentials = credentials_from_token(token)
        access_token = credentials._cached

        self.assertEqual(access_token.access_token, token)
        self.assertEqual(access_token.expires_at, datetime.max.replace(tzinfo=UTC))

    def test_client_uses_single_token_interface(self):
        client = OneNexusClient(token="opaque-token")

        self.assertEqual(client.token, "opaque-token")
        self.assertFalse(hasattr(client, "access_token"))
        self.assertFalse(hasattr(client, "personal_token"))
        self.assertFalse(hasattr(client, "api_style"))
        self.assertFalse(hasattr(client, "cas_credentials"))
        self.assertFalse(hasattr(client, "upload_dataset"))
        self.assertFalse(hasattr(client, "download_dataset"))
        self.assertFalse(hasattr(client, "upload_model_version"))
        self.assertFalse(hasattr(client, "upload_model_versiion"))
        self.assertFalse(hasattr(client, "upload_to_model_version"))
        self.assertFalse(hasattr(client, "download_model"))
        self.assertFalse(hasattr(client, "download_model_dataset"))

    def test_api_client_exposes_rpc_post_only(self):
        api = APIClient(token="opaque-token")

        self.assertTrue(hasattr(api, "post"))
        self.assertFalse(hasattr(api, "request"))
        self.assertFalse(hasattr(api, "get"))
        self.assertFalse(hasattr(api, "patch"))
        self.assertFalse(hasattr(api, "delete"))

    def test_cli_only_accepts_rpc_pascal_case_domains_and_commands(self):
        parser = build_parser()

        parsed = parser.parse_args(
            ["--token", "opaque-token", "DataHub", "CreateDataset", "--name", "ds"]
        )
        self.assertEqual(parsed.domain, "DataHub")
        self.assertEqual(parsed.command, "CreateDataset")

        for args in (
            ["--token", "opaque-token", "data-hub", "CreateDataset", "--name", "ds"],
            ["--token", "opaque-token", "DataHub", "create-dataset", "--name", "ds"],
            [
                "--token",
                "opaque-token",
                "Training",
                "logs",
                "--experiment-id",
                "e",
                "--run-id",
                "r",
            ],
        ):
            with self.subTest(args=args):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        parser.parse_args(args)

    def test_cli_exposes_dataset_upload_lifecycle_commands(self):
        parser = build_parser()

        cases = (
            (
                [
                    "--token",
                    "opaque-token",
                    "DataHub",
                    "StartDatasetUpload",
                    "--dataset-id",
                    "dataset-1",
                ],
                "StartDatasetUpload",
            ),
            (
                [
                    "--token",
                    "opaque-token",
                    "DataHub",
                    "FinalizeDatasetUpload",
                    "--dataset-id",
                    "dataset-1",
                ],
                "FinalizeDatasetUpload",
            ),
            (
                [
                    "--token",
                    "opaque-token",
                    "DataHub",
                    "FailDatasetUpload",
                    "--dataset-id",
                    "dataset-1",
                    "--failure-reason",
                    "UploadFailed",
                ],
                "FailDatasetUpload",
            ),
            (
                [
                    "--token",
                    "opaque-token",
                    "DataHub",
                    "CancelDatasetUpload",
                    "--dataset-id",
                    "dataset-1",
                ],
                "CancelDatasetUpload",
            ),
        )

        for args, command in cases:
            with self.subTest(command=command):
                parsed = parser.parse_args(args)
                self.assertEqual(parsed.domain, "DataHub")
                self.assertEqual(parsed.command, command)

    def test_cli_exposes_model_version_upload_lifecycle_commands(self):
        parser = build_parser()

        cases = (
            "StartModelVersionUpload",
            "FinalizeModelVersionUpload",
            "FailModelVersionUpload",
            "CancelModelVersionUpload",
        )

        for command in cases:
            with self.subTest(command=command):
                parsed = parser.parse_args(
                    [
                        "--token",
                        "opaque-token",
                        "ModelRegistry",
                        command,
                        "--model-id",
                        "model-1",
                        "--model-version-id",
                        "version-1",
                    ]
                )
                self.assertEqual(parsed.domain, "ModelRegistry")
                self.assertEqual(parsed.command, command)

    def test_cli_only_exposes_high_level_checkpoint_and_tokenizer_transfers(self):
        parser = build_parser()

        public_cases = (
            (
                [
                    "Training",
                    "UploadToCheckpoint",
                    "--experiment-id",
                    "experiment-1",
                    "--run-id",
                    "run-1",
                    "--checkpoint-name",
                    "step-10",
                    "--source-path",
                    "/tmp/checkpoint",
                ],
                "UploadToCheckpoint",
            ),
            (
                [
                    "Training",
                    "UploadToRunTokenizer",
                    "--experiment-id",
                    "experiment-1",
                    "--run-id",
                    "run-1",
                    "--source-path",
                    "/tmp/tokenizer",
                ],
                "UploadToRunTokenizer",
            ),
        )

        for args, command in public_cases:
            with self.subTest(command=command):
                parsed = parser.parse_args(["--token", "opaque-token", *args])
                self.assertEqual(parsed.domain, args[0])
                self.assertEqual(parsed.command, command)

        for command in (
            "StartCheckpointUpload",
            "FinalizeCheckpointUpload",
            "FailCheckpointUpload",
            "CancelCheckpointUpload",
            "StartRunTokenizerUpload",
            "FinalizeRunTokenizerUpload",
            "FailRunTokenizerUpload",
            "CancelRunTokenizerUpload",
        ):
            with (
                self.subTest(command=command),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    parser.parse_args(["Training", command])

    def test_login_defaults_to_current_platform_url_not_saved_legacy_url(self):
        token = fake_jwt({"exp": 1_893_456_000})
        args = Namespace(token=token, url=None, base_url=None, cas_url=None)

        with (
            patch(
                "nexusai.cli.load_api_url", return_value="http://165.245.166.16:30210/"
            ),
            patch("nexusai.cli_handlers.save_login") as save_login,
        ):
            result = handle_login(args)

        self.assertEqual(result["api_url"], PLATFORM_BASE_URL)
        save_login.assert_called_once()
        self.assertEqual(save_login.call_args.kwargs["api_url"], PLATFORM_BASE_URL)

    def test_login_defaults_to_current_cas_url_not_saved_legacy_url(self):
        token = fake_jwt({"exp": 1_893_456_000})
        args = Namespace(token=token, url=None, base_url=None, cas_url=None)

        with (
            patch(
                "nexusai.cli_handlers.load_cas_url",
                return_value="https://cas.onenexus-do.cloud",
            ),
            patch("nexusai.cli_handlers.save_login") as save_login,
        ):
            result = handle_login(args)

        self.assertEqual(result["cas_url"], CAS_BASE_URL)
        save_login.assert_called_once()
        self.assertEqual(save_login.call_args.kwargs["cas_url"], CAS_BASE_URL)

    def test_public_modules_drop_rpc_transport_prefix(self):
        for module_name in (
            "nexusai.data_hub",
            "nexusai.training",
            "nexusai.model_registry",
            "nexusai.inference",
            "nexusai.platform_catalog",
            "nexusai.tenant_workspace",
        ):
            with self.subTest(module_name=module_name):
                self.assertIsNotNone(importlib.import_module(module_name))

        import nexusai

        self.assertFalse(hasattr(nexusai, "RpcDataHubClient"))
        self.assertFalse(hasattr(nexusai, "RpcTrainingClient"))
        self.assertFalse(hasattr(nexusai, "WorkloadClient"))
        self.assertFalse(hasattr(nexusai, "InternalWorkloadClient"))

        for legacy_module in (
            "nexusai.rpc_data_hub",
            "nexusai.rpc_training",
            "nexusai.rpc_model_registry",
            "nexusai.rpc_inference",
            "nexusai.rpc_platform_catalog",
            "nexusai.rpc_tenant_workspace",
            "nexusai.internal_workload",
            "nexusai.workload_auth",
            "nexusai.http",
            "nexusai.storage",
            "nexusai.cas_storage",
        ):
            with self.subTest(legacy_module=legacy_module):
                self.assertIsNone(find_spec(legacy_module))

    def test_cli_reports_package_version(self):
        parser = build_parser()

        with contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as exit_info:
                parser.parse_args(["--version"])

        self.assertEqual(exit_info.exception.code, 0)
        self.assertRegex(output.getvalue(), r"^nexusai \d+\.\d+\.\d+\n$")


if __name__ == "__main__":
    unittest.main()
