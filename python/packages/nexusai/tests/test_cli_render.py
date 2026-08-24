from __future__ import annotations

import io
from argparse import Namespace
from types import SimpleNamespace

from nexusai.cli import build_parser
from nexusai.cli_handlers import (
    handle_delete_dataset,
    handle_delete_model,
    handle_delete_model_version,
)
from nexusai.cli_errors import ExitCode, render_error
from nexusai.cli_progress import is_transfer_command, transfer_progress_for
from nexusai.cli_render import render_result
from nexusai.errors import OneNexusAPIError, ProblemType
from nexusai.models import DatasetSummary, Page


class TerminalBuffer(io.StringIO):
    def __init__(self, *, tty: bool) -> None:
        super().__init__()
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def dataset() -> DatasetSummary:
    return DatasetSummary(
        id="dataset-1",
        name="sample",
        status="READY",
        message_code="DATASET_READY",
        status_message="Ready",
        file_count=1,
        total_size_bytes=12,
    )


def test_table_output_is_stable_and_has_no_color_for_pipe() -> None:
    stream = TerminalBuffer(tty=False)

    render_result(Page(items=[dataset()], total_pages=1), stream=stream)

    output = stream.getvalue()
    assert "ID" in output
    assert "dataset-1" in output
    assert "READY" in output
    assert "\x1b[" not in output


def test_table_output_colors_tty_status(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    stream = TerminalBuffer(tty=True)

    render_result(dataset(), stream=stream)

    assert "\x1b[32mREADY\x1b[0m" in stream.getvalue()


def test_json_and_scalar_output_never_contain_ansi() -> None:
    json_stream = TerminalBuffer(tty=True)
    field_stream = TerminalBuffer(tty=True)

    render_result(dataset(), output="json", stream=json_stream)
    render_result(dataset(), field="id", stream=field_stream)

    assert '"id": "dataset-1"' in json_stream.getvalue()
    assert json_stream.getvalue().endswith("\n")
    assert field_stream.getvalue() == "dataset-1\n"
    assert "\x1b[" not in json_stream.getvalue() + field_stream.getvalue()


def test_detail_table_flattens_nested_user_data() -> None:
    stream = TerminalBuffer(tty=False)

    render_result(
        {
            "id": "run-1",
            "hyperparameters": {
                "optimizer": {"learning_rate": 0.001},
                "layers": [8, 16],
            },
        },
        stream=stream,
    )

    output = stream.getvalue()
    assert "hyperparameters.optimizer.learning_rate" in output
    assert "hyperparameters.layers" in output
    assert "8, 16" in output
    assert '{"optimizer"' not in output


def test_list_table_formats_resource_references_for_people() -> None:
    stream = TerminalBuffer(tty=False)

    render_result(
        [
            {
                "id": "run-1",
                "dataset": {"id": "dataset-1", "name": "training-data"},
                "input_model": {
                    "source": "platform",
                    "model": {"id": "model-1", "name": "qwen-private"},
                    "model_version": {"id": "version-1", "name": "v1"},
                },
            }
        ],
        stream=stream,
    )

    output = stream.getvalue()
    assert "training-data" in output
    assert "qwen-private / v1" in output
    assert '"model"' not in output


def test_error_table_contains_stable_fields_and_exit_code() -> None:
    stream = TerminalBuffer(tty=False)
    error = OneNexusAPIError(
        status_code=404,
        problem_type=ProblemType.RESOURCE_NOT_FOUND,
        title="Resource not found",
        detail="Dataset does not exist",
        request_id="request-1",
    )

    exit_code = render_error(error, stream=stream)

    output = stream.getvalue()
    assert exit_code == ExitCode.NOT_FOUND
    assert "HTTP status   404" in output
    assert ProblemType.RESOURCE_NOT_FOUND in output
    assert "Dataset does not exist" in output
    assert "request-1" in output
    assert "Traceback" not in output


def test_transfer_progress_is_disabled_for_machine_output() -> None:
    stream = TerminalBuffer(tty=True)
    args = Namespace(
        command="UploadDataset",
        output="json",
        field=None,
    )

    with transfer_progress_for(args, stream=stream):
        pass

    assert stream.getvalue() == ""
    assert is_transfer_command("UploadDataset")
    assert is_transfer_command("DownloadModelVersion")
    assert not is_transfer_command("ListModels")


def test_cli_registration_uses_split_handler_module() -> None:
    args = build_parser().parse_args(
        [
            "DataHub",
            "GetDataset",
            "--dataset-id",
            "dataset-1",
        ]
    )

    assert args.handler.__module__ == "nexusai.cli_handlers"


def test_delete_handlers_preserve_public_action_results() -> None:
    dataset_result = object()
    model_result = object()
    version_result = object()
    client = SimpleNamespace(
        data_hub=SimpleNamespace(delete_dataset=lambda _dataset_id: dataset_result),
        model_registry=SimpleNamespace(
            delete_model=lambda _model_id: model_result,
            delete_model_version=lambda **_kwargs: version_result,
        ),
    )

    assert (
        handle_delete_dataset(
            client,  # type: ignore[arg-type]
            Namespace(dataset_id="dataset-1"),
        )
        is dataset_result
    )
    assert (
        handle_delete_model(
            client,  # type: ignore[arg-type]
            Namespace(model_id="model-1"),
        )
        is model_result
    )
    assert (
        handle_delete_model_version(
            client,  # type: ignore[arg-type]
            Namespace(model_id="model-1", model_version_id="version-1"),
        )
        is version_result
    )
