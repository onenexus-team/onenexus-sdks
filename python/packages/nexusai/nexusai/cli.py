import argparse
import json
from dataclasses import asdict, is_dataclass
from typing import Any, cast

from .auth import (
    delete_token,
    load_api_url,
    load_cas_url,
    load_token,
    prompt_token,
    save_login,
    token_profile,
)
from .client import OneNexusClient
from .config import PLATFORM_BASE_URL


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "auth_command", None):
        result = args.handler(args)
        if result is not None:
            print_json(result)
        return

    token = load_token(args.token)
    if not token:
        parser.error("run `nexusai login` or pass --token")

    client = OneNexusClient(
        token=token,
        base_url=load_api_url(args.base_url),
        cas_url=load_cas_url(args.cas_url),
    )
    result = args.handler(client, args)
    if result is not None:
        print_json(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexusai")
    parser.add_argument("--token", help="Token. Overrides saved login token.")
    parser.add_argument(
        "--base-url",
        help="Platform URL. Overrides saved login URL for this command.",
    )
    parser.add_argument(
        "--cas-url",
        help="CAS URL. Overrides saved CAS URL for this command.",
    )
    domains = parser.add_subparsers(dest="domain", required=True)

    add_auth_commands(domains)
    add_tenant_workspace_commands(domains)
    add_data_hub_commands(domains)
    add_model_registry_commands(domains)
    add_training_commands(domains)
    add_inference_commands(domains)
    return parser


def add_auth_commands(
    domains: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    login = domains.add_parser("login")
    login.add_argument("--token", help="Token to save. Prompts if omitted.")
    login.add_argument(
        "--url",
        help="Platform URL to save. Defaults to https://ai-api-v2.onenexus-do.cloud.",
    )
    login.add_argument(
        "--cas-url",
        help="CAS URL to save. Defaults to https://cas.onenexus-do.cloud.",
    )
    login.set_defaults(auth_command=True, handler=handle_login)

    logout = domains.add_parser("logout")
    logout.set_defaults(auth_command=True, handler=handle_logout)

    whoami = domains.add_parser("whoami")
    whoami.set_defaults(auth_command=True, handler=handle_whoami)


def add_tenant_workspace_commands(
    domains: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    tenant_workspace = domains.add_parser("TenantWorkspace")
    commands = tenant_workspace.add_subparsers(dest="command", required=True)

    command = commands.add_parser("CreateTenantWorkspace")
    add_required(command, "--name")
    add_required(command, "--model-registry-bucket")
    add_required(command, "--datahub-bucket")
    add_required(command, "--checkpoint-bucket")
    add_required(command, "--tokenizer-bucket")
    command.add_argument("--tenant-gpus-quota", type=int, default=16)
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_tenant_workspace)

    command = commands.add_parser("GetTenantWorkspace")
    add_required(command, "--workspace-id")
    command.set_defaults(handler=handle_get_tenant_workspace)

    command = commands.add_parser("ListTenantWorkspaces")
    add_list_filters(command)
    command.set_defaults(handler=handle_list_tenant_workspaces)


def add_data_hub_commands(
    domains: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    data_hub = domains.add_parser("DataHub")
    commands = data_hub.add_subparsers(dest="command", required=True)

    command = commands.add_parser("CreateDataset")
    add_required(command, "--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_dataset)

    command = commands.add_parser("ListDatasets")
    add_list_filters(command)
    command.set_defaults(handler=handle_list_datasets)

    command = commands.add_parser("GetDataset")
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handle_get_dataset)

    command = commands.add_parser("UpdateDataset")
    add_required(command, "--dataset-id")
    command.add_argument("--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_update_dataset)

    command = commands.add_parser("DeleteDataset")
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handle_delete_dataset)

    command = commands.add_parser("StartDatasetUpload")
    add_required(command, "--dataset-id")
    command.add_argument("--idempotency-key")
    command.add_argument("--declared-manifest-json")
    command.add_argument("--reserved-quota-bytes", type=int, default=0)
    command.add_argument("--lease-ttl-seconds", type=int, default=3600)
    command.set_defaults(handler=handle_start_dataset_upload)

    command = commands.add_parser("FinalizeDatasetUpload")
    add_required(command, "--dataset-id")
    command.add_argument("--manifest-json")
    command.add_argument("--file-count", type=int, default=0)
    command.add_argument("--total-size-bytes", type=int, default=0)
    command.set_defaults(handler=handle_finalize_dataset_upload)

    command = commands.add_parser("FailDatasetUpload")
    add_required(command, "--dataset-id")
    add_required(command, "--failure-reason")
    command.add_argument("--last-error")
    command.set_defaults(handler=handle_fail_dataset_upload)

    command = commands.add_parser("CancelDatasetUpload")
    add_required(command, "--dataset-id")
    command.add_argument("--cancel-reason")
    command.set_defaults(handler=handle_cancel_dataset_upload)

    command = commands.add_parser("ListDatasetFiles")
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handle_dataset_files)

    command = commands.add_parser("GetDatasetSize")
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handle_dataset_size)

    command = commands.add_parser("GetUploadDatasetInstruction")
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handle_upload_dataset_instruction)

    command = commands.add_parser("UploadDataset")
    add_required(command, "--name")
    add_required(command, "--source-path")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_upload_dataset)

    command = commands.add_parser("UploadToDataset")
    add_required(command, "--dataset-id")
    add_required(command, "--source-path")
    command.set_defaults(handler=handle_upload_to_dataset)

    command = commands.add_parser("DownloadDataset")
    add_required(command, "--dataset-id")
    add_required(command, "--destination-path")
    command.set_defaults(handler=handle_download_dataset)


