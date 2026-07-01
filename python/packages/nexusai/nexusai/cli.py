import argparse
import json
from dataclasses import asdict, is_dataclass
from typing import Any

from .auth import (
    delete_token,
    load_api_url,
    load_cas_url,
    load_token,
    prompt_token,
    save_login,
    token_profile,
)
from .client import SDK_API_STYLES, OneNexusClient


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "auth_command", None):
        result = args.handler(args)
        if result is not None:
            print_json(result)
        return

    token = load_token(args.access_token or args.personal_token)
    if not token:
        parser.error("run `nexusai login` or pass --access-token")

    client = OneNexusClient(
        access_token=token,
        api_style=args.api_style,
        base_url=load_api_url(args.base_url),
        cas_url=load_cas_url(args.cas_url),
    )
    result = args.handler(client, args)
    if result is not None:
        print_json(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexusai")
    parser.add_argument(
        "--personal-token",
        help="Deprecated alias for --access-token.",
    )
    parser.add_argument(
        "--access-token",
        help="CAS access token. Overrides saved login token.",
    )
    parser.add_argument(
        "--base-url",
        help="Platform URL. Overrides saved login URL for this command.",
    )
    parser.add_argument(
        "--cas-url",
        help="CAS URL. Overrides saved CAS URL for this command.",
    )
    parser.add_argument(
        "--api-style",
        choices=SDK_API_STYLES,
        default="rpc",
        help="API interface to use. Defaults to rpc.",
    )
    domains = parser.add_subparsers(dest="domain", required=True)

    add_auth_commands(domains)
    add_tenant_workspace_commands(domains)
    add_data_hub_commands(domains)
    add_model_registry_commands(domains)
    add_training_commands(domains)
    add_inference_commands(domains)
    return parser


def add_auth_commands(domains) -> None:
    login = domains.add_parser("login")
    login.add_argument(
        "--access-token",
        help="CAS access token to save. Prompts if omitted.",
    )
    login.add_argument("--personal-token", help="Deprecated alias for --access-token.")
    login.add_argument(
        "--url",
        help="Platform URL to save. Defaults to http://165.245.166.16:30210.",
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


def add_tenant_workspace_commands(domains) -> None:
    tenant_workspace = domains.add_parser(
        "TenantWorkspace",
        aliases=["tenant-workspace", "workspace", "workspaces"],
    )
    commands = tenant_workspace.add_subparsers(dest="command", required=True)

    command = commands.add_parser(
        "CreateTenantWorkspace",
        aliases=["create-tenant-workspace", "create"],
    )
    add_required(command, "--name")
    add_required(command, "--model-registry-bucket")
    add_required(command, "--datahub-bucket")
    add_required(command, "--checkpoint-bucket")
    add_required(command, "--tokenizer-bucket")
    command.add_argument("--tenant-gpus-quota", type=int, default=16)
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_tenant_workspace)

    command = commands.add_parser(
        "GetTenantWorkspace",
        aliases=["get-tenant-workspace", "get"],
    )
    add_required(command, "--workspace-id")
    command.set_defaults(handler=handle_get_tenant_workspace)

    command = commands.add_parser(
        "ListTenantWorkspaces",
        aliases=["list-tenant-workspaces", "list"],
    )
    add_list_filters(command)
    command.set_defaults(handler=handle_list_tenant_workspaces)


def add_data_hub_commands(domains) -> None:
    data_hub = domains.add_parser(
        "DataHub",
        aliases=["data-hub", "datahub", "datasets"],
    )
    commands = data_hub.add_subparsers(dest="command", required=True)

    command = commands.add_parser("CreateDataset", aliases=["create-dataset"])
    add_required(command, "--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_dataset)

    command = commands.add_parser("ListDatasets", aliases=["list-datasets"])
    add_list_filters(command)
    command.set_defaults(handler=handle_list_datasets)

    command = commands.add_parser("GetDataset", aliases=["get-dataset"])
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handle_get_dataset)

    command = commands.add_parser("UpdateDataset", aliases=["update-dataset"])
    add_required(command, "--dataset-id")
    command.add_argument("--name")
    command.add_argument("--status")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_update_dataset)

    command = commands.add_parser("DeleteDataset", aliases=["delete-dataset"])
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handle_delete_dataset)

    command = commands.add_parser("ListDatasetFiles", aliases=["dataset-files"])
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handle_dataset_files)

    command = commands.add_parser("GetDatasetSize", aliases=["dataset-size"])
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handle_dataset_size)

    command = commands.add_parser(
        "UploadDatasetInstruction",
        aliases=["upload-dataset-instruction"],
    )
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handle_upload_dataset_instruction)

    command = commands.add_parser(
        "UploadDatasetCredential",
        aliases=["upload-dataset-credential"],
    )
    add_required(command, "--dataset-id")
    add_expires_arg(command)
    command.set_defaults(handler=handle_upload_dataset_credential)

    command = commands.add_parser(
        "DownloadDatasetCredential",
        aliases=["download-dataset-credential"],
    )
    add_required(command, "--dataset-id")
    add_expires_arg(command)
    command.set_defaults(handler=handle_download_dataset_credential)

    command = commands.add_parser("UploadDataset", aliases=["upload-dataset"])
    add_required(command, "--name")
    add_required(command, "--source-path")
    command.add_argument("--extras-json")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_upload_dataset)

    command = commands.add_parser("UploadToDataset", aliases=["upload-to-dataset"])
    add_required(command, "--dataset-id")
    add_required(command, "--source-path")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_upload_to_dataset)

    command = commands.add_parser("DownloadDataset", aliases=["download-dataset"])
    add_required(command, "--dataset-id")
    add_required(command, "--destination-path")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_download_dataset)


