# NexusAI Python SDK

Python SDK and CLI for the OneNexus MLOps platform. The SDK only uses the
PascalCase RPC API and targets:

- Data Hub dataset metadata and upload lifecycle.
- Training experiments, runs, logs, metrics, checkpoints, and tokenizers.
- Model Registry models and model versions.
- Inference instances and OpenAI-compatible endpoint discovery.

Default URLs:

- Platform API: `https://ai-api-v2.onenexus-do.cloud`
- CAS: `https://cas.onenexus-do.cloud`
- S3 endpoint: `https://s3.onenexus-do.cloud`

The SDK sends `Authorization: Bearer <token>` to the MLOps API. Dataset/model
upload and download do not use MLOps credential-returning endpoints. The SDK
exchanges the saved token with CAS at runtime, obtains temporary S3 credentials,
performs the S3 transfer, then calls the MLOps finalize API.

## Install

Install the current internal wheel from the public S3 artifact bucket:

```bash
python -m pip install --upgrade \
  https://s3.onenexus-do.cloud/019eee637b887feb858b1c6250a19e0c%3Aonenexus-public-sdk-artifacts/nexusai/releases/v0.0.3/nexusai-0.0.3-py3-none-any.whl
```

For local development from this repository:

```bash
cd /Users/hoangbui2/Desktop/OneNexusWorkspace/onenexus-sdks/python/packages/nexusai
python -m pip install -e .
```

## Login

Interactive login:

```bash
nexusai login --url https://ai-api-v2.onenexus-do.cloud
```

Non-interactive login:

```bash
export NEXUSAI_TOKEN="<token>"
nexusai login \
  --url https://ai-api-v2.onenexus-do.cloud \
  --cas-url https://cas.onenexus-do.cloud \
  --token "$NEXUSAI_TOKEN"
```

You can also pass the token on every command:

```bash
nexusai --token "$NEXUSAI_TOKEN" DataHub ListDatasets
```

## Python Full Flow

This example simulates a real user flow:

1. Upload a local dataset.
2. Create a training experiment and run with Qwen3-0.6B.
3. Read logs, metrics, and checkpoints.
4. Register a model version from a checkpoint.
5. Create an inference instance.
6. Call the inference endpoint with the OpenAI-compatible API.

The final inference call uses `requests`; install it with
`python -m pip install requests` if your environment does not already have it.

```python
import os
import time
from pathlib import Path

import requests
from nexusai import OneNexusClient


client = OneNexusClient(
    token=os.environ["NEXUSAI_TOKEN"],
    base_url="https://ai-api-v2.onenexus-do.cloud",
    cas_url="https://cas.onenexus-do.cloud",
)


def wait_for_terminal_run(experiment_id: str, run_id: str, timeout_seconds: int = 7200):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        run = client.training.get_run(experiment_id=experiment_id, run_id=run_id)
        status = str(run.get("status", "")).upper()
        print("training status:", status)
        if status in {"SUCCEEDED", "FAILED", "CANCELED", "STOPPED"}:
            return run
        time.sleep(30)
    raise TimeoutError(f"training run did not finish within {timeout_seconds}s")


def wait_for_inference_endpoint(inference_instance_id: str, timeout_seconds: int = 3600):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        endpoint = client.inference.get_inference_instance_endpoint(
            inference_instance_id=inference_instance_id
        )
        status = str(endpoint.get("status", "")).upper()
        print("inference status:", status, "endpoint:", endpoint.get("endpoint"))
        if endpoint.get("endpoint"):
            return endpoint
        if status in {"FAILED", "STOPPED", "DELETED"}:
            raise RuntimeError(endpoint)
        time.sleep(20)
    raise TimeoutError(f"inference endpoint was not ready within {timeout_seconds}s")


# 1. Prepare and upload a dataset.
dataset_dir = Path("tmp/qwen3-smoke-dataset")
dataset_dir.mkdir(parents=True, exist_ok=True)
(dataset_dir / "train.jsonl").write_text(
    '{"text":"OneNexus training sample 1."}\n'
    '{"text":"OneNexus training sample 2."}\n',
    encoding="utf-8",
)

dataset_upload = client.data_hub.upload_dataset(
    name="qwen3-smoke-dataset",
    source_path=str(dataset_dir),
    extras_data={"purpose": "sdk-readme-smoke"},
)
dataset = dataset_upload.resource
dataset_id = dataset["id"]
print("dataset:", dataset_id)
print("dataset files:", client.data_hub.list_dataset_files(dataset_id))


# 2. Create a training experiment and run.
experiment = client.training.create_experiment(
    name="qwen3-smoke-experiment",
    extras_data={"purpose": "sdk-readme-smoke"},
)
experiment_id = experiment["id"]

run = client.training.create_run(
    experiment_id=experiment_id,
    name="qwen3-0-6b-smoke-run",
    dataset_id=dataset_id,
    training_type="pretraining",
    flavor="2x2-mi355",
    input_model_id="Qwen/Qwen3-0.6B",
    num_checkpoint=1,
    hyperparameters={
        "model": {
            "from": "registry",
            "module": "nexus_titan.torchtitan_ft_configs",
            "config": "qwen3_0_6b_ft_pretrain",
        }
    },
    extras_data={"purpose": "sdk-readme-smoke"},
)
run_id = run["id"]
print("run:", run_id)


# 3. Observe logs and metrics while the run is active.
print("run logs iframe:", client.training.get_run_logs(experiment_id, run_id))
print("run metrics iframe:", client.training.get_run_metrics(experiment_id, run_id))

final_run = wait_for_terminal_run(experiment_id, run_id)
if str(final_run.get("status", "")).upper() != "SUCCEEDED":
    raise RuntimeError(final_run)

checkpoints = client.training.list_run_checkpoints(experiment_id, run_id)
print("checkpoints:", checkpoints)
checkpoint_name = checkpoints[-1]["name"] if checkpoints else "step-10"


# 4. Register a model version from the selected training checkpoint.
model = client.model_registry.create_model(
    name="qwen3-0-6b-smoke-model",
    extras_data={"source": "training-checkpoint"},
)
model_version = client.model_registry.create_model_version_from_checkpoint(
    model_id=model["id"],
    name=f"{checkpoint_name}-hf",
    experiment_id=experiment_id,
    run_id=run_id,
    checkpoint_name=checkpoint_name,
    extras_data={"source_checkpoint": checkpoint_name},
)
print("model:", model["id"])
print("model version:", model_version["id"])


# 5. Create inference from the registered model version.
inference = client.inference.create_inference_instance(
    name="qwen3-0-6b-smoke-inference",
    model_id=model["id"],
    model_version_id=model_version["id"],
    served_model_name="qwen3-0.6b",
    flavor="1x1-mi355",
    configuration={},
)
inference_instance_id = inference["id"]
endpoint = wait_for_inference_endpoint(inference_instance_id)
base_url = endpoint["endpoint"].rstrip("/")


# 6. Call the OpenAI-compatible chat completion endpoint.
response = requests.post(
    f"{base_url}/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    json={
        "model": "qwen3-0.6b",
        "messages": [{"role": "user", "content": "hello world"}],
        "temperature": 0.2,
        "max_tokens": 128,
    },
    timeout=120,
    verify=False,
)
response.raise_for_status()
print(response.json())
```