def add_model_registry_commands(
    domains: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    registry = domains.add_parser("ModelRegistry")
    commands = registry.add_subparsers(dest="command", required=True)

    command = commands.add_parser("CreateModel")
    add_required(command, "--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_model)

    command = commands.add_parser("ListModels")
    add_list_filters(command)
    command.set_defaults(handler=handle_list_models)

    command = commands.add_parser("GetModel")
    add_required(command, "--model-id")
    command.set_defaults(handler=handle_get_model)

    command = commands.add_parser("UpdateModel")
    add_required(command, "--model-id")
    command.add_argument("--name")
    command.add_argument("--latest-version-id")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_update_model)

    command = commands.add_parser("DeleteModel")
    add_required(command, "--model-id")
    command.set_defaults(handler=handle_delete_model)

    command = commands.add_parser("CreateModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--name")
    command.add_argument("--training-experiment-name")
    command.add_argument("--training-run-name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_model_version)

    command = commands.add_parser("CreateModelVersionFromCheckpoint")
    add_required(command, "--model-id")
    add_required(command, "--name")
    add_required(command, "--experiment-id")
    add_required(command, "--run-id")
    add_required(command, "--checkpoint-name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_model_version_from_checkpoint)

    command = commands.add_parser("ListModelVersions")
    add_required(command, "--model-id")
    add_list_filters(command)
    command.add_argument("--training-experiment-name")
    command.add_argument("--training-run-name")
    command.set_defaults(handler=handle_list_model_versions)

    command = commands.add_parser("GetModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handle_get_model_version)

    command = commands.add_parser("UpdateModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.add_argument("--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_update_model_version)

    command = commands.add_parser("DeleteModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handle_delete_model_version)

    command = commands.add_parser("StartModelVersionUpload")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.add_argument("--idempotency-key")
    command.add_argument("--declared-manifest-json")
    command.add_argument("--reserved-quota-bytes", type=int, default=0)
    command.set_defaults(handler=handle_start_model_version_upload)

    command = commands.add_parser("FinalizeModelVersionUpload")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.add_argument("--manifest-json")
    command.add_argument("--file-count", type=int, default=0)
    command.add_argument("--total-size-bytes", type=int, default=0)
    command.add_argument("--artifact-format")
    command.set_defaults(handler=handle_finalize_model_version_upload)

    command = commands.add_parser("FailModelVersionUpload")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.add_argument("--failure-reason")
    command.add_argument("--failure-message")
    command.set_defaults(handler=handle_fail_model_version_upload)

    command = commands.add_parser("CancelModelVersionUpload")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.add_argument("--failure-reason")
    command.add_argument("--failure-message")
    command.set_defaults(handler=handle_cancel_model_version_upload)

    command = commands.add_parser("ListModelVersionFiles")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handle_model_version_files)

    command = commands.add_parser("GetModelVersionSize")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handle_model_version_size)

    command = commands.add_parser("UploadModelVersion")
    add_required(command, "--model-name")
    add_required(command, "--version-name")
    add_required(command, "--source-path")
    command.add_argument("--model-extras-json")
    command.add_argument("--version-extras-json")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_upload_model_version)

    command = commands.add_parser("UploadModelVersionById")
    add_required(command, "--model-id")
    add_required(command, "--version-name")
    add_required(command, "--source-path")
    command.add_argument("--version-extras-json")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_upload_model_version_by_id)

    command = commands.add_parser("UploadToModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    add_required(command, "--source-path")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_upload_to_model_version)

    command = commands.add_parser("DownloadModel")
    add_required(command, "--model-id")
    add_required(command, "--destination-path")
    command.add_argument("--model-version-id")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_download_model)

    command = commands.add_parser("DownloadModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    add_required(command, "--destination-path")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_download_model_version)


def add_training_commands(
    domains: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    training = domains.add_parser("Training")
    commands = training.add_subparsers(dest="command", required=True)

    command = commands.add_parser("CreateExperiment")
    add_required(command, "--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_experiment)

    command = commands.add_parser("ListExperiments")
    add_list_filters(command)
    command.set_defaults(handler=handle_list_experiments)

    command = commands.add_parser("GetExperiment")
    add_required(command, "--experiment-id")
    command.set_defaults(handler=handle_get_experiment)

    command = commands.add_parser("UpdateExperiment")
    add_required(command, "--experiment-id")
    command.add_argument("--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_update_experiment)

    command = commands.add_parser("DeleteExperiment")
    add_required(command, "--experiment-id")
    command.set_defaults(handler=handle_delete_experiment)

    command = commands.add_parser("CreateRun")
    add_required(
        command,
        "--experiment-id",
        "--name",
        "--dataset-id",
        "--training-type",
        "--flavor",
        "--input-model-id",
    )
    command.add_argument("--input-model-version-id")
    command.add_argument("--hyperparameters-json", default="{}")
    command.add_argument("--num-checkpoint", type=int, default=0)
    command.add_argument("--output-model-name")
    command.add_argument("--output-model-version-name")
    command.add_argument("--checkpoint-path")
    command.add_argument("--tokenizer-path")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_run)

    command = commands.add_parser("ListRuns")
    add_required(command, "--experiment-id")
    add_list_filters(command)
    command.add_argument("--training-type")
    command.add_argument("--dataset-name")
    command.add_argument("--output-model-name")
    command.add_argument("--output-model-version-name")
    command.add_argument("--status")
    command.set_defaults(handler=handle_list_runs)

    command = commands.add_parser("GetRun")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_get_run)

    command = commands.add_parser("StopRun")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_stop_run)

    command = commands.add_parser("CancelRun")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_cancel_run)

    command = commands.add_parser("DeleteRun")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_delete_run)

    command = commands.add_parser("ResumeRun")
    add_experiment_run_ids(command)
    command.add_argument("--checkpoint-name")
    command.add_argument("--hyperparameters-json")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_resume_run)

    command = commands.add_parser("GetRunLogs")
    add_experiment_run_ids(command)
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handle_get_run_logs)

    command = commands.add_parser("GetRunMetrics")
    add_experiment_run_ids(command)
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handle_get_run_metrics)

    command = commands.add_parser("ListRunCheckpoints")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_list_run_checkpoints)

    command = commands.add_parser("GetRunCheckpoint")
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-id")
    command.set_defaults(handler=handle_get_run_checkpoint)

    command = commands.add_parser("StartCheckpointUpload")
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-name")
    add_checkpoint_start_args(command)
    command.set_defaults(handler=handle_start_checkpoint_upload)

    command = commands.add_parser("FinalizeCheckpointUpload")
    add_experiment_run_ids(command)
    add_checkpoint_upload_identity_args(command)
    command.add_argument("--manifest-json")
    command.add_argument("--file-count", type=int, default=0)
    command.add_argument("--total-size-bytes", type=int, default=0)
    command.set_defaults(handler=handle_finalize_checkpoint_upload)

    command = commands.add_parser("FailCheckpointUpload")
    add_experiment_run_ids(command)
    add_checkpoint_upload_identity_args(command)
    command.add_argument("--failure-reason")
    command.add_argument("--failure-message")
    command.set_defaults(handler=handle_fail_checkpoint_upload)

    command = commands.add_parser("CancelCheckpointUpload")
    add_experiment_run_ids(command)
    add_checkpoint_upload_identity_args(command)
    command.add_argument("--failure-reason")
    command.add_argument("--failure-message")
    command.set_defaults(handler=handle_cancel_checkpoint_upload)

    command = commands.add_parser("UploadToCheckpoint")
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-name")
    add_required(command, "--source-path")
    add_checkpoint_start_args(command, process_index_default=0)
    command.set_defaults(handler=handle_upload_to_checkpoint)

    command = commands.add_parser("FailRunCheckpoint")
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-id")
    command.add_argument("--failure-reason")
    command.add_argument("--failure-message")
    command.set_defaults(handler=handle_fail_run_checkpoint)

    command = commands.add_parser("DeleteRunCheckpoints")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_delete_run_checkpoints)

    command = commands.add_parser("ListRunCheckpointFiles")
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-name")
    command.set_defaults(handler=handle_list_run_checkpoint_files)

    command = commands.add_parser("DeleteRunCheckpoint")
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-name")
    command.set_defaults(handler=handle_delete_run_checkpoint)

    command = commands.add_parser("GetRunTokenizer")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_get_run_tokenizer)

    command = commands.add_parser("StartRunTokenizerUpload")
    add_experiment_run_ids(command)
    add_run_tokenizer_upload_args(command, include_manifest=True)
    command.set_defaults(handler=handle_start_run_tokenizer_upload)

    command = commands.add_parser("FinalizeRunTokenizerUpload")
    add_experiment_run_ids(command)
    command.add_argument("--manifest-json")
    command.add_argument("--file-count", type=int, default=0)
    command.add_argument("--total-size-bytes", type=int, default=0)
    command.set_defaults(handler=handle_finalize_run_tokenizer_upload)

    command = commands.add_parser("FailRunTokenizerUpload")
    add_experiment_run_ids(command)
    command.add_argument("--failure-reason")
    command.add_argument("--failure-message")
    command.set_defaults(handler=handle_fail_run_tokenizer_upload)

    command = commands.add_parser("CancelRunTokenizerUpload")
    add_experiment_run_ids(command)
    command.add_argument("--failure-reason")
    command.add_argument("--failure-message")
    command.set_defaults(handler=handle_cancel_run_tokenizer_upload)

    command = commands.add_parser("UploadToRunTokenizer")
    add_experiment_run_ids(command)
    add_required(command, "--source-path")
    add_run_tokenizer_upload_args(command)
    command.set_defaults(handler=handle_upload_to_run_tokenizer)

    command = commands.add_parser("DeleteRunTokenizer")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_delete_run_tokenizer)


