from __future__ import annotations

import argparse

from . import cli_handlers as handlers


def add_auth_commands(
    domains: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    login = domains.add_parser("login")
    login.add_argument("--token", help="Token to save. Prompts if omitted.")
    login.add_argument(
        "--url",
        help="Platform URL to save. Defaults to https://ai-api-v3.ric1.onenexus-do.cloud.",
    )
    login.add_argument(
        "--cas-url",
        help="CAS URL to save. Defaults to https://auth.onenexus-do.cloud.",
    )
    login.set_defaults(auth_command=True, handler=handlers.handle_login)

    logout = domains.add_parser("logout")
    logout.set_defaults(auth_command=True, handler=handlers.handle_logout)

    whoami = domains.add_parser("whoami")
    whoami.set_defaults(auth_command=True, handler=handlers.handle_whoami)


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
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_create_tenant_workspace)

    command = commands.add_parser("GetTenantWorkspace")
    add_required(command, "--workspace-id")
    command.set_defaults(handler=handlers.handle_get_tenant_workspace)

    command = commands.add_parser("ListTenantWorkspaces")
    add_list_filters(command)
    command.set_defaults(handler=handlers.handle_list_tenant_workspaces)


def add_data_hub_commands(
    domains: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    data_hub = domains.add_parser("DataHub")
    commands = data_hub.add_subparsers(dest="command", required=True)

    command = commands.add_parser("CreateDataset")
    add_required(command, "--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_create_dataset)

    command = commands.add_parser("ListDatasets")
    add_list_filters(command)
    command.set_defaults(handler=handlers.handle_list_datasets)

    command = commands.add_parser("GetDataset")
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handlers.handle_get_dataset)

    command = commands.add_parser("UpdateDataset")
    add_required(command, "--dataset-id")
    command.add_argument("--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_update_dataset)

    command = commands.add_parser("DeleteDataset")
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handlers.handle_delete_dataset)

    command = commands.add_parser("StartDatasetUpload")
    add_required(command, "--dataset-id")
    command.add_argument("--idempotency-key")
    command.set_defaults(handler=handlers.handle_start_dataset_upload)

    command = commands.add_parser("FinalizeDatasetUpload")
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handlers.handle_finalize_dataset_upload)

    command = commands.add_parser("FailDatasetUpload")
    add_required(command, "--dataset-id")
    add_required(command, "--failure-reason")
    command.set_defaults(handler=handlers.handle_fail_dataset_upload)

    command = commands.add_parser("CancelDatasetUpload")
    add_required(command, "--dataset-id")
    command.add_argument("--cancel-reason")
    command.set_defaults(handler=handlers.handle_cancel_dataset_upload)

    command = commands.add_parser("ListDatasetFiles")
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handlers.handle_dataset_files)

    command = commands.add_parser("GetDatasetSize")
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handlers.handle_dataset_size)

    command = commands.add_parser("GetUploadDatasetInstruction")
    add_required(command, "--dataset-id")
    command.set_defaults(handler=handlers.handle_upload_dataset_instruction)

    command = commands.add_parser("UploadDataset")
    add_required(command, "--name")
    add_required(command, "--source-path")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_upload_dataset)

    command = commands.add_parser("UploadToDataset")
    add_required(command, "--dataset-id")
    add_required(command, "--source-path")
    command.set_defaults(handler=handlers.handle_upload_to_dataset)

    command = commands.add_parser("DownloadDataset")
    add_required(command, "--dataset-id")
    add_required(command, "--destination-path")
    command.set_defaults(handler=handlers.handle_download_dataset)


