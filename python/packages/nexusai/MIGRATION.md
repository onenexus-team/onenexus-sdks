# Migrating to NexusAI 0.1

NexusAI 0.1 aligns the SDK with the bounded public MLOps response contract.

## Public clients

Use `DataHubClient`, `ModelRegistryClient`, `TrainingClient`,
`InferenceClient`, `TenantWorkspaceClient`, and `PlatformCatalogClient` through
`OneNexusClient`. Do not import the former `Rpc*Client` classes.

## Typed results

Public methods now return typed Summary, Detail, Action, Monitoring, Page,
Upload, and Download results instead of arbitrary dictionaries. Replace:

```python
run_id = response["id"]
status = response.get("status")
```

with:

```python
run_id = response.resource_id
status = run.status
```

## Internal lifecycle data

Execution IDs, upload sessions, leases, checkpoint processes, Kubernetes
resources, storage locations, credentials, and background job records are no
longer public. Use projected `status`, `status_message`, attempt monitoring, and
high-level upload/download methods.

`nexusai.http`, `nexusai.storage`, and `nexusai.cas_storage` are no longer
public modules. Applications should use domain clients and high-level transfer
methods. Workload containers use the protected `nexusai._internal` contract.

## CLI output

CLI output now defaults to tables. Add `--output json` for machine-readable
output or `--field <path>` for a scalar. JSON mode never includes ANSI color.

## Retry behavior

Read calls retry transient failures by default. Mutating calls now receive an
automatic `Idempotency-Key` header that remains stable across retries and is
deduplicated by the MLOps API. Pass `RetryPolicy(enabled=False)` to retain
caller-managed retries.