def add_inference_commands(
    domains: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    inference = domains.add_parser("Inference")
    commands = inference.add_subparsers(dest="command", required=True)

    command = commands.add_parser("CreateInferenceInstance")
    add_required(command, "--name")
    add_required(command, "--model-id")
    command.add_argument("--model-version-id")
    add_required(command, "--served-model-name")
    add_required(command, "--flavor")
    command.add_argument("--configuration-json")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_inference_instance)

    command = commands.add_parser("ListInferenceInstances")
    add_list_filters(command)
    command.add_argument("--model-id")
    command.add_argument("--model-version-id")
    command.add_argument("--status")
    command.set_defaults(handler=handle_list_inference_instances)

    command = commands.add_parser("GetInferenceInstance")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_get_inference_instance)

    command = commands.add_parser("UpdateInferenceInstance")
    add_required(command, "--inference-instance-id")
    command.add_argument("--name")
    command.add_argument("--model-id")
    command.add_argument("--model-version-id")
    command.add_argument("--clear-model-version-id", action="store_true")
    command.add_argument("--served-model-name")
    command.add_argument("--flavor")
    command.add_argument("--configuration-json")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_update_inference_instance)

    command = commands.add_parser("StopInferenceInstance")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_stop_inference_instance)

    command = commands.add_parser("RestartInferenceInstance")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_restart_inference_instance)

    command = commands.add_parser("FinalizeInferenceInstance")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_finalize_inference_instance)

    command = commands.add_parser("DeleteInferenceInstance")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_delete_inference_instance)

    command = commands.add_parser("GetInferenceInstanceEndpoint")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_get_inference_instance_endpoint)

    command = commands.add_parser("GetInferenceInstanceLogs")
    add_required(command, "--inference-instance-id")
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handle_get_inference_instance_logs)

    command = commands.add_parser("GetInferenceInstanceMetrics")
    add_required(command, "--inference-instance-id")
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handle_get_inference_instance_metrics)