def add_model_registry_commands(domains) -> None:
    registry = domains.add_parser(
        "ModelRegistry",
        aliases=["model-registry", "models", "model"],
    )
    commands = registry.add_subparsers(dest="command", required=True)

    command = commands.add_parser("CreateModel", aliases=["create-model"])
    add_required(command, "--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_model)

    command = commands.add_parser("ListModels", aliases=["list-models"])
    add_list_filters(command)
    command.set_defaults(handler=handle_list_models)

    command = commands.add_parser("GetModel", aliases=["get-model"])
    add_required(command, "--model-id")
    command.set_defaults(handler=handle_get_model)

    command = commands.add_parser("UpdateModel", aliases=["update-model"])
    add_required(command, "--model-id")
    command.add_argument("--name")
    command.add_argument("--latest-version-id")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_update_model)

    command = commands.add_parser("DeleteModel", aliases=["delete-model"])
    add_required(command, "--model-id")
    command.set_defaults(handler=handle_delete_model)

    command = commands.add_parser(
        "CreateModelVersion",
        aliases=["create-model-version"],
    )
    add_required(command, "--model-id")
    add_required(command, "--name")
    command.add_argument("--training-experiment-name")
    command.add_argument("--training-run-name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_model_version)

    command = commands.add_parser(
        "CreateModelVersionFromCheckpoint",
        aliases=["create-model-version-from-checkpoint"],
    )
    add_required(command, "--model-id")
    add_required(command, "--name")
    add_required(command, "--experiment-id")
    add_required(command, "--run-id")
    add_required(command, "--checkpoint-name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_model_version_from_checkpoint)

    command = commands.add_parser(
        "ListModelVersions",
        aliases=["list-model-versions"],
    )
    add_required(command, "--model-id")
    add_list_filters(command)
    command.add_argument("--training-experiment-name")
    command.add_argument("--training-run-name")
    command.set_defaults(handler=handle_list_model_versions)

    command = commands.add_parser("GetModelVersion", aliases=["get-model-version"])
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handle_get_model_version)

    command = commands.add_parser(
        "UpdateModelVersion",
        aliases=["update-model-version"],
    )
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.add_argument("--name")
    command.add_argument("--status")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_update_model_version)

    command = commands.add_parser(
        "DeleteModelVersion",
        aliases=["delete-model-version"],
    )
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handle_delete_model_version)

    command = commands.add_parser(
        "ListModelVersionFiles",
        aliases=["model-version-files"],
    )
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handle_model_version_files)

    command = commands.add_parser(
        "GetModelVersionSize",
        aliases=["model-version-size"],
    )
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handle_model_version_size)

    command = commands.add_parser(
        "UploadModelVersionCredential",
        aliases=["upload-model-version-credential"],
    )
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    add_expires_arg(command)
    command.set_defaults(handler=handle_upload_model_version_credential)

    command = commands.add_parser(
        "DownloadModelVersionCredential",
        aliases=["download-model-version-credential"],
    )
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    add_expires_arg(command)
    command.set_defaults(handler=handle_download_model_version_credential)

    command = commands.add_parser(
        "UploadModelVersion",
        aliases=["upload-model-version"],
    )
    add_required(command, "--model-name")
    add_required(command, "--version-name")
    add_required(command, "--source-path")
    command.add_argument("--model-extras-json")
    command.add_argument("--version-extras-json")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_upload_model_version)

    command = commands.add_parser(
        "UploadModelVersionById",
        aliases=["upload-model-version-by-id"],
    )
    add_required(command, "--model-id")
    add_required(command, "--version-name")
    add_required(command, "--source-path")
    command.add_argument("--version-extras-json")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_upload_model_version_by_id)

    command = commands.add_parser(
        "UploadToModelVersion",
        aliases=["upload-to-model-version"],
    )
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    add_required(command, "--source-path")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_upload_to_model_version)

    command = commands.add_parser("DownloadModel", aliases=["download-model"])
    add_required(command, "--model-id")
    add_required(command, "--destination-path")
    command.add_argument("--model-version-id")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_download_model)

    command = commands.add_parser(
        "DownloadModelVersion",
        aliases=["download-model-version"],
    )
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    add_required(command, "--destination-path")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handle_download_model_version)


