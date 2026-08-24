# NexusAI Python SDK

NexusAI is the typed Python SDK and CLI for OneNexus Data Hub, Model Registry,
Training, Inference, and Tenant Workspace APIs. The public SDK uses PascalCase
RPC operations on the wire while exposing idiomatic Python client methods.

Default services:

- Platform API: `https://ai-api-v2.ric1.onenexus-do.cloud`
- CAS: `https://cas.ric1.onenexus-do.cloud`

The SDK accepts one token and sends it to the Platform API. High-level transfer
methods exchange that token through CAS for short-lived, resource-scoped S3
access. Public API responses never contain S3 credentials, bucket names,
Kubernetes identifiers, upload sessions, leases, or execution records.

## Requirements

- Python 3.11 or newer
- A OneNexus token authorized for the target tenant
- Network access to the Platform API, CAS, and configured object storage

## Install

Install the immutable wheel from the public SDK artifact bucket:

```bash
python -m pip install \
  "<wheel-url-from-platform-catalog>"
```

Verify the wheel against the SHA256 stored in Platform Catalog before
installing it in a production image. The MLOps upload instruction resolves the
current reviewed release URL from Platform Catalog.

For repository development, run this from the SDK repository root:

```bash
python -m pip install -e python/packages/nexusai
```

## Authentication

Interactive login stores the token and service URLs in the current user's
configuration directory:

```bash
nexusai login --url https://ai-api-v2.ric1.onenexus-do.cloud
```

For non-interactive use, pass a token explicitly:

```bash
export NEXUSAI_TOKEN="<token>"
nexusai --token "$NEXUSAI_TOKEN" DataHub ListDatasets
```

`nexusai whoami` decodes JWT claims locally for display only. Its output marks
those claims as unverified; authorization is always decided by the server.

## Python Quick Start

```python
import os

from nexusai import OneNexusClient, RetryPolicy


client = OneNexusClient(
    token=os.environ["NEXUSAI_TOKEN"],
    retry_policy=RetryPolicy(max_attempts=3, max_elapsed_seconds=15),
)

datasets = client.data_hub.list_datasets(limit=20)
for dataset in datasets:
    print(dataset.id, dataset.name, dataset.status)
```

List methods return a typed `Page[T]`. The page preserves response metadata:

```python
page = client.model_registry.list_models(limit=20)
print(page.total_pages, page.request_id)
for model in page:
    print(model.id, model.latest_version)
```

## Errors and Lifecycle Codes

API failures raise `OneNexusAPIError`. Branch on the RFC 7807 problem URI, not
the localized title or detail:

```python
from nexusai import OneNexusAPIError, ProblemType

try:
    client.data_hub.get_dataset("missing-id")
except OneNexusAPIError as error:
    if error.problem_type == ProblemType.RESOURCE_NOT_FOUND:
        print("Dataset not found", error.request_id)
```

Resources and accepted asynchronous actions expose the server-provided
`message_code`. Stable values are listed by `nexusai.MessageCode`; the SDK does
not infer a code from status.

## Dataset Upload and Download

High-level methods own the complete create, transfer, and finalize workflow.
They do not expose upload sessions or temporary credentials.

```python
from pathlib import Path


source = Path("training-data")
source.mkdir(exist_ok=True)
(source / "train.jsonl").write_text(
    '{"text":"OneNexus sample 1"}\n'
    '{"text":"OneNexus sample 2"}\n',
    encoding="utf-8",
)

upload = client.data_hub.upload_dataset(
    name="qwen3-training-data",
    source_path=str(source),
)
dataset = upload.resource
print(dataset.id, dataset.status, len(upload.files))

download = client.data_hub.download_dataset(
    dataset_id=dataset.id,
    destination_path="downloaded-data",
)
print(download.resource.id, len(download.files))
```

Each transfer entry contains only a path relative to the requested source or
destination and its byte size. Storage object keys, bucket names, credentials,
and absolute local paths remain internal.

Upload sources cannot be symbolic links. Downloads reject unsafe object keys,
write through temporary files, verify object size, and atomically replace the
final path.

## Training and Monitoring

```python
experiment = client.training.create_experiment(name="qwen3-experiment")
run_action = client.training.create_run(
    experiment_id=experiment.id,
    name="qwen3-0-6b-run",
    dataset_id=dataset.id,
    training_type="pretraining",
    flavor="2x2-mi355",
    input_model_id="Qwen/Qwen3-0.6B",
    hyperparameters={},
    num_checkpoint=1,
)

run = client.training.wait_for_run(
    experiment_id=experiment.id,
    run_id=run_action.resource_id,
    target_statuses={"COMPLETED", "FAILED", "CANCELED"},
)
print(run.id, run.status, run.status_message)

logs = client.training.get_run_logs(experiment.id, run.id)
metrics = client.training.get_run_metrics(experiment.id, run.id)
print(logs.overview.iframe_url)
print(metrics.overview.model_metrics_iframe_url)

for attempt in logs.attempts:
    print(attempt.attempt, attempt.status, attempt.iframe_url)
```