def add_required(command: argparse.ArgumentParser, *flags: str) -> None:
    command.add_argument(*flags, required=True)


def add_list_filters(command: argparse.ArgumentParser) -> None:
    command.add_argument("--name")
    command.add_argument("--page", type=int)
    command.add_argument("--limit", type=int)
    command.add_argument("--start-time")
    command.add_argument("--end-time")


def add_expires_arg(command: argparse.ArgumentParser) -> None:
    command.add_argument("--expires-in", type=int, default=3600)


def add_experiment_run_ids(command: argparse.ArgumentParser) -> None:
    add_required(command, "--experiment-id")
    add_required(command, "--run-id")


def add_checkpoint_start_args(
    command: argparse.ArgumentParser,
    *,
    process_index_default: int | None = None,
) -> None:
    command.add_argument("--execution-id")
    command.add_argument("--attempt", type=int)
    command.add_argument("--checkpoint-step", type=int)
    command.add_argument("--num-process", type=int, default=1)
    command.add_argument("--process-index", type=int, default=process_index_default)
    command.add_argument("--process-name")
    command.add_argument("--pod-name")
    command.add_argument("--idempotency-key")
    command.add_argument("--storage-bucket")
    command.add_argument("--storage-prefix")


def add_checkpoint_upload_identity_args(command: argparse.ArgumentParser) -> None:
    command.add_argument("--checkpoint-name")
    command.add_argument("--checkpoint-id")
    command.add_argument("--execution-id")
    command.add_argument("--process-index", type=int)
    command.add_argument("--process-name")
    command.add_argument("--pod-name")
    command.add_argument("--storage-prefix")
    command.add_argument("--idempotency-key")


