from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from collections.abc import Iterator
from typing import Any, Generic, Mapping, Optional, TypeVar, cast


ModelT = TypeVar("ModelT", bound="APIModel")
ItemT = TypeVar("ItemT")


class APIModel:
    @classmethod
    def from_dict(cls: type[ModelT], payload: Mapping[str, Any]) -> ModelT:
        accepted = {field.name for field in fields(cast(Any, cls))}
        return cls(**{key: value for key, value in payload.items() if key in accepted})

    def to_dict(self) -> dict[str, Any]:
        return asdict(cast(Any, self))

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass(frozen=True)
class Page(Generic[ItemT]):
    items: list[ItemT]
    total_pages: Optional[int] = None
    code: Optional[str] = None
    message: Optional[str] = None
    request_id: Optional[str] = None

    def __iter__(self) -> Iterator[ItemT]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> ItemT:
        return self.items[index]


@dataclass(frozen=True)
class ResourceReference(APIModel):
    id: str
    name: Optional[str] = None


@dataclass(frozen=True)
class ActionResult(APIModel):
    resource_id: str
    status: str
    status_message: str


@dataclass(frozen=True)
class InferenceActionResult(ActionResult):
    endpoint: Optional[str] = None


@dataclass(frozen=True)
class FileItem(APIModel):
    file_path: str
    size_bytes: int


@dataclass(frozen=True)
class DatasetSizeResult(APIModel):
    dataset_id: str
    object_count: int
    size_bytes: int
    size: str


@dataclass(frozen=True)
class ModelVersionSizeResult(APIModel):
    model_id: str
    model_version_id: str
    object_count: int
    size_bytes: int
    size: str


@dataclass(frozen=True)
class UploadInstruction(APIModel):
    dataset_id: str
    dataset_name: str
    instruction_markdown: str


@dataclass(frozen=True)
class TenantWorkspaceSummary(APIModel):
    id: str
    name: str
    tenant_gpus_quota: int
    num_models: int
    num_model_versions: int
    num_datasets: int
    num_experiments: int
    num_experiment_runs: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TenantWorkspaceDetail(TenantWorkspaceSummary):
    extras_data: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class DatasetSummary(APIModel):
    id: str
    name: str
    status: str
    status_message: str
    file_count: int
    total_size_bytes: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class DatasetDetail(DatasetSummary):
    extras_data: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class ModelVersionReference(APIModel):
    id: str
    name: Optional[str] = None
    status: Optional[str] = None


@dataclass(frozen=True)
class ModelSummary(APIModel):
    id: str
    name: str
    status: str
    status_message: str
    version_count: int
    created_at: str
    updated_at: str
    latest_version: Optional[ModelVersionReference] = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ModelSummary:
        data = dict(payload)
        latest = data.get("latest_version")
        data["latest_version"] = (
            ModelVersionReference.from_dict(latest)
            if isinstance(latest, Mapping)
            else None
        )
        return super().from_dict(data)


@dataclass(frozen=True)
class ModelDetail(ModelSummary):
    extras_data: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class ModelVersionSource(APIModel):
    type: str
    experiment_id: Optional[str] = None
    experiment_name: Optional[str] = None
    run_id: Optional[str] = None
    run_name: Optional[str] = None


@dataclass(frozen=True)
class ModelVersionSummary(APIModel):
    id: str
    model_id: str
    name: str
    status: str
    status_message: str
    file_count: int
    total_size_bytes: int
    created_at: str
    updated_at: str
    artifact_format: Optional[str] = None
    finalized_at: Optional[str] = None


@dataclass(frozen=True)
class ModelVersionDetail(ModelVersionSummary):
    source: Optional[ModelVersionSource] = None
    extras_data: Optional[dict[str, Any]] = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ModelVersionDetail:
        data = dict(payload)
        source = data.get("source")
        data["source"] = (
            ModelVersionSource.from_dict(source)
            if isinstance(source, Mapping)
            else None
        )
        return super().from_dict(data)


@dataclass(frozen=True)
class ModelSource(APIModel):
    source: str
    huggingface_id: Optional[str] = None
    model: Optional[ResourceReference] = None
    model_version: Optional[ResourceReference] = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ModelSource:
        data = dict(payload)
        for key in ("model", "model_version"):
            value = data.get(key)
            data[key] = (
                ResourceReference.from_dict(value)
                if isinstance(value, Mapping)
                else None
            )
        return super().from_dict(data)


@dataclass(frozen=True)
class ExperimentSummary(APIModel):
    id: str
    name: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ExperimentDetail(ExperimentSummary):
    extras_data: Optional[dict[str, Any]] = None


