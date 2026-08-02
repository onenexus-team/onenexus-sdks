from importlib.metadata import requires


def test_runtime_sdk_dependencies_are_release_pinned_and_hash_verified():
    dependencies = requires("nexusai") or []
    core = next(item for item in dependencies if item.startswith("onenexus-sdk-core"))
    cas = next(item for item in dependencies if item.startswith("onenexus-cas-client"))

    assert "/releases/download/v0.0.8/" in core
    assert "onenexus_sdk_core-0.0.8-py3-none-any.whl" in core
    assert (
        "#sha256=0bd2e8c7ff5d1319ed4062bcc824828aeb56440ed5603cdd4433b7532ff090cf"
        in core
    )
    assert "/releases/download/v0.0.8/" in cas
    assert "onenexus_cas_client-0.0.8-py3-none-any.whl" in cas
    assert (
        "#sha256=0629868f45b7c8b6cb34f7e90402776dc8d14db54500086f494147d35653d2bb"
        in cas
    )