def add_model_registry_commands(
    domains: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    registry = domains.add_parser("ModelRegistry")
    commands = registry.add_subparsers(dest="command", required=True)

    command = commands.add_parser("CreateModel")
    add_required(command, "--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_create_model)

    command = commands.add_parser("ListModels")
    add_list_filters(command)
    command.set_defaults(handler=handlers.handle_list_models)

    command = commands.add_parser("GetModel")
    add_required(command, "--model-id")
    command.set_defaults(handler=handlers.handle_get_model)

    command = commands.add_parser("UpdateModel")
    add_required(command, "--model-id")
    command.add_argument("--name")
    command.add_argument("--latest-version-id")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_update_model)

    command = commands.add_parser("DeleteModel")
    add_required(command, "--model-id")
    command.set_defaults(handler=handlers.handle_delete_model)

    command = commands.add_parser("CreateModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--name")
    command.add_argument("--training-experiment-name")
    command.add_argument("--training-run-name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_create_model_version)

    command = commands.add_parser("CreateModelVersionFromCheckpoint")
    add_required(command, "--model-id")
    add_required(command, "--name")
    add_required(command, "--experiment-id")
    add_required(command, "--run-id")
    add_required(command, "--checkpoint-name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_create_model_version_from_checkpoint)

    command = commands.add_parser("ListModelVersions")
    add_required(command, "--model-id")
    add_list_filters(command)
    command.add_argument("--training-experiment-name")
    command.add_argument("--training-run-name")
    command.set_defaults(handler=handlers.handle_list_model_versions)

    command = commands.add_parser("GetModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handlers.handle_get_model_version)

    command = commands.add_parser("UpdateModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.add_argument("--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_update_model_version)

    command = commands.add_parser("DeleteModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handlers.handle_delete_model_version)

    command = commands.add_parser("StartModelVersionUpload")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.add_argument("--idempotency-key")
    command.set_defaults(handler=handlers.handle_start_model_version_upload)

    command = commands.add_parser("FinalizeModelVersionUpload")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.add_argument("--artifact-format")
    command.set_defaults(handler=handlers.handle_finalize_model_version_upload)

    command = commands.add_parser("FailModelVersionUpload")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.add_argument("--failure-reason")
    command.add_argument("--failure-message")
    command.set_defaults(handler=handlers.handle_fail_model_version_upload)

    command = commands.add_parser("CancelModelVersionUpload")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.add_argument("--failure-reason")
    command.add_argument("--failure-message")
    command.set_defaults(handler=handlers.handle_cancel_model_version_upload)

    command = commands.add_parser("ListModelVersionFiles")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handlers.handle_model_version_files)

    command = commands.add_parser("GetModelVersionSize")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    command.set_defaults(handler=handlers.handle_model_version_size)

    command = commands.add_parser("UploadModelVersion")
    add_required(command, "--model-name")
    add_required(command, "--version-name")
    add_required(command, "--source-path")
    command.add_argument("--model-extras-json")
    command.add_argument("--version-extras-json")
    command.add_argument("--expires-in", type=int, default=3600)
    _add_serving_manifest_options(command)
    command.set_defaults(handler=handlers.handle_upload_model_version)

    command = commands.add_parser("UploadModelVersionById")
    add_required(command, "--model-id")
    add_required(command, "--version-name")
    add_required(command, "--source-path")
    command.add_argument("--version-extras-json")
    command.add_argument("--expires-in", type=int, default=3600)
    _add_serving_manifest_options(command)
    command.set_defaults(handler=handlers.handle_upload_model_version_by_id)

    command = commands.add_parser("UploadToModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    add_required(command, "--source-path")
    command.add_argument("--expires-in", type=int, default=3600)
    _add_serving_manifest_options(command)
    command.set_defaults(handler=handlers.handle_upload_to_model_version)

    command = commands.add_parser("DownloadModel")
    add_required(command, "--model-id")
    add_required(command, "--destination-path")
    command.add_argument("--model-version-id")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handlers.handle_download_model)

    command = commands.add_parser("DownloadModelVersion")
    add_required(command, "--model-id")
    add_required(command, "--model-version-id")
    add_required(command, "--destination-path")
    command.add_argument("--expires-in", type=int, default=3600)
    command.set_defaults(handler=handlers.handle_download_model_version)


def add_training_commands(
    domains: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    training = domains.add_parser("Training")
    commands = training.add_subparsers(dest="command", required=True)

    command = commands.add_parser("CreateExperiment")
    add_required(command, "--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_create_experiment)

    command = commands.add_parser("ListExperiments")
    add_list_filters(command)
    command.set_defaults(handler=handlers.handle_list_experiments)

    command = commands.add_parser("GetExperiment")
    add_required(command, "--experiment-id")
    command.set_defaults(handler=handlers.handle_get_experiment)

    command = commands.add_parser("UpdateExperiment")
    add_required(command, "--experiment-id")
    command.add_argument("--name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_update_experiment)

    command = commands.add_parser("DeleteExperiment")
    add_required(command, "--experiment-id")
    command.set_defaults(handler=handlers.handle_delete_experiment)

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
    command.add_argument("--output-model-type", choices=("new", "existing"))
    command.add_argument("--output-model-name")
    command.add_argument("--output-model-id")
    command.add_argument("--output-model-version-name")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_create_run)

    command = commands.add_parser("ListRuns")
    add_required(command, "--experiment-id")
    add_list_filters(command)
    command.add_argument("--training-type")
    command.add_argument("--dataset-name")
    command.add_argument("--output-model-name")
    command.add_argument("--output-model-version-name")
    command.add_argument("--status")
    command.set_defaults(handler=handlers.handle_list_runs)

    command = commands.add_parser("GetRun")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handlers.handle_get_run)

    command = commands.add_parser("StopRun")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handlers.handle_stop_run)

    command = commands.add_parser("CancelRun")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handlers.handle_cancel_run)

    command = commands.add_parser("DeleteRun")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handlers.handle_delete_run)

    command = commands.add_parser("ResumeRun")
    add_experiment_run_ids(command)
    command.add_argument("--checkpoint-name")
    command.add_argument("--hyperparameters-json")
    command.add_argument("--extras-json")
    command.set_defaults(handler=handlers.handle_resume_run)

    command = commands.add_parser("GetRunLogs")
    add_experiment_run_ids(command)
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handlers.handle_get_run_logs)

    command = commands.add_parser("GetRunMetrics")
    add_experiment_run_ids(command)
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handlers.handle_get_run_metrics)

    command = commands.add_parser("ListRunCheckpoints")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handlers.handle_list_run_checkpoints)

    command = commands.add_parser("GetRunCheckpoint")
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-id")
    command.set_defaults(handler=handlers.handle_get_run_checkpoint)

    command = commands.add_parser("UploadToCheckpoint")
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-name")
    add_required(command, "--source-path")
    command.add_argument("--checkpoint-step", type=int)
    command.add_argument("--idempotency-key")
    command.set_defaults(handler=handlers.handle_upload_to_checkpoint)

    command = commands.add_parser("DeleteRunCheckpoints")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handlers.handle_delete_run_checkpoints)

    command = commands.add_parser("ListRunCheckpointFiles")
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-name")
    command.set_defaults(handler=handlers.handle_list_run_checkpoint_files)

    command = commands.add_parser("DeleteRunCheckpoint")
    add_experiment_run_ids(command)
    add_required(command, "--checkpoint-name")
    command.set_defaults(handler=handlers.handle_delete_run_checkpoint)

    command = commands.add_parser("GetRunTokenizer")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handlers.handle_get_run_tokenizer)

    command = commands.add_parser("UploadToRunTokenizer")
    add_experiment_run_ids(command)
    add_required(command, "--source-path")
    command.set_defaults(handler=handlers.handle_upload_to_run_tokenizer)

    command = commands.add_parser("DeleteRunTokenizer")
    add_experiment_run_ids(command)
    command.set_defaults(handler=handlers.handle_delete_run_tokenizer)


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
    command.set_defaults(handler=handlers.handle_create_inference_instance)

    command = commands.add_parser("ListInferenceInstances")
    add_list_filters(command)
    command.add_argument("--model-id")
    command.add_argument("--model-version-id")
    command.add_argument("--status")
    command.set_defaults(handler=handlers.handle_list_inference_instances)

    command = commands.add_parser("GetInferenceInstance")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handlers.handle_get_inference_instance)

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
    command.set_defaults(handler=handlers.handle_update_inference_instance)

    command = commands.add_parser("StopInferenceInstance")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handlers.handle_stop_inference_instance)

    command = commands.add_parser("RestartInferenceInstance")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handlers.handle_restart_inference_instance)

    command = commands.add_parser("FinalizeInferenceInstance")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handlers.handle_finalize_inference_instance)

    command = commands.add_parser("DeleteInferenceInstance")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handlers.handle_delete_inference_instance)

    command = commands.add_parser("GetInferenceInstanceEndpoint")
    add_required(command, "--inference-instance-id")
    command.set_defaults(handler=handlers.handle_get_inference_instance_endpoint)

    command = commands.add_parser("GetInferenceInstanceLogs")
    add_required(command, "--inference-instance-id")
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handlers.handle_get_inference_instance_logs)

    command = commands.add_parser("GetInferenceInstanceMetrics")
    add_required(command, "--inference-instance-id")
    command.add_argument("--start-timestamp")
    command.add_argument("--end-timestamp")
    command.set_defaults(handler=handlers.handle_get_inference_instance_metrics)


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


def _add_serving_manifest_options(command: argparse.ArgumentParser) -> None:
    command.add_argument("--artifact-format")
    command.add_argument("--model-architecture")
    command.add_argument("--runtime", default="sglang")
    command.add_argument("--accelerator", action="append")


def add_experiment_run_ids(command: argparse.ArgumentParser) -> None:
    add_required(command, "--experiment-id")
    add_required(command, "--run-id")
