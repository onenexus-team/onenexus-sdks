from dataclasses import dataclass
from typing import Generic, TypeVar

from ..results import TransferFile
from .storage import StorageTransferFile


ResourceT = TypeVar("ResourceT")


@dataclass(frozen=True)
class InternalUploadResult(Generic[ResourceT]):
    resource: ResourceT
    files: list[StorageTransferFile]


@dataclass(frozen=True)
class InternalDownloadResult(Generic[ResourceT]):
    resource: ResourceT
    files: list[StorageTransferFile]


def to_public_transfer_files(
    files: list[StorageTransferFile],
) -> list[TransferFile]:
    return [
        TransferFile(path=file.relative_path, size_bytes=file.size_bytes)
        for file in files
    ]