Monitoring results contain one overall projection and one projection per run
attempt. Iframe URLs are opaque: clients must not derive Grafana queries,
execution IDs, namespaces, or JobSet names.

## Model Registry

Register a model version from a finalized checkpoint:

```python
checkpoints = client.training.list_run_checkpoints(experiment.id, run.id)
checkpoint = checkpoints[-1]

model = client.model_registry.create_model(name="qwen3-private")
version_action = client.model_registry.create_model_version_from_checkpoint(
    model_id=model.id,
    name=f"{checkpoint.name}-hf",
    experiment_id=experiment.id,
    run_id=run.id,
    checkpoint_name=checkpoint.name,
)
version = client.model_registry.get_model_version(
    model_id=model.id,
    model_version_id=version_action.resource_id,
)
print(version.id, version.status, version.artifact_format)
```

You can also upload and download a model version directly with
`upload_model_version`, `upload_to_model_version`, and
`download_model_version`. These methods keep transfer credentials private.

## Inference

```python
instance_action = client.inference.create_inference_instance(
    name="qwen3-private-inference",
    model_id=model.id,
    model_version_id=version.id,
    served_model_name="qwen3-private",
    flavor="1x1-mi355",
    configuration={},
)

instance = client.inference.wait_for_inference_instance(
    instance_action.resource_id,
    target_statuses={"RUNNING", "FAILED"},
)
if instance.status != "RUNNING":
    raise RuntimeError(instance.status_message)

endpoint = client.inference.get_inference_instance_endpoint(instance.id)
print(endpoint.endpoint)
```

The returned endpoint is OpenAI compatible. Use a normal TLS-verified request:

```bash
curl --location 'https://your-inference-domain/v1/chat/completions' \
  --header 'Content-Type: application/json' \
  --data '{
    "model": "qwen3-private",
    "messages": [{"role": "user", "content": "hello world"}],
    "temperature": 0.2,
    "max_tokens": 128
  }'
```

## CLI

The CLI defaults to human-readable tables. Headers and identifiers use cyan,
successful states use green, transitional states use yellow, and failures use
red when stdout is a TTY. Color is disabled for pipes and when `NO_COLOR` or
`--no-color` is set.

```bash
nexusai DataHub ListDatasets
nexusai Training GetRun --experiment-id "$EXPERIMENT_ID" --run-id "$RUN_ID"
```

Use JSON for automation:

```bash
nexusai --output json ModelRegistry ListModels --limit 20
```

Extract a scalar without `jq`:

```bash
DATASET_ID="$(nexusai --field id DataHub CreateDataset --name sample-data)"
EXPERIMENT_ID="$(nexusai --field id Training CreateExperiment --name sample-exp)"
RUN_ID="$(
  nexusai --field resource_id Training CreateRun \
    --experiment-id "$EXPERIMENT_ID" \
    --name sample-run \
    --dataset-id "$DATASET_ID" \
    --training-type pretraining \
    --flavor 2x2-mi355 \
    --input-model-id Qwen/Qwen3-0.6B \
    --hyperparameters-json '{}'
)"
```

CLI errors are written to stderr with stable exit codes:

| Exit | Meaning |
| ---: | --- |
| 2 | Invalid CLI usage |
| 3 | Authentication or authorization failure |
| 4 | Validation or conflict |
| 5 | Resource not found |
| 6 | Transient operation exhausted retries |
| 70 | Unexpected failure |
| 130 | Canceled by the user |

Use `--debug` only when a traceback is needed for diagnosis.

## Retry Policy

Read-only RPC calls retry transient connection failures, timeouts, HTTP 408,
429, and retryable 5xx responses with bounded exponential backoff and full
jitter. `Retry-After` is honored within the configured delay limit.

For every mutating RPC call, the SDK generates an `Idempotency-Key` header and
keeps it stable across transport retries. The backend scopes the key to the
authenticated tenant, principal, and operation, so a lost response cannot
create or finalize the same resource twice. A normal HTTP 409 is not retried;
only the explicit `idempotency_in_progress` conflict may be retried. Storage
transfers retry at the object-transfer layer; the SDK does not restart an
entire create/upload/finalize workflow after a later phase succeeds.

Disable retries when the caller owns retry orchestration:

```python
client = OneNexusClient(
    token=os.environ["NEXUSAI_TOKEN"],
    retry_policy=RetryPolicy(enabled=False),
)
```

Every API request includes `nexusai/<version>` in `User-Agent` and a generated
`X-Request-ID`. The SDK does not add opt-out telemetry.

## Errors

Library calls raise `OneNexusAPIError` for API failures and `OneNexusError` for
SDK and transport failures:

```python
from nexusai import OneNexusAPIError


try:
    client.data_hub.get_dataset("missing")
except OneNexusAPIError as error:
    print(error.status_code, error.code, error.message, error.request_id)
```

See [COMPATIBILITY.md](COMPATIBILITY.md), [MIGRATION.md](MIGRATION.md), and
[CHANGELOG.md](CHANGELOG.md) for versioning and upgrade policy.