def add_run_tokenizer_upload_args(
    command: argparse.ArgumentParser,
    *,
    include_manifest: bool = False,
) -> None:
    command.add_argument("--execution-id")
    command.add_argument("--attempt", type=int)
    command.add_argument("--storage-bucket")
    command.add_argument("--storage-prefix")
    if include_manifest:
        command.add_argument("--manifest-json")
        command.add_argument("--file-count", type=int, default=0)
        command.add_argument("--total-size-bytes", type=int, default=0)


def handle_login(args: argparse.Namespace) -> Any:
    token = args.token or prompt_token()
    api_url = args.url or args.base_url or PLATFORM_BASE_URL
    cas_url = args.cas_url or load_cas_url()
    save_login(token=token, api_url=api_url, cas_url=cas_url)
    profile = token_profile(token)
    return {"logged_in": True, "api_url": api_url, "cas_url": cas_url, **profile}


def handle_logout(args: argparse.Namespace) -> Any:
    return {"logged_out": delete_token()}


def handle_whoami(args: argparse.Namespace) -> Any:
    token = load_token(args.token)
    profile = token_profile(token) if token else {}
    return {
        "logged_in": bool(token),
        "token_source": "explicit_or_saved" if token else None,
        "api_url": load_api_url(args.base_url),
        "cas_url": load_cas_url(args.cas_url),
        **profile,
    }


