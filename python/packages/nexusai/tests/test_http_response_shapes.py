from __future__ import annotations

import pytest

from nexusai.errors import OneNexusError
from nexusai._internal.http import APIClient, APIListEnvelope


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
        "post_list_envelope",
        lambda *_args, **_kwargs: APIListEnvelope(
            items=[{"id": "one"}, {"id": "two"}], total_pages=1
        ),
    )

    assert client.post_list("/resources") == [{"id": "one"}, {"id": "two"}]

    with pytest.raises(OneNexusError, match="invalid list items"):
        client._decode_list_response(b'{"items":["invalid"],"total_pages":1}')


@pytest.mark.parametrize(
    "payload",
    [
        b'{"data":[]}',
        b'{"items":[],"total_pages":-1}',
        b'{"items":[]}',
    ],
)
def test_list_decoder_rejects_legacy_or_invalid_envelopes(payload: bytes) -> None:
    client = APIClient(token="test-token", base_url="https://api.example.test")

    with pytest.raises(OneNexusError):
        client._decode_list_response(payload)


def test_object_decoder_rejects_bare_or_list_envelopes() -> None:
    client = APIClient(token="test-token", base_url="https://api.example.test")

    with pytest.raises(OneNexusError, match="invalid object envelope"):
        client._decode_response(b'{"items":[],"total_pages":0}')


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
