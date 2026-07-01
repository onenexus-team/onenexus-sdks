from dataclasses import dataclass
from typing import Any

from .storage import StorageTransferFile


@dataclass(frozen=True)
class UploadResult:
    resource: dict[str, Any]
    credential: dict[str, Any]
    files: list[StorageTransferFile]


@dataclass(frozen=True)
class DownloadResult:
    resource: dict[str, Any]
    credential: dict[str, Any]
    files: list[StorageTransferFile]
