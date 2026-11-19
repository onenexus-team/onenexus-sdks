from dataclasses import dataclass
from typing import Generic, TypeVar


ResourceT = TypeVar("ResourceT")


@dataclass(frozen=True)
class TransferFile:
    path: str
    size_bytes: int


@dataclass(frozen=True)
class UploadResult(Generic[ResourceT]):
    resource: ResourceT
    files: list[TransferFile]


@dataclass(frozen=True)
class DownloadResult(Generic[ResourceT]):
    resource: ResourceT
    files: list[TransferFile]