def handle_create_tenant_workspace(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.tenant_workspace.create_tenant_workspace(
        name=args.name,
        model_registry_bucket=args.model_registry_bucket,
        datahub_bucket=args.datahub_bucket,
        checkpoint_bucket=args.checkpoint_bucket,
        tokenizer_bucket=args.tokenizer_bucket,
        tenant_gpus_quota=args.tenant_gpus_quota,
        extras_data=parse_json(args.extras_json),
    )


def handle_get_tenant_workspace(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.tenant_workspace.get_tenant_workspace(args.workspace_id)


def handle_list_tenant_workspaces(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.tenant_workspace.list_tenant_workspaces(
        page=args.page,
        limit=args.limit,
        name=args.name,
        start_time=args.start_time,
        end_time=args.end_time,
    )


def handle_create_dataset(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.create_dataset(
        name=args.name,
        extras_data=parse_json(args.extras_json),
    )


def handle_list_datasets(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.list_datasets(
        page=args.page,
        limit=args.limit,
        name=args.name,
        start_time=args.start_time,
        end_time=args.end_time,
    )


def handle_get_dataset(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.get_dataset(args.dataset_id)


def handle_update_dataset(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.update_dataset(
        dataset_id=args.dataset_id,
        name=args.name,
        extras_data=parse_json(args.extras_json),
    )


def handle_delete_dataset(client: OneNexusClient, args: argparse.Namespace) -> Any:
    client.data_hub.delete_dataset(args.dataset_id)
    return None


def handle_start_dataset_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.start_dataset_upload(
        dataset_id=args.dataset_id,
        idempotency_key=args.idempotency_key,
        declared_manifest=parse_json(args.declared_manifest_json),
        reserved_quota_bytes=args.reserved_quota_bytes,
        lease_ttl_seconds=args.lease_ttl_seconds,
    )


def handle_finalize_dataset_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.finalize_dataset_upload(
        dataset_id=args.dataset_id,
        manifest=parse_json(args.manifest_json),
        file_count=args.file_count,
        total_size_bytes=args.total_size_bytes,
    )


def handle_fail_dataset_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.fail_dataset_upload(
        dataset_id=args.dataset_id,
        failure_reason=args.failure_reason,
        last_error=args.last_error,
    )


def handle_cancel_dataset_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.cancel_dataset_upload(
        dataset_id=args.dataset_id,
        cancel_reason=args.cancel_reason,
    )


def handle_dataset_files(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.list_dataset_files(args.dataset_id)


def handle_dataset_size(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.get_dataset_size(args.dataset_id)


def handle_upload_dataset_instruction(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.upload_dataset_instruction(args.dataset_id)


def handle_upload_dataset(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.upload_dataset(
        name=args.name,
        source_path=args.source_path,
        extras_data=parse_json(args.extras_json),
    )


def handle_upload_to_dataset(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.upload_to_dataset(
        dataset_id=args.dataset_id,
        source_path=args.source_path,
    )


def handle_download_dataset(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.download_dataset(
        dataset_id=args.dataset_id,
        destination_path=args.destination_path,
    )


def handle_create_model(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.create_model(
        name=args.name,
        extras_data=parse_json(args.extras_json),
    )


def handle_list_models(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.list_models(
        page=args.page,
        limit=args.limit,
        name=args.name,
        start_time=args.start_time,
        end_time=args.end_time,
    )


def handle_get_model(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.get_model(args.model_id)


def handle_update_model(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.update_model(
        model_id=args.model_id,
        name=args.name,
        latest_version_id=args.latest_version_id,
        extras_data=parse_json(args.extras_json),
    )


def handle_delete_model(client: OneNexusClient, args: argparse.Namespace) -> Any:
    client.model_registry.delete_model(args.model_id)
    return None


def handle_create_model_version(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.create_model_version(
        model_id=args.model_id,
        name=args.name,
        training_experiment_name=args.training_experiment_name,
        training_run_name=args.training_run_name,
        extras_data=parse_json(args.extras_json),
    )


def handle_create_model_version_from_checkpoint(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.create_model_version_from_checkpoint(
        model_id=args.model_id,
        name=args.name,
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        extras_data=parse_json(args.extras_json),
    )


def handle_list_model_versions(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.list_model_versions(
        model_id=args.model_id,
        page=args.page,
        limit=args.limit,
        name=args.name,
        start_time=args.start_time,
        end_time=args.end_time,
        training_experiment_name=args.training_experiment_name,
        training_run_name=args.training_run_name,
    )


def handle_get_model_version(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.get_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
    )


def handle_update_model_version(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.update_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        name=args.name,
        extras_data=parse_json(args.extras_json),
    )


def handle_delete_model_version(client: OneNexusClient, args: argparse.Namespace) -> Any:
    client.model_registry.delete_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
    )
    return None


def handle_start_model_version_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.start_model_version_upload(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        idempotency_key=args.idempotency_key,
        declared_manifest=parse_json(args.declared_manifest_json),
        reserved_quota_bytes=args.reserved_quota_bytes,
    )


def handle_finalize_model_version_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.finalize_model_version_upload(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        manifest=parse_json(args.manifest_json),
        file_count=args.file_count,
        total_size_bytes=args.total_size_bytes,
        artifact_format=args.artifact_format,
    )


def handle_fail_model_version_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.fail_model_version_upload(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        failure_reason=args.failure_reason,
        failure_message=args.failure_message,
    )


def handle_cancel_model_version_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.cancel_model_version_upload(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        failure_reason=args.failure_reason,
        failure_message=args.failure_message,
    )


def handle_model_version_files(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.list_model_version_files(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
    )


def handle_model_version_size(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.get_model_version_size(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
    )


def handle_upload_model_version(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.upload_model_version(
        model_name=args.model_name,
        version_name=args.version_name,
        source_path=args.source_path,
        model_extras_data=parse_json(args.model_extras_json),
        version_extras_data=parse_json(args.version_extras_json),
        expires_in=args.expires_in,
    )


def handle_upload_model_version_by_id(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.upload_model_version_by_id(
        model_id=args.model_id,
        version_name=args.version_name,
        source_path=args.source_path,
        version_extras_data=parse_json(args.version_extras_json),
        expires_in=args.expires_in,
    )


def handle_upload_to_model_version(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.upload_to_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        source_path=args.source_path,
        expires_in=args.expires_in,
    )


def handle_download_model(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.download_model(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        destination_path=args.destination_path,
        expires_in=args.expires_in,
    )


def handle_download_model_version(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.download_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        destination_path=args.destination_path,
        expires_in=args.expires_in,
    )


def handle_create_experiment(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.create_experiment(
        name=args.name,
        extras_data=parse_json(args.extras_json),
    )


def handle_list_experiments(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.list_experiments(
        page=args.page,
        limit=args.limit,
        name=args.name,
        start_time=args.start_time,
        end_time=args.end_time,
    )


def handle_get_experiment(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.get_experiment(args.experiment_id)


def handle_update_experiment(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.update_experiment(
        experiment_id=args.experiment_id,
        name=args.name,
        extras_data=parse_json(args.extras_json),
    )


def handle_delete_experiment(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.delete_experiment(args.experiment_id)


def handle_create_run(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.create_run(
        experiment_id=args.experiment_id,
        name=args.name,
        dataset_id=args.dataset_id,
        training_type=args.training_type,
        flavor=args.flavor,
        input_model_id=args.input_model_id,
        input_model_version_id=args.input_model_version_id,
        hyperparameters=parse_json(args.hyperparameters_json) or {},
        num_checkpoint=args.num_checkpoint,
        output_model_name=args.output_model_name,
        output_model_version_name=args.output_model_version_name,
        checkpoint_path=args.checkpoint_path,
        tokenizer_path=args.tokenizer_path,
        extras_data=parse_json(args.extras_json),
    )


def handle_list_runs(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.list_runs(
        experiment_id=args.experiment_id,
        page=args.page,
        limit=args.limit,
        name=args.name,
        training_type=args.training_type,
        dataset_name=args.dataset_name,
        output_model_name=args.output_model_name,
        output_model_version_name=args.output_model_version_name,
        status=args.status,
        start_time=args.start_time,
        end_time=args.end_time,
    )


def handle_get_run(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.get_run(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_stop_run(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.stop_run(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_cancel_run(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.cancel_run(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_delete_run(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.delete_run(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_resume_run(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.resume_run(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        hyperparameters=parse_json(args.hyperparameters_json),
        extras_data=parse_json(args.extras_json),
    )


def handle_get_run_logs(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.get_run_logs(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        start_timestamp=args.start_timestamp,
        end_timestamp=args.end_timestamp,
    )


def handle_get_run_metrics(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.get_run_metrics(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        start_timestamp=args.start_timestamp,
        end_timestamp=args.end_timestamp,
    )


def handle_list_run_checkpoints(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.list_run_checkpoints(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_get_run_checkpoint(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.get_run_checkpoint(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_id=args.checkpoint_id,
    )


def handle_start_checkpoint_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.start_checkpoint_upload(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        execution_id=args.execution_id,
        attempt=args.attempt,
        checkpoint_step=args.checkpoint_step,
        num_process=args.num_process,
        process_index=args.process_index,
        process_name=args.process_name,
        pod_name=args.pod_name,
        idempotency_key=args.idempotency_key,
        storage_bucket=args.storage_bucket,
        storage_prefix=args.storage_prefix,
    )


def handle_finalize_checkpoint_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.finalize_checkpoint_upload(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        checkpoint_id=args.checkpoint_id,
        execution_id=args.execution_id,
        process_index=args.process_index,
        process_name=args.process_name,
        pod_name=args.pod_name,
        storage_prefix=args.storage_prefix,
        manifest=parse_json(args.manifest_json),
        file_count=args.file_count,
        total_size_bytes=args.total_size_bytes,
        idempotency_key=args.idempotency_key,
    )


def handle_fail_checkpoint_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.fail_checkpoint_upload(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        checkpoint_id=args.checkpoint_id,
        execution_id=args.execution_id,
        process_index=args.process_index,
        process_name=args.process_name,
        pod_name=args.pod_name,
        storage_prefix=args.storage_prefix,
        idempotency_key=args.idempotency_key,
        failure_reason=args.failure_reason,
        failure_message=args.failure_message,
    )


def handle_cancel_checkpoint_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.cancel_checkpoint_upload(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        checkpoint_id=args.checkpoint_id,
        execution_id=args.execution_id,
        process_index=args.process_index,
        process_name=args.process_name,
        pod_name=args.pod_name,
        storage_prefix=args.storage_prefix,
        idempotency_key=args.idempotency_key,
        failure_reason=args.failure_reason,
        failure_message=args.failure_message,
    )


def handle_upload_to_checkpoint(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.upload_to_checkpoint(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        source_path=args.source_path,
        execution_id=args.execution_id,
        attempt=args.attempt,
        checkpoint_step=args.checkpoint_step,
        num_process=args.num_process,
        process_index=args.process_index,
        process_name=args.process_name,
        pod_name=args.pod_name,
        idempotency_key=args.idempotency_key,
        storage_bucket=args.storage_bucket,
        storage_prefix=args.storage_prefix,
    )


def handle_fail_run_checkpoint(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.fail_run_checkpoint(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_id=args.checkpoint_id,
        failure_reason=args.failure_reason,
        failure_message=args.failure_message,
    )


def handle_delete_run_checkpoints(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.delete_run_checkpoints(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_list_run_checkpoint_files(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.list_run_checkpoint_files(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
    )


def handle_delete_run_checkpoint(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.delete_run_checkpoint(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
    )


def handle_get_run_tokenizer(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.get_run_tokenizer(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_start_run_tokenizer_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.start_run_tokenizer_upload(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        execution_id=args.execution_id,
        attempt=args.attempt,
        storage_bucket=args.storage_bucket,
        storage_prefix=args.storage_prefix,
        manifest=parse_json(args.manifest_json),
        file_count=args.file_count,
        total_size_bytes=args.total_size_bytes,
    )


def handle_finalize_run_tokenizer_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.finalize_run_tokenizer_upload(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        manifest=parse_json(args.manifest_json),
        file_count=args.file_count,
        total_size_bytes=args.total_size_bytes,
    )


def handle_fail_run_tokenizer_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.fail_run_tokenizer_upload(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        failure_reason=args.failure_reason,
        failure_message=args.failure_message,
    )


def handle_cancel_run_tokenizer_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.cancel_run_tokenizer_upload(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        failure_reason=args.failure_reason,
        failure_message=args.failure_message,
    )


def handle_upload_to_run_tokenizer(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.upload_to_run_tokenizer(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        source_path=args.source_path,
        execution_id=args.execution_id,
        attempt=args.attempt,
        storage_bucket=args.storage_bucket,
        storage_prefix=args.storage_prefix,
    )


def handle_delete_run_tokenizer(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.training.delete_run_tokenizer(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_create_inference_instance(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.inference.create_inference_instance(
        name=args.name,
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        served_model_name=args.served_model_name,
        flavor=args.flavor,
        configuration=parse_json(args.configuration_json),
        extras_data=parse_json(args.extras_json),
    )


def handle_list_inference_instances(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.inference.list_inference_instances(
        page=args.page,
        limit=args.limit,
        name=args.name,
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        status=args.status,
        start_time=args.start_time,
        end_time=args.end_time,
    )


def handle_get_inference_instance(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.inference.get_inference_instance(args.inference_instance_id)


def handle_update_inference_instance(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.inference.update_inference_instance(
        inference_instance_id=args.inference_instance_id,
        name=args.name,
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        clear_model_version_id=args.clear_model_version_id,
        served_model_name=args.served_model_name,
        flavor=args.flavor,
        configuration=parse_json(args.configuration_json),
        extras_data=parse_json(args.extras_json),
    )


def handle_stop_inference_instance(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.inference.stop_inference_instance(args.inference_instance_id)


def handle_restart_inference_instance(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.inference.restart_inference_instance(args.inference_instance_id)


def handle_finalize_inference_instance(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.inference.finalize_inference_instance(args.inference_instance_id)


def handle_delete_inference_instance(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.inference.delete_inference_instance(args.inference_instance_id)


def handle_get_inference_instance_endpoint(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.inference.get_inference_instance_endpoint(
        args.inference_instance_id
    )


def handle_get_inference_instance_logs(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.inference.get_inference_instance_logs(
        inference_instance_id=args.inference_instance_id,
        start_timestamp=args.start_timestamp,
        end_timestamp=args.end_timestamp,
    )


def handle_get_inference_instance_metrics(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.inference.get_inference_instance_metrics(
        inference_instance_id=args.inference_instance_id,
        start_timestamp=args.start_timestamp,
        end_timestamp=args.end_timestamp,
    )


def parse_json(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("JSON value must be an object")
    return parsed


def print_json(value: Any) -> None:
    print(json.dumps(to_jsonable(value), indent=2, sort_keys=True))


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(cast(Any, value)))
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value
