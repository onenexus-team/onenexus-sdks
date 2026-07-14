from __future__ import annotations

import pytest

import nexusai.wait as wait_module
from nexusai import WaitPolicy, WaitTimeoutError
from nexusai.inference import InferenceClient
from nexusai.models import InferenceInstanceDetail, RunDetail
from nexusai.training import TrainingClient


def run(status: str) -> RunDetail:
    return RunDetail.from_dict(
        {
            "id": "run-1",
            "name": "run",
            "experiment": {"id": "exp-1", "name": "experiment"},
            "dataset": {"id": "dataset-1", "name": "dataset"},
            "input_model": {
                "source": "huggingface",
                "huggingface_id": "Qwen/Qwen3-0.6B",
            },
            "training_type": "pretraining",
            "flavor": "2x2-mi355",
            "status": status,
            "status_message": status.title(),
            "created_at": "2026-07-13T00:00:00Z",
            "updated_at": "2026-07-13T00:00:00Z",
        }
    )


def inference(status: str) -> InferenceInstanceDetail:
    return InferenceInstanceDetail.from_dict(
        {
            "id": "instance-1",
            "name": "instance",
            "model": {
                "source": "huggingface",
                "huggingface_id": "Qwen/Qwen3-0.6B",
            },
            "served_model_name": "qwen",
            "flavor": "1x1-mi355",
            "status": status,
            "status_message": status.title(),
            "created_at": "2026-07-13T00:00:00Z",
            "updated_at": "2026-07-13T00:00:00Z",
        }
    )


def test_training_waiter_polls_until_requested_status(monkeypatch) -> None:
    client = object.__new__(TrainingClient)
    responses = iter([run("SCHEDULING"), run("RUNNING"), run("COMPLETED")])
    monkeypatch.setattr(client, "get_run", lambda *_args: next(responses))
    monkeypatch.setattr(wait_module.time, "sleep", lambda _delay: None)

    result = client.wait_for_run(
        "exp-1",
        "run-1",
        target_statuses={"COMPLETED"},
        policy=WaitPolicy(timeout_seconds=1, interval_seconds=0),
    )

    assert result.status == "COMPLETED"


def test_inference_waiter_returns_running_instance(monkeypatch) -> None:
    client = object.__new__(InferenceClient)
    responses = iter([inference("DEPLOYING"), inference("RUNNING")])
    monkeypatch.setattr(
        client, "get_inference_instance", lambda *_args: next(responses)
    )
    monkeypatch.setattr(wait_module.time, "sleep", lambda _delay: None)

    result = client.wait_for_inference_instance(
        "instance-1",
        target_statuses={"RUNNING"},
        policy=WaitPolicy(timeout_seconds=1, interval_seconds=0),
    )

    assert result.status == "RUNNING"


def test_waiter_timeout_reports_last_status(monkeypatch) -> None:
    times = iter([0.0, 2.0])
    monkeypatch.setattr(wait_module.time, "monotonic", lambda: next(times))

    with pytest.raises(WaitTimeoutError, match="last status was RUNNING"):
        wait_module.wait_for_status(
            lambda: run("RUNNING"),
            status_of=lambda item: item.status,
            target_statuses={"COMPLETED"},
            policy=WaitPolicy(timeout_seconds=1, interval_seconds=0),
            description="training run run-1",
        )