def _require_non_empty_name(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


@dataclass(frozen=True)
class NewRunOutputModel:
    model_name: str
    model_version_name: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "model_name",
            _require_non_empty_name(self.model_name, "model_name"),
        )
        object.__setattr__(
            self,
            "model_version_name",
            _require_non_empty_name(
                self.model_version_name,
                "model_version_name",
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "type": "new",
            "model_name": self.model_name,
            "model_version_name": self.model_version_name,
        }


@dataclass(frozen=True)
class ExistingRunOutputModel:
    model_id: str
    model_version_name: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "model_id",
            _require_non_empty_name(self.model_id, "model_id"),
        )
        object.__setattr__(
            self,
            "model_version_name",
            _require_non_empty_name(
                self.model_version_name,
                "model_version_name",
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "type": "existing",
            "model_id": self.model_id,
            "model_version_name": self.model_version_name,
        }


RunOutputModel = NewRunOutputModel | ExistingRunOutputModel


@dataclass(frozen=True)
class RunSummary(APIModel):
    id: str
    name: str
    experiment: ResourceReference
    dataset: ResourceReference
    input_model: ModelSource
    training_type: str
    flavor: str
    status: str
    status_message: str
    created_at: str
    updated_at: str
    step: Optional[str] = None
    attempt: Optional[int] = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RunSummary:
        data = dict(payload)
        data["experiment"] = ResourceReference.from_dict(data["experiment"])
        data["dataset"] = ResourceReference.from_dict(data["dataset"])
        data["input_model"] = ModelSource.from_dict(data["input_model"])
        return super().from_dict(data)


@dataclass(frozen=True)
class RunDetail(RunSummary):
    hyperparameters: Optional[dict[str, Any]] = None
    checkpoint_count: int = 0
    output_model: Optional[ResourceReference] = None
    output_model_version: Optional[ResourceReference] = None
    extras_data: Optional[dict[str, Any]] = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RunDetail:
        data = dict(payload)
        data["experiment"] = ResourceReference.from_dict(data["experiment"])
        data["dataset"] = ResourceReference.from_dict(data["dataset"])
        data["input_model"] = ModelSource.from_dict(data["input_model"])
        for key in ("output_model", "output_model_version"):
            value = data.get(key)
            data[key] = (
                ResourceReference.from_dict(value)
                if isinstance(value, Mapping)
                else None
            )
        return super(RunSummary, cls).from_dict(data)


@dataclass(frozen=True)
class MonitoringOverview(APIModel):
    is_live: bool
    available: bool
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


@dataclass(frozen=True)
class RunMonitoringOverview(MonitoringOverview):
    attempt_count: Optional[int] = None
    iframe_url: Optional[str] = None
    model_metrics_iframe_url: Optional[str] = None
    system_metrics_iframe_url: Optional[str] = None


@dataclass(frozen=True)
class InferenceMonitoringOverview(MonitoringOverview):
    iframe_url: Optional[str] = None


@dataclass(frozen=True)
class MonitoringAttempt(APIModel):
    attempt: int
    status: str
    status_message: str
    started_at: str
    is_live: bool
    available: bool
    ended_at: Optional[str] = None


@dataclass(frozen=True)
class RunMonitoringAttempt(MonitoringAttempt):
    iframe_url: Optional[str] = None
    model_metrics_iframe_url: Optional[str] = None
    system_metrics_iframe_url: Optional[str] = None


@dataclass(frozen=True)
class InferenceMonitoringAttempt(MonitoringAttempt):
    iframe_url: Optional[str] = None


@dataclass(frozen=True)
class RunMonitoringResult(APIModel):
    run_id: str
    run_name: str
    overview: RunMonitoringOverview
    attempts: list[RunMonitoringAttempt]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RunMonitoringResult:
        data = dict(payload)
        data["overview"] = RunMonitoringOverview.from_dict(data["overview"])
        data["attempts"] = [
            RunMonitoringAttempt.from_dict(item) for item in data.get("attempts", [])
        ]
        return super().from_dict(data)


@dataclass(frozen=True)
class InferenceMonitoringResult(APIModel):
    inference_instance_id: str
    overview: InferenceMonitoringOverview
    attempts: list[InferenceMonitoringAttempt]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> InferenceMonitoringResult:
        data = dict(payload)
        data["overview"] = InferenceMonitoringOverview.from_dict(data["overview"])
        data["attempts"] = [
            InferenceMonitoringAttempt.from_dict(item)
            for item in data.get("attempts", [])
        ]
        return super().from_dict(data)


# Kept as the concise public name for training-run monitoring.
MonitoringResult = RunMonitoringResult


@dataclass(frozen=True)
class RunCheckpoint(APIModel):
    id: str
    name: str
    status: str
    status_message: str
    file_count: int
    size_bytes: int
    step: Optional[int] = None
    source_attempt: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class RunTokenizer(APIModel):
    id: str
    status: str
    status_message: str
    file_count: int
    size_bytes: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class InferenceInstanceSummary(APIModel):
    id: str
    name: str
    model: ModelSource
    served_model_name: str
    flavor: str
    status: str
    status_message: str
    created_at: str
    updated_at: str
    endpoint: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> InferenceInstanceSummary:
        data = dict(payload)
        data["model"] = ModelSource.from_dict(data["model"])
        return super().from_dict(data)


@dataclass(frozen=True)
class InferenceInstanceDetail(InferenceInstanceSummary):
    configuration: Optional[dict[str, Any]] = None
    extras_data: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class InferenceEndpoint(APIModel):
    resource_id: str
    name: str
    status: str
    status_message: str
    endpoint: Optional[str] = None
    sample_curl: Optional[str] = None


@dataclass(frozen=True)
class Flavor(APIModel):
    id: str
    name: str
    gpus: int
    cpus: str
    memory: str
    nodes: int
    rdma: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TrainingConfiguration(APIModel):
    id: str
    training_type: str
    default_hyperparameters: dict[str, Any]
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class InferenceConfiguration(APIModel):
    id: str
    runtime: str
    default_configuration: dict[str, Any]
    created_at: str
    updated_at: str