def add_training_commands(domains) -> None:
    training = domains.add_parser("Training", aliases=["training"])
    commands = training.add_subparsers(dest="command", required=True)

    command = commands.add_parser("CreateExperiment", aliases=["create-experiment"])
    add_required(command, "--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_experiment)

    command = commands.add_parser("ListExperiments", aliases=["list-experiments"])
    add_list_filters(command)
    command.set_defaults(handler=handle_list_experiments)

    command = commands.add_parser("GetExperiment", aliases=["get-experiment"])
    add_required(command, "--experiment-id")
    command.set_defaults(handler=handle_get_experiment)

    command = commands.add_parser("UpdateExperiment", aliases=["update-experiment"])
    add_required(command, "--experiment-id")
    command.add_argument("--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_update_experiment)

    command = commands.add_parser("DeleteExperiment", aliases=["delete-experiment"])
    add_required(command, "--experiment-id")
    command.set_defaults(handler=handle_delete_experiment)

    command = commands.add_parser("CreateRun", aliases=["create-run"])
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

    command = commands.add_parser("ListRuns", aliases=["list-runs"])
    add_required(command, "--experiment-id")
    add_list_filters(command)
    command.add_argument("--training-type")
    command.add_argument("--dataset-name")
    command.add_argument("--output-model-name")
    command.add_argument("--output-model-version-name")
    command.add_argument("--status")
    command.set_defaults(handler=handle_list_runs)

    command = commands.add_parser("GetRun", aliases=["get-run"])
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_get_run)

    command = commands.add_parser("StopRun", aliases=["stop-run"])
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_stop_run)

    command = commands.add_parser("CancelRun", aliases=["cancel-run"])
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_cancel_run)

    command = commands.add_parser("DeleteRun", aliases=["delete-run"])
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_delete_run)

    command = commands.add_parser("ResumeRun", aliases=["resume-run"])
    add_experiment_run_ids(command)
    command.add_argument("--checkpoint-name")
    command.add_argument("--hyperparameters-json")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_resume_run)

    command = commands.add_parser("GetRunLogs", aliases=["get-run-logs", "logs"])
    add_experiment_run_ids(command)
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handle_get_run_logs)

    command = commands.add_parser("GetRunMetrics", aliases=["get-run-metrics", "metrics"])
    add_experiment_run_ids(command)
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handle_get_run_metrics)

    command = commands.add_parser(
        "ListRunCheckpoints",
        aliases=["list-run-checkpoints", "checkpoints"],
    )
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_list_run_checkpoints)

    command = commands.add_parser(
        "CreateRunCheckpoint",
        aliases=["create-run-checkpoint"],
    )
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-name")
    command.set_defaults(handler=handle_create_run_checkpoint)

    command = commands.add_parser(
        "DeleteRunCheckpoints",
        aliases=["delete-run-checkpoints"],
    )
    add_experiment_run_ids(command)
    command.set_defaults(handler=handle_delete_run_checkpoints)

    command = commands.add_parser(
        "ListRunCheckpointFiles",
        aliases=["list-run-checkpoint-files", "checkpoint-files"],
    )
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-name")
    command.set_defaults(handler=handle_list_run_checkpoint_files)

    command = commands.add_parser(
        "DeleteRunCheckpoint",
        aliases=["delete-run-checkpoint"],
    )
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-name")
    command.set_defaults(handler=handle_delete_run_checkpoint)

    command = commands.add_parser(
        "UploadRunCheckpointCredential",
        aliases=["upload-run-checkpoint-credential"],
    )
    add_run_checkpoint_credential_args(command)
    command.set_defaults(handler=handle_upload_run_checkpoint_credential)

    command = commands.add_parser(
        "DownloadRunCheckpointCredential",
        aliases=["download-run-checkpoint-credential"],
    )
    add_run_checkpoint_credential_args(command)
    command.set_defaults(handler=handle_download_run_checkpoint_credential)