## CLI Full Flow

The commands below use only PascalCase resource and operation names. They assume
`jq` is installed.

### 1. Login

```bash
export NEXUSAI_TOKEN="<token>"

nexusai login \
  --url https://ai-api-v2.onenexus-do.cloud \
  --cas-url https://cas.onenexus-do.cloud \
  --token "$NEXUSAI_TOKEN"

nexusai whoami
```

### 2. Prepare a sample dataset

```bash
mkdir -p /tmp/onenexus-qwen3-dataset
cat > /tmp/onenexus-qwen3-dataset/train.jsonl <<'JSONL'
{"text":"OneNexus training sample 1."}
{"text":"OneNexus training sample 2."}
JSONL
```

### 3. Create and upload the dataset

```bash
nexusai DataHub CreateDataset \
  --name qwen3-smoke-dataset \
  --extras-json '{"purpose":"cli-smoke"}' | tee /tmp/onenexus-dataset.json

export DATASET_ID="$(jq -r '.id' /tmp/onenexus-dataset.json)"

nexusai DataHub GetUploadDatasetInstruction \
  --dataset-id "$DATASET_ID"

nexusai DataHub UploadToDataset \
  --dataset-id "$DATASET_ID" \
  --source-path /tmp/onenexus-qwen3-dataset | tee /tmp/onenexus-dataset-upload.json

nexusai DataHub ListDatasetFiles --dataset-id "$DATASET_ID"
nexusai DataHub GetDatasetSize --dataset-id "$DATASET_ID"
```

### 4. Create a training experiment

```bash
nexusai Training CreateExperiment \
  --name qwen3-smoke-experiment \
  --extras-json '{"purpose":"cli-smoke"}' | tee /tmp/onenexus-experiment.json

export EXPERIMENT_ID="$(jq -r '.id' /tmp/onenexus-experiment.json)"
```

### 5. Start a Qwen3-0.6B training run

```bash
nexusai Training CreateRun \
  --experiment-id "$EXPERIMENT_ID" \
  --name qwen3-0-6b-smoke-run \
  --dataset-id "$DATASET_ID" \
  --training-type pretraining \
  --flavor 2x2-mi355 \
  --input-model-id Qwen/Qwen3-0.6B \
  --num-checkpoint 1 \
  --hyperparameters-json '{"model":{"from":"registry","module":"nexus_titan.torchtitan_ft_configs","config":"qwen3_0_6b_ft_pretrain"}}' \
  --extras-json '{"purpose":"cli-smoke"}' | tee /tmp/onenexus-run.json

export RUN_ID="$(jq -r '.id' /tmp/onenexus-run.json)"
```

