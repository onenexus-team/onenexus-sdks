from importlib.metadata import requires


def test_runtime_sdk_dependencies_are_release_pinned_and_hash_verified():
    dependencies = requires("nexusai") or []
    core = next(item for item in dependencies if item.startswith("onenexus-sdk-core"))
    cas = next(item for item in dependencies if item.startswith("onenexus-cas-client"))

    assert "/releases/download/v0.0.2/" in core
    assert "onenexus_sdk_core-0.0.2-py3-none-any.whl" in core
    assert (
        "#sha256=4d12ecef5bea8326f1a6506bbe5c01be9f021dd948ffed0548a9affb5d3a319a"
        in core
    )
    assert "/releases/download/v0.0.2/" in cas
    assert "onenexus_cas_client-0.0.2-py3-none-any.whl" in cas
    assert (
        "#sha256=c3ce161dc7ee6f76932444456f23ae4cc8622976c3ecdc35a539ff1666ad1655"
        in cas
    )