def add_inference_commands(domains) -> None:
    inference = domains.add_parser("Inference", aliases=["inference"])
    commands = inference.add_subparsers(dest="command", required=True)

    command = commands.add_parser(
        "CreateInferenceInstance",
        aliases=["create-inference-instance", "create"],
    )
    add_required(command, "--name")
    add_required(command, "--model-id")
    command.add_argument("--model-version-id")
    add_required(command, "--served-model-name")
    add_required(command, "--flavor")
    command.add_argument("--configuration-json")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handle_create_inference_instance)

    command = commands.add_parser(
        "ListInferenceInstances",
        aliases=["list-inference-instances", "list"],
    )
    add_list_filters(command)
    command.add_argument("--model-id")
    command.add_argument("--model-version-id")
    command.add_argument("--status")
    command.set_defaults(handler=handle_list_inference_instances)

    command = commands.add_parser(
        "GetInferenceInstance",
        aliases=["get-inference-instance", "get"],
    )
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_get_inference_instance)

    command = commands.add_parser(
        "UpdateInferenceInstance",
        aliases=["update-inference-instance", "update"],
    )
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

    command = commands.add_parser(
        "StopInferenceInstance",
        aliases=["stop-inference-instance", "stop"],
    )
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_stop_inference_instance)

    command = commands.add_parser(
        "RestartInferenceInstance",
        aliases=["restart-inference-instance", "restart"],
    )
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_restart_inference_instance)

    command = commands.add_parser(
        "FinalizeInferenceInstance",
        aliases=["finalize-inference-instance", "finalize"],
    )
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_finalize_inference_instance)

    command = commands.add_parser(
        "DeleteInferenceInstance",
        aliases=["delete-inference-instance", "delete"],
    )
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_delete_inference_instance)

    command = commands.add_parser(
        "GetInferenceInstanceEndpoint",
        aliases=["get-inference-instance-endpoint", "endpoint"],
    )
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handle_get_inference_instance_endpoint)

    command = commands.add_parser(
        "GetInferenceInstanceLogs",
        aliases=["get-inference-instance-logs", "logs"],
    )
    add_required(command, "--inference-instance-id")
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handle_get_inference_instance_logs)

    command = commands.add_parser(
        "GetInferenceInstanceMetrics",
        aliases=["get-inference-instance-metrics", "metrics"],
    )
    add_required(command, "--inference-instance-id")
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handle_get_inference_instance_metrics)


def add_required(command, *flags: str) -> None:
    command.add_argument(*flags, required=True)


def add_list_filters(command) -> None:
    command.add_argument("--name")
    command.add_argument("--page", type=int)
    command.add_argument("--limit", type=int)
    command.add_argument("--start-time")
    command.add_argument("--end-time")


