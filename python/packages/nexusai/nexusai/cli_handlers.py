from __future__ import annotations

import argparse
import json
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
from .client import OneNexusClient
from .config import CAS_BASE_URL, PLATFORM_BASE_URL
from .models import ExistingRunOutputModel, NewRunOutputModel, RunOutputModel


def handle_login(args: argparse.Namespace) -> Any:
    token = args.token or prompt_token()
    api_url = args.url or args.base_url or PLATFORM_BASE_URL
    cas_url = args.cas_url or CAS_BASE_URL
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


def handle_create_tenant_workspace(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.tenant_workspace.create_tenant_workspace(
        name=args.name,
        model_registry_bucket=args.model_registry_bucket,
        datahub_bucket=args.datahub_bucket,
        checkpoint_bucket=args.checkpoint_bucket,
        tokenizer_bucket=args.tokenizer_bucket,
        extras_data=parse_json(args.extras_json),
    )


def handle_get_tenant_workspace(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.tenant_workspace.get_tenant_workspace(args.workspace_id)


def handle_list_tenant_workspaces(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
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
    return client.data_hub.delete_dataset(args.dataset_id)


def handle_start_dataset_upload(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.data_hub.start_dataset_upload(
        dataset_id=args.dataset_id,
        idempotency_key=args.idempotency_key,
    )


def handle_finalize_dataset_upload(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.data_hub.finalize_dataset_upload(
        dataset_id=args.dataset_id,
    )


def handle_fail_dataset_upload(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.fail_dataset_upload(
        dataset_id=args.dataset_id,
        failure_reason=args.failure_reason,
    )


def handle_cancel_dataset_upload(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.data_hub.cancel_dataset_upload(
        dataset_id=args.dataset_id,
        cancel_reason=args.cancel_reason,
    )


def handle_dataset_files(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.list_dataset_files(args.dataset_id)


def handle_dataset_size(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.data_hub.get_dataset_size(args.dataset_id)


def handle_upload_dataset_instruction(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
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
    return client.model_registry.delete_model(args.model_id)


def handle_create_model_version(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.model_registry.create_model_version(
        model_id=args.model_id,
        name=args.name,
        training_experiment_name=args.training_experiment_name,
        training_run_name=args.training_run_name,
        extras_data=parse_json(args.extras_json),
    )


def handle_create_model_version_from_checkpoint(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
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


def handle_update_model_version(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.model_registry.update_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        name=args.name,
        extras_data=parse_json(args.extras_json),
    )


def handle_delete_model_version(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.model_registry.delete_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
    )


def handle_start_model_version_upload(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.model_registry.start_model_version_upload(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        idempotency_key=args.idempotency_key,
    )


def handle_finalize_model_version_upload(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.model_registry.finalize_model_version_upload(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        artifact_format=args.artifact_format,
    )


def handle_fail_model_version_upload(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.model_registry.fail_model_version_upload(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        failure_reason=args.failure_reason,
        failure_message=args.failure_message,
    )


def handle_cancel_model_version_upload(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
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


def handle_upload_model_version(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.model_registry.upload_model_version(
        model_name=args.model_name,
        version_name=args.version_name,
        source_path=args.source_path,
        model_extras_data=parse_json(args.model_extras_json),
        version_extras_data=parse_json(args.version_extras_json),
        expires_in=args.expires_in,
        artifact_format=args.artifact_format,
        model_architecture=args.model_architecture,
        runtime=args.runtime,
        accelerators=tuple(args.accelerator or ("amd",)),
    )


def handle_upload_model_version_by_id(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.model_registry.upload_model_version_by_id(
        model_id=args.model_id,
        version_name=args.version_name,
        source_path=args.source_path,
        version_extras_data=parse_json(args.version_extras_json),
        expires_in=args.expires_in,
        artifact_format=args.artifact_format,
        model_architecture=args.model_architecture,
        runtime=args.runtime,
        accelerators=tuple(args.accelerator or ("amd",)),
    )


def handle_upload_to_model_version(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.model_registry.upload_to_model_version(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        source_path=args.source_path,
        expires_in=args.expires_in,
        artifact_format=args.artifact_format,
        model_architecture=args.model_architecture,
        runtime=args.runtime,
        accelerators=tuple(args.accelerator or ("amd",)),
    )


def handle_download_model(client: OneNexusClient, args: argparse.Namespace) -> Any:
    return client.model_registry.download_model(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        destination_path=args.destination_path,
        expires_in=args.expires_in,
    )


def handle_download_model_version(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
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
    output_model = _create_run_output_model(args)
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
        output_model=output_model,
        extras_data=parse_json(args.extras_json),
    )


def _create_run_output_model(args: argparse.Namespace) -> RunOutputModel | None:
    output_type = args.output_model_type
    model_name = args.output_model_name
    model_id = args.output_model_id
    version_name = args.output_model_version_name
    if output_type is None:
        if any((model_name, model_id, version_name)):
            raise ValueError(
                "--output-model-type is required when configuring an output model"
            )
        return None
    if not version_name:
        raise ValueError("--output-model-version-name is required")
    if output_type == "new":
        if not model_name or model_id:
            raise ValueError(
                "new output models require --output-model-name and do not accept "
                "--output-model-id"
            )
        return NewRunOutputModel(
            model_name=model_name,
            model_version_name=version_name,
        )
    if not model_id or model_name:
        raise ValueError(
            "existing output models require --output-model-id and do not accept "
            "--output-model-name"
        )
    return ExistingRunOutputModel(
        model_id=model_id,
        model_version_name=version_name,
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


def handle_list_run_checkpoints(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
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


def handle_upload_to_checkpoint(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.training.upload_to_checkpoint(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
        source_path=args.source_path,
        checkpoint_step=args.checkpoint_step,
        idempotency_key=args.idempotency_key,
    )


def handle_delete_run_checkpoints(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.training.delete_run_checkpoints(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_list_run_checkpoint_files(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.training.list_run_checkpoint_files(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        checkpoint_name=args.checkpoint_name,
    )


def handle_delete_run_checkpoint(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
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


def handle_upload_to_run_tokenizer(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.training.upload_to_run_tokenizer(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        source_path=args.source_path,
    )


def handle_delete_run_tokenizer(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.training.delete_run_tokenizer(
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )


def handle_create_inference_instance(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.inference.create_inference_instance(
        name=args.name,
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        served_model_name=args.served_model_name,
        flavor=args.flavor,
        configuration=parse_json(args.configuration_json),
        extras_data=parse_json(args.extras_json),
    )


def handle_list_inference_instances(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
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


def handle_get_inference_instance(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.inference.get_inference_instance(args.inference_instance_id)


def handle_update_inference_instance(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
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


def handle_stop_inference_instance(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.inference.stop_inference_instance(args.inference_instance_id)


def handle_restart_inference_instance(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.inference.restart_inference_instance(args.inference_instance_id)


def handle_finalize_inference_instance(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.inference.finalize_inference_instance(args.inference_instance_id)


def handle_delete_inference_instance(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.inference.delete_inference_instance(args.inference_instance_id)


def handle_get_inference_instance_endpoint(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.inference.get_inference_instance_endpoint(args.inference_instance_id)


def handle_get_inference_instance_logs(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
    return client.inference.get_inference_instance_logs(
        inference_instance_id=args.inference_instance_id,
        start_timestamp=args.start_timestamp,
        end_timestamp=args.end_timestamp,
    )


def handle_get_inference_instance_metrics(
    client: OneNexusClient, args: argparse.Namespace
) -> Any:
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
