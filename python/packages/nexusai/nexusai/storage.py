from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import boto3  # type: ignore[import-untyped]

from .config import DEFAULT_REGION


@dataclass(frozen=True)
class StorageTransferFile:
    local_path: str
    object_key: str
    size_bytes: int


def upload_path(
    source_path: str | Path,
    credential: dict[str, Any],
    region: str = DEFAULT_REGION,
) -> list[StorageTransferFile]:
    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Source path not found: {source}")

    s3 = _s3_client(credential, region=region)
    prefix = _normalize_prefix(credential["prefix"])
    uploaded: list[StorageTransferFile] = []

    if source.is_file():
        uploaded.append(
            _upload_file(s3, credential["bucket"], prefix, source, source.name)
        )
        return uploaded

    for file_path in _iter_files(source):
        relative_path = file_path.relative_to(source).as_posix()
        uploaded.append(
            _upload_file(s3, credential["bucket"], prefix, file_path, relative_path)
        )
    return uploaded


def download_prefix(
    destination_path: str | Path,
    credential: dict[str, Any],
    region: str = DEFAULT_REGION,
) -> list[StorageTransferFile]:
    destination = Path(destination_path).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)

    s3 = _s3_client(credential, region=region)
    bucket = credential["bucket"]
    prefix = _normalize_prefix(credential["prefix"])
    files: list[StorageTransferFile] = []

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item.get("Key", "")
            if not key or key == prefix or key.endswith("/"):
                continue
            relative_path = _relative_key(key, prefix)
            local_path = destination / relative_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(local_path))
            files.append(
                StorageTransferFile(
                    local_path=str(local_path),
                    object_key=key,
                    size_bytes=item.get("Size", 0),
                )
            )
    return files


def _s3_client(credential: dict[str, Any], region: str) -> Any:
    kwargs = {
        "endpoint_url": credential["endpoint_url"],
        "aws_access_key_id": credential["access_key"],
        "aws_secret_access_key": credential["secret_key"],
        "region_name": region,
    }
    session_token = credential.get("session_token")
    if session_token:
        kwargs["aws_session_token"] = session_token

    return boto3.client(
        "s3",
        **kwargs,
    )


def _upload_file(
    s3: Any,
    bucket: str,
    prefix: str,
    file_path: Path,
    relative_path: str,
) -> StorageTransferFile:
    key = f"{prefix}/{relative_path}" if prefix else relative_path
    s3.upload_file(str(file_path), bucket, key)
    return StorageTransferFile(
        local_path=str(file_path),
        object_key=key,
        size_bytes=file_path.stat().st_size,
    )


def _iter_files(root: Path) -> Iterable[Path]:
    for item in sorted(root.rglob("*")):
        if item.is_file():
            yield item


def _normalize_prefix(prefix: str) -> str:
    return str(prefix or "").strip("/")


def _relative_key(key: str, prefix: str) -> str:
    folder = f"{prefix}/" if prefix else ""
    if folder and key.startswith(folder):
        return key[len(folder) :]
    return key