def add_expires_arg(command) -> None:
    command.add_argument("--expires-in", type=int, default=3600)


def add_run_checkpoint_credential_args(command) -> None:
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-name")
    add_expires_arg(command)


def add_experiment_run_ids(command) -> None:
    add_required(command, "--experiment-id")
    add_required(command, "--run-id")


def handle_login(args):
    token = args.access_token or args.personal_token or prompt_token()
    api_url = args.url or args.base_url or load_api_url()
    cas_url = args.cas_url or load_cas_url()
    save_login(token=token, api_url=api_url, cas_url=cas_url)
    profile = token_profile(token)
    return {"logged_in": True, "api_url": api_url, "cas_url": cas_url, **profile}


def handle_logout(args):
    return {"logged_out": delete_token()}


def handle_whoami(args):
    token = load_token(args.access_token or args.personal_token)
    profile = token_profile(token) if token else {}
    return {
        "logged_in": bool(token),
        "token_source": "explicit_or_saved" if token else None,
        "api_url": load_api_url(args.base_url),
        "cas_url": load_cas_url(args.cas_url),
        **profile,
    }


def handle_create_tenant_workspace(client: OneNexusClient, args):
    return client.tenant_workspace.create_tenant_workspace(
        name=args.name,
        model_registry_bucket=args.model_registry_bucket,
        datahub_bucket=args.datahub_bucket,
        checkpoint_bucket=args.checkpoint_bucket,
        tokenizer_bucket=args.tokenizer_bucket,
        tenant_gpus_quota=args.tenant_gpus_quota,
        extras_data=parse_json(args.extras_json),
    )


def handle_get_tenant_workspace(client: OneNexusClient, args):
    return client.tenant_workspace.get_tenant_workspace(args.workspace_id)


def handle_list_tenant_workspaces(client: OneNexusClient, args):
    return client.tenant_workspace.list_tenant_workspaces(
        page=args.page,
        limit=args.limit,
        name=args.name,
        start_time=args.start_time,
        end_time=args.end_time,
    )


def handle_create_dataset(client: OneNexusClient, args):
    return client.data_hub.create_dataset(
        name=args.name,
        extras_data=parse_json(args.extras_json),
    )


def handle_list_datasets(client: OneNexusClient, args):
    return client.data_hub.list_datasets(
        page=args.page,
        limit=args.limit,
        name=args.name,
        start_time=args.start_time,
        end_time=args.end_time,
    )


def handle_get_dataset(client: OneNexusClient, args):
    return client.data_hub.get_dataset(args.dataset_id)


def handle_update_dataset(client: OneNexusClient, args):
    return client.data_hub.update_dataset(
        dataset_id=args.dataset_id,
        name=args.name,
        status=args.status,
        extras_data=parse_json(args.extras_json),
    )


def handle_delete_dataset(client: OneNexusClient, args):
    client.data_hub.delete_dataset(args.dataset_id)
    return None


def handle_dataset_files(client: OneNexusClient, args):
    return client.data_hub.list_dataset_files(args.dataset_id)


def handle_dataset_size(client: OneNexusClient, args):
    return client.data_hub.get_dataset_size(args.dataset_id)


def handle_upload_dataset_instruction(client: OneNexusClient, args):
    return client.data_hub.upload_dataset_instruction(args.dataset_id)


def handle_upload_dataset_credential(client: OneNexusClient, args):
    return client.data_hub.create_upload_credential(
        dataset_id=args.dataset_id,
        expires_in=args.expires_in,
    )


def handle_download_dataset_credential(client: OneNexusClient, args):
    return client.data_hub.create_download_credential(
        dataset_id=args.dataset_id,
        expires_in=args.expires_in,
    )


def handle_upload_dataset(client: OneNexusClient, args):
    return client.data_hub.upload_dataset(
        name=args.name,
        source_path=args.source_path,
        extras_data=parse_json(args.extras_json),
        expires_in=args.expires_in,
    )


def handle_upload_to_dataset(client: OneNexusClient, args):
    return client.data_hub.upload_to_dataset(
        dataset_id=args.dataset_id,
        source_path=args.source_path,
        expires_in=args.expires_in,
    )


