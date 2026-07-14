from __future__ import annotations

import pytest

from nexusai.errors import OneNexusError
from nexusai._internal.http import APIClient


def test_post_dict_accepts_an_object_and_rejects_a_list(monkeypatch) -> None:
    client = APIClient(token="test-token", base_url="https://api.example.test")
    monkeypatch.setattr(client, "post", lambda *_args, **_kwargs: {"id": "one"})

    assert client.post_dict("/resource") == {"id": "one"}

    monkeypatch.setattr(client, "post", lambda *_args, **_kwargs: [])
    with pytest.raises(OneNexusError, match="expected object"):
        client.post_dict("/resource")


def test_post_list_accepts_objects_and_rejects_invalid_items(monkeypatch) -> None:
    client = APIClient(token="test-token", base_url="https://api.example.test")
    monkeypatch.setattr(
        client,
        "post",
        lambda *_args, **_kwargs: [{"id": "one"}, {"id": "two"}],
    )

    assert client.post_list("/resources") == [{"id": "one"}, {"id": "two"}]

    monkeypatch.setattr(client, "post", lambda *_args, **_kwargs: ["invalid"])
    with pytest.raises(OneNexusError, match="list of objects"):
        client.post_list("/resources")


def test_post_optional_dict_accepts_object_or_null_and_rejects_list(
    monkeypatch,
) -> None:
    client = APIClient(token="test-token", base_url="https://api.example.test")
    monkeypatch.setattr(client, "post", lambda *_args, **_kwargs: {"id": "one"})

    assert client.post_optional_dict("/resource") == {"id": "one"}

    monkeypatch.setattr(client, "post", lambda *_args, **_kwargs: None)
    assert client.post_optional_dict("/resource") is None

    monkeypatch.setattr(client, "post", lambda *_args, **_kwargs: [])
    with pytest.raises(OneNexusError, match="expected object or null"):
        client.post_optional_dict("/resource")
