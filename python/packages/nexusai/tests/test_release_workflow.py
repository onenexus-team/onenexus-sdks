from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[4]
    / ".github"
    / "workflows"
    / "nexusai-release.yml"
)


def test_nexusai_release_pipeline_is_fail_closed() -> None:
    workflow = WORKFLOW.read_text()

    assert 'tags:\n      - "nexusai-v*"' in workflow
    assert "uv sync --package nexusai --all-extras --frozen" in workflow
    assert "pytest -q packages/nexusai/tests" in workflow
    assert "ruff check packages/nexusai" in workflow
    assert "mypy packages/nexusai/nexusai" in workflow
    assert "SOURCE_DATE_EPOCH" in workflow
    assert "uv build --package nexusai --wheel" in workflow
    assert "sha256sum" in workflow
    assert 'pip" check' in workflow
    assert "nexusai-wheel-smoke" in workflow
    assert "actions/attest-build-provenance@v2" in workflow
    assert "refusing to overwrite it" in workflow


def test_manual_dispatch_does_not_publish_a_release() -> None:
    workflow = WORKFLOW.read_text()

    release_step = workflow.split(
        "- name: Create immutable NexusAI GitHub release", maxsplit=1
    )[1]
    assert "if: github.ref_type == 'tag'" in release_step


def test_shared_sdk_release_jobs_ignore_nexusai_tags() -> None:
    workflow = WORKFLOW.with_name("sdk-release.yml").read_text()

    # Only the prepare job can start an SDK release. All publication depends on
    # its guarded version output and on the complete language build matrix.
    assert "  prepare:\n    if: startsWith(github.event.release.tag_name, 'v')\n" in workflow
    assert "  build:\n    needs: prepare\n" in workflow
    assert "needs: [prepare, build]" in workflow