### 6. Observe run status, logs, metrics, and checkpoints

```bash
nexusai Training GetRun \
  --experiment-id "$EXPERIMENT_ID" \
  --run-id "$RUN_ID"

nexusai Training GetRunLogs \
  --experiment-id "$EXPERIMENT_ID" \
  --run-id "$RUN_ID" | tee /tmp/onenexus-run-logs.json

nexusai Training GetRunMetrics \
  --experiment-id "$EXPERIMENT_ID" \
  --run-id "$RUN_ID" | tee /tmp/onenexus-run-metrics.json

nexusai Training ListRunCheckpoints \
  --experiment-id "$EXPERIMENT_ID" \
  --run-id "$RUN_ID" | tee /tmp/onenexus-checkpoints.json

export CHECKPOINT_NAME="$(jq -r '.[-1].name // "step-10"' /tmp/onenexus-checkpoints.json)"
```

### 7. Optional: resume from a checkpoint

```bash
nexusai Training ResumeRun \
  --experiment-id "$EXPERIMENT_ID" \
  --run-id "$RUN_ID" \
  --checkpoint-name "$CHECKPOINT_NAME"
```

### 8. Register a model version from the training checkpoint

```bash
nexusai ModelRegistry CreateModel \
  --name qwen3-0-6b-smoke-model \
  --extras-json '{"source":"training-checkpoint"}' | tee /tmp/onenexus-model.json

export MODEL_ID="$(jq -r '.id' /tmp/onenexus-model.json)"

nexusai ModelRegistry CreateModelVersionFromCheckpoint \
  --model-id "$MODEL_ID" \
  --name "${CHECKPOINT_NAME}-hf" \
  --experiment-id "$EXPERIMENT_ID" \
  --run-id "$RUN_ID" \
  --checkpoint-name "$CHECKPOINT_NAME" \
  --extras-json "{\"source_checkpoint\":\"$CHECKPOINT_NAME\"}" | tee /tmp/onenexus-model-version.json

export MODEL_VERSION_ID="$(jq -r '.id' /tmp/onenexus-model-version.json)"

nexusai ModelRegistry GetModelVersion \
  --model-id "$MODEL_ID" \
  --model-version-id "$MODEL_VERSION_ID"
```

### 9. Create an inference instance

```bash
nexusai Inference CreateInferenceInstance \
  --name qwen3-0-6b-smoke-inference \
  --model-id "$MODEL_ID" \
  --model-version-id "$MODEL_VERSION_ID" \
  --served-model-name qwen3-0.6b \
  --flavor 1x1-mi355 \
  --configuration-json '{}' | tee /tmp/onenexus-inference.json

export INFERENCE_INSTANCE_ID="$(jq -r '.id' /tmp/onenexus-inference.json)"
```

### 10. Get endpoint, logs, and metrics

```bash
nexusai Inference GetInferenceInstance \
  --inference-instance-id "$INFERENCE_INSTANCE_ID"

nexusai Inference GetInferenceInstanceEndpoint \
  --inference-instance-id "$INFERENCE_INSTANCE_ID" | tee /tmp/onenexus-inference-endpoint.json

nexusai Inference GetInferenceInstanceLogs \
  --inference-instance-id "$INFERENCE_INSTANCE_ID"

nexusai Inference GetInferenceInstanceMetrics \
  --inference-instance-id "$INFERENCE_INSTANCE_ID"
```

### 11. Call the OpenAI-compatible endpoint

```bash
export INFERENCE_ENDPOINT="$(jq -r '.endpoint' /tmp/onenexus-inference-endpoint.json)"

curl -k --location "$INFERENCE_ENDPOINT/v1/chat/completions" \
  --header 'Content-Type: application/json' \
  --data '{
    "model": "qwen3-0.6b",
    "messages": [
      {
        "role": "user",
        "content": "hello world"
      }
    ],
    "temperature": 0.2,
    "max_tokens": 128
  }'
```

### 12. Optional cleanup

Use cleanup only when no active run or inference is using the resource.

```bash
nexusai Inference StopInferenceInstance \
  --inference-instance-id "$INFERENCE_INSTANCE_ID"

nexusai Inference DeleteInferenceInstance \
  --inference-instance-id "$INFERENCE_INSTANCE_ID"

nexusai Training DeleteRun \
  --experiment-id "$EXPERIMENT_ID" \
  --run-id "$RUN_ID"
```

## Notes

- The SDK defaults to RPC. Keep using PascalCase domains and commands for the
  clean public interface.
- Dataset/model S3 credentials are never returned by the MLOps API. The SDK
  obtains temporary credentials through CAS at runtime.
- `GetRunLogs`, `GetRunMetrics`, `GetInferenceInstanceLogs`, and
  `GetInferenceInstanceMetrics` return monitoring URLs or payloads suitable for
  frontend iframe integration.
