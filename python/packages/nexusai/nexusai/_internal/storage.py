import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from uuid import uuid4

import boto3

from ..config import DEFAULT_REGION


@dataclass(frozen=True)
class StorageTransferFile:
    local_path: str
    object_key: str
    relative_path: str
    size_bytes: int


def upload_path(
    source_path: str | Path,
    credential: dict[str, Any],
    region: str = DEFAULT_REGION,
) -> list[StorageTransferFile]:
    unresolved_source = Path(source_path).expanduser()
    if unresolved_source.is_symlink():
        raise ValueError("Upload source must not be a symbolic link")
    source = unresolved_source.resolve()
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
            local_path = (destination / relative_path).resolve()
            if not local_path.is_relative_to(destination):
                raise ValueError(f"Unsafe object key returned by storage: {key!r}")
            local_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = local_path.with_name(
                f".{local_path.name}.{uuid4().hex}.part"
            )
            try:
                s3.download_file(bucket, key, str(temporary_path))
                expected_size = int(item.get("Size", 0))
                actual_size = temporary_path.stat().st_size
                if actual_size != expected_size:
                    raise OSError(
                        f"Downloaded size mismatch for {key!r}: "
                        f"expected {expected_size}, got {actual_size}"
                    )
                os.replace(temporary_path, local_path)
            finally:
                temporary_path.unlink(missing_ok=True)
            files.append(
                StorageTransferFile(
                    local_path=str(local_path),
                    object_key=key,
                    relative_path=relative_path,
                    size_bytes=int(item.get("Size", 0)),
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
        relative_path=PurePosixPath(relative_path).as_posix(),
        size_bytes=file_path.stat().st_size,
    )


def _iter_files(root: Path) -> Iterable[Path]:
    for item in sorted(root.rglob("*")):
        if item.is_symlink():
            raise ValueError(f"Upload tree contains a symbolic link: {item}")
        if item.is_file():
            yield item


def _normalize_prefix(prefix: str) -> str:
    return str(prefix or "").strip("/")


def _relative_key(key: str, prefix: str) -> str:
    folder = f"{prefix}/" if prefix else ""
    if folder and not key.startswith(folder):
        raise ValueError(f"Object key {key!r} is outside prefix {prefix!r}")
    relative = key[len(folder) :] if folder else key
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or not relative
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"Unsafe object key returned by storage: {key!r}")
    return path.as_posix()