def handle_download_dataset(client: OneNexusClient, args):
    return client.data_hub.download_dataset(
        dataset_id=args.dataset_id,
        destination_path=args.destination_path,
        expires_in=args.expires_in,
    )


def handle_create_model(client: OneNexusClient, args):
    return client.model_registry.create_model(
        name=args.name,
        extras_data=parse_json(args.extras_json),
    )


def handle_list_models(client: OneNexusClient, args):
    return client.model_registry.list_models(
        page=args.page,
        limit=args.limit,
        name=args.name,
        start_time=args.start_time,
        end_time=args.end_time,
    )


def handle_get_model(client: OneNexusClient, args):
    return client.model_registry.get_model(args.model_id)


def handle_update_model(client: OneNexusClient, args):
    return client.model_registry.update_model(
        model_id=args.model_id,
        name=args.name,
        latest_version_id=args.latest_version_id,
        extras_data=parse_json(args.extras_json),
    )


def handle_delete_model(client: OneNexusClient, args):
    client.model_registry.delete_model(args.model_id)
    return None


def handle_create_model_version(client: OneNexusClient, args):
    return client.model_registry.create_model_version(
        model_id=args.model_id,
        name=args.name,
        training_experiment_name=args.training_experiment_name,
        training_run_name=args.training_run_name,
        extras_data=parse_json(args.extras_json),
    )


def handle_create_model_version_from_checkpoint(client: OneNexusClient, args):
    return client.model_registry.create_model_version_from_checkpoint(
        model_id=args.model_id,
        name=args.name,
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        extras_data=parse_json(args.extras_json),
    )


def handle_list_model_versions(client: OneNexusClient, args):
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


def handle_get_model_version(client: OneNexusClient, args):
    return client.model_registry.get_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
    )


def handle_update_model_version(client: OneNexusClient, args):
    return client.model_registry.update_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        name=args.name,
        status=args.status,
        extras_data=parse_json(args.extras_json),
    )


def handle_delete_model_version(client: OneNexusClient, args):
    client.model_registry.delete_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
    )
    return None


def handle_model_version_files(client: OneNexusClient, args):
    return client.model_registry.list_model_version_files(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
    )


def handle_model_version_size(client: OneNexusClient, args):
    return client.model_registry.get_model_version_size(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
    )


def handle_upload_model_version_credential(
    client: OneNexusClient,
    args,
):
    return client.model_registry.create_upload_credential(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        expires_in=args.expires_in,
    )


def handle_download_model_version_credential(
    client: OneNexusClient,
    args,
):
    return client.model_registry.create_download_credential(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        expires_in=args.expires_in,
    )


def handle_upload_model_version(client: OneNexusClient, args):
    return client.model_registry.upload_model_version(
        model_name=args.model_name,
        version_name=args.version_name,
        source_path=args.source_path,
        model_extras_data=parse_json(args.model_extras_json),
        version_extras_data=parse_json(args.version_extras_json),
        expires_in=args.expires_in,
    )


def handle_upload_model_version_by_id(client: OneNexusClient, args):
    return client.model_registry.upload_model_version_by_id(
        model_id=args.model_id,
        version_name=args.version_name,
        source_path=args.source_path,
        version_extras_data=parse_json(args.version_extras_json),
        expires_in=args.expires_in,
    )


def handle_upload_to_model_version(client: OneNexusClient, args):
    return client.model_registry.upload_to_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        source_path=args.source_path,
        expires_in=args.expires_in,
    )


def handle_download_model(client: OneNexusClient, args):
    return client.model_registry.download_model(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        destination_path=args.destination_path,
        expires_in=args.expires_in,
    )


def handle_download_model_version(client: OneNexusClient, args):
    return client.model_registry.download_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        destination_path=args.destination_path,
        expires_in=args.expires_in,
    )


def handle_create_experiment(client: OneNexusClient, args):
    return client.training.create_experiment(
        name=args.name,
        extras_data=parse_json(args.extras_json),
    )


