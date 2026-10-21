from __future__ import annotations

import ast
import json
from dataclasses import fields
from pathlib import Path
from types import ModuleType

from nexusai import data_hub, inference, model_registry, platform_catalog
from nexusai import tenant_workspace, training
from nexusai.models import (
    DatasetDetail,
    DatasetSizeResult,
    DatasetSummary,
    ExperimentDetail,
    ExperimentSummary,
    FileItem,
    Flavor,
    InferenceConfiguration,
    InferenceActionResult,
    InferenceInstanceDetail,
    InferenceInstanceSummary,
    InferenceLogsResult,
    InferenceMetricsResult,
    ModelDetail,
    ModelSummary,
    ModelVersionDetail,
    ModelVersionSizeResult,
    ModelVersionSummary,
    RunCheckpoint,
    RunDetail,
    RunMonitoringResult,
    RunSummary,
    RunTokenizer,
    TenantWorkspaceDetail,
    TenantWorkspaceSummary,
    TrainingConfiguration,
    UploadInstruction,
    ActionResult,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
OPENAPI_PATH = REPOSITORY_ROOT / "specs" / "mlops" / "openapi.json"
PUBLIC_CLIENT_MODULES = (
    tenant_workspace,
    data_hub,
    model_registry,
    training,
    inference,
    platform_catalog,
)
PUBLIC_MODEL_SCHEMAS = {
    TenantWorkspaceSummary: "TenantWorkspaceSummaryResponse",
    TenantWorkspaceDetail: "TenantWorkspaceDetailResponse",
    DatasetSummary: "DatasetSummaryResponse",
    DatasetDetail: "DatasetDetailResponse",
    ModelSummary: "ModelSummaryResponse",
    ModelDetail: "ModelDetailResponse",
    ModelVersionSummary: "ModelVersionSummaryResponse",
    ModelVersionDetail: "ModelVersionDetailResponse",
    ExperimentSummary: "ExperimentSummaryResponse",
    ExperimentDetail: "ExperimentDetailResponse",
    RunSummary: "RunSummaryResponse",
    RunDetail: "RunDetailResponse",
    RunCheckpoint: "RunCheckpointPublicResponse",
    RunTokenizer: "RunTokenizerPublicResponse",
    InferenceInstanceSummary: "InferenceInstanceSummaryResponse",
    InferenceInstanceDetail: "InferenceInstanceDetailResponse",
    Flavor: "FlavorOptionResponse",
    TrainingConfiguration: "TrainingConfigurationOptionResponse",
    InferenceConfiguration: "InferenceConfigurationOptionResponse",
    FileItem: "DatasetFileResponse",
    UploadInstruction: "UploadDatasetInstructionResponse",
    ActionResult: "TrainingActionResponse",
    InferenceActionResult: "InferenceActionResponse",
    DatasetSizeResult: "DatasetSizeResponse",
    ModelVersionSizeResult: "ModelVersionSizeResponse",
    RunMonitoringResult: "RunLogsResponse",
    InferenceLogsResult: "InferenceLogsPublicResponse",
    InferenceMetricsResult: "InferenceMetricsPublicResponse",
}


def _openapi() -> dict:
    return json.loads(OPENAPI_PATH.read_text())


def _literal_rpc_paths(module: ModuleType) -> set[str]:
    source_path = Path(module.__file__ or "")
    tree = ast.parse(source_path.read_text())
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("/v1/")
    }


def test_public_client_rpc_paths_exist_in_committed_openapi() -> None:
    openapi_paths = set(_openapi()["paths"])
    client_paths = {
        f"/api{path}"
        for module in PUBLIC_CLIENT_MODULES
        for path in _literal_rpc_paths(module)
    }
    dynamic_prefixes = {path for path in client_paths if path.endswith("/")}
    exact_paths = client_paths - dynamic_prefixes

    assert client_paths
    assert exact_paths <= openapi_paths
    assert all(
        any(path.startswith(prefix) for path in openapi_paths)
        for prefix in dynamic_prefixes
    )


def test_public_sdk_models_match_backend_schema_fields() -> None:
    schemas = _openapi()["components"]["schemas"]

    for model, schema_name in PUBLIC_MODEL_SCHEMAS.items():
        assert {field.name for field in fields(model)} == set(
            schemas[schema_name]["properties"]
        )


def test_committed_openapi_excludes_internal_contracts() -> None:
    spec = _openapi()
    paths = set(spec["paths"])
    schema_names = set(spec["components"]["schemas"])

    assert not any("/workload/" in path for path in paths)
    assert not any("/protected/" in path for path in paths)
    assert not any(
        marker in schema_name.lower()
        for schema_name in schema_names
        for marker in (
            "execution",
            "uploadsession",
            "checkpointprocess",
            "transfertarget",
        )
    )


def test_create_run_openapi_does_not_expose_internal_storage_paths() -> None:
    properties = _openapi()["components"]["schemas"]["RpcCreateRunRequest"][
        "properties"
    ]

    assert "checkpoint_path" not in properties
    assert "tokenizer_path" not in properties
    assert "output_model" in properties
    assert "output_model_name" not in properties
    assert "output_model_version_name" not in properties

    output_schema = properties["output_model"]["anyOf"][0]
    assert output_schema["discriminator"]["propertyName"] == "type"
    assert {item["$ref"].rsplit("/", 1)[-1] for item in output_schema["oneOf"]} == {
        "NewRunOutputModelRequest",
        "ExistingRunOutputModelRequest",
    }
