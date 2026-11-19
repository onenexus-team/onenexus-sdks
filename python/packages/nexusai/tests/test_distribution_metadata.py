from importlib.metadata import requires


def test_runtime_sdk_dependencies_are_release_pinned_and_hash_verified():
    dependencies = requires("nexusai") or []
    core = next(item for item in dependencies if item.startswith("onenexus-sdk-core"))
    cas = next(item for item in dependencies if item.startswith("onenexus-cas-client"))

    assert "/releases/download/v0.0.15/" in core
    assert "onenexus_sdk_core-0.0.15-py3-none-any.whl" in core
    assert (
        "#sha256=e05ab620aa5caa5eb3bc7eb91cc9145e3c9e9fc871dc53138917fdea2f87bb97"
        in core
    )
    assert "/releases/download/v0.0.15/" in cas
    assert "onenexus_cas_client-0.0.15-py3-none-any.whl" in cas
    assert (
        "#sha256=f8968073ab84827a5d69bfcf834c5f64da396f95759d8fa16c1904f886a2a865"
        in cas
    )