def handle_list_experiments(client: OneNexusClient, args):
    return client.training.list_experiments(
        page=args.page,
        limit=args.limit,
        name=args.name,
        start_time=args.start_time,
        end_time=args.end_time,
    )


def handle_get_experiment(client: OneNexusClient, args):
    return client.training.get_experiment(args.experiment_id)


def handle_update_experiment(client: OneNexusClient, args):
    return client.training.update_experiment(
        experiment_id=args.experiment_id,
        name=args.name,
        extras_data=parse_json(args.extras_json),
    )


def handle_delete_experiment(client: OneNexusClient, args):
    return client.training.delete_experiment(args.experiment_id)


def handle_create_run(client: OneNexusClient, args):
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


def handle_list_runs(client: OneNexusClient, args):
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


def handle_get_run(client: OneNexusClient, args):
    return client.training.get_run(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_stop_run(client: OneNexusClient, args):
    return client.training.stop_run(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_cancel_run(client: OneNexusClient, args):
    return client.training.cancel_run(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_delete_run(client: OneNexusClient, args):
    return client.training.delete_run(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_resume_run(client: OneNexusClient, args):
    return client.training.resume_run(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        hyperparameters=parse_json(args.hyperparameters_json),
        extras_data=parse_json(args.extras_json),
    )


def handle_get_run_logs(client: OneNexusClient, args):
    return client.training.get_run_logs(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        start_timestamp=args.start_timestamp,
        end_timestamp=args.end_timestamp,
    )


def handle_get_run_metrics(client: OneNexusClient, args):
    return client.training.get_run_metrics(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        start_timestamp=args.start_timestamp,
        end_timestamp=args.end_timestamp,
    )


def handle_list_run_checkpoints(client: OneNexusClient, args):
    return client.training.list_run_checkpoints(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_create_run_checkpoint(client: OneNexusClient, args):
    return client.training.create_run_checkpoint(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
    )


def handle_delete_run_checkpoints(client: OneNexusClient, args):
    return client.training.delete_run_checkpoints(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_list_run_checkpoint_files(client: OneNexusClient, args):
    return client.training.list_run_checkpoint_files(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
    )


def handle_delete_run_checkpoint(client: OneNexusClient, args):
    return client.training.delete_run_checkpoint(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
    )


def handle_upload_run_checkpoint_credential(client: OneNexusClient, args):
    return client.training.create_checkpoint_upload_credential(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        expires_in=args.expires_in,
    )


def handle_download_run_checkpoint_credential(client: OneNexusClient, args):
    return client.training.create_checkpoint_download_credential(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        expires_in=args.expires_in,
    )


def handle_create_inference_instance(client: OneNexusClient, args):
    return client.inference.create_inference_instance(
        name=args.name,
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        served_model_name=args.served_model_name,
        flavor=args.flavor,
        configuration=parse_json(args.configuration_json),
        extras_data=parse_json(args.extras_json),
    )


def handle_list_inference_instances(client: OneNexusClient, args):
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


def handle_get_inference_instance(client: OneNexusClient, args):
    return client.inference.get_inference_instance(args.inference_instance_id)


def handle_update_inference_instance(client: OneNexusClient, args):
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


def handle_stop_inference_instance(client: OneNexusClient, args):
    return client.inference.stop_inference_instance(args.inference_instance_id)


def handle_restart_inference_instance(client: OneNexusClient, args):
    return client.inference.restart_inference_instance(args.inference_instance_id)


def handle_finalize_inference_instance(client: OneNexusClient, args):
    return client.inference.finalize_inference_instance(args.inference_instance_id)


def handle_delete_inference_instance(client: OneNexusClient, args):
    return client.inference.delete_inference_instance(args.inference_instance_id)


def handle_get_inference_instance_endpoint(client: OneNexusClient, args):
    return client.inference.get_inference_instance_endpoint(
        args.inference_instance_id
    )


def handle_get_inference_instance_logs(client: OneNexusClient, args):
    return client.inference.get_inference_instance_logs(
        inference_instance_id=args.inference_instance_id,
        start_timestamp=args.start_timestamp,
        end_timestamp=args.end_timestamp,
    )


def handle_get_inference_instance_metrics(client: OneNexusClient, args):
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
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value
