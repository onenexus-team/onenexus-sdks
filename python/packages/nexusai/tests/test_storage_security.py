from __future__ import annotations

from pathlib import Path

import pytest

import nexusai._internal.storage as storage


CREDENTIAL = {
    "endpoint_url": "https://s3.example.test",
    "access_key": "access",
    "secret_key": "secret",
    "bucket": "bucket",
    "prefix": "tenant/resource",
}


class Paginator:
    def __init__(self, contents: list[dict[str, object]]) -> None:
        self.contents = contents

    def paginate(self, **_kwargs):
        return [{"Contents": self.contents}]


class DownloadClient:
    def __init__(self, contents: list[dict[str, object]], payload: bytes) -> None:
        self.paginator = Paginator(contents)
        self.payload = payload

    def get_paginator(self, _name: str) -> Paginator:
        return self.paginator

    def download_file(self, _bucket: str, _key: str, destination: str) -> None:
        Path(destination).write_bytes(self.payload)


def test_relative_key_rejects_prefix_escape_and_path_traversal() -> None:
    with pytest.raises(ValueError, match="outside prefix"):
        storage._relative_key("other/file.bin", "tenant/resource")
    with pytest.raises(ValueError, match="Unsafe object key"):
        storage._relative_key("tenant/resource/../secret", "tenant/resource")
    with pytest.raises(ValueError, match="Unsafe object key"):
        storage._relative_key("tenant/resource//file", "tenant/resource")


def test_upload_rejects_source_symlink(tmp_path, monkeypatch) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"data")
    source = tmp_path / "source.bin"
    source.symlink_to(target)
    monkeypatch.setattr(storage, "_s3_client", lambda *_a, **_k: object())

    with pytest.raises(ValueError, match="symbolic link"):
        storage.upload_path(source, CREDENTIAL)


def test_upload_rejects_symlink_inside_directory(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target.bin"
    target.write_bytes(b"data")
    (source / "linked.bin").symlink_to(target)
    monkeypatch.setattr(storage, "_s3_client", lambda *_a, **_k: object())

    with pytest.raises(ValueError, match="symbolic link"):
        storage.upload_path(source, CREDENTIAL)


def test_download_is_atomic_and_verifies_size(tmp_path, monkeypatch) -> None:
    client = DownloadClient([{"Key": "tenant/resource/model.bin", "Size": 4}], b"bad")
    monkeypatch.setattr(storage, "_s3_client", lambda *_a, **_k: client)

    with pytest.raises(OSError, match="size mismatch"):
        storage.download_prefix(tmp_path, CREDENTIAL)

    assert not (tmp_path / "model.bin").exists()
    assert list(tmp_path.glob("*.part")) == []


def test_download_atomically_replaces_final_file(tmp_path, monkeypatch) -> None:
    client = DownloadClient([{"Key": "tenant/resource/model.bin", "Size": 4}], b"data")
    monkeypatch.setattr(storage, "_s3_client", lambda *_a, **_k: client)

    files = storage.download_prefix(tmp_path, CREDENTIAL)

    assert (tmp_path / "model.bin").read_bytes() == b"data"
    assert files[0].object_key == "tenant/resource/model.bin"
    assert list(tmp_path.glob("*.part")) == []
