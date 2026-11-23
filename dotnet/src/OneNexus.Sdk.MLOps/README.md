# OneNexus.Sdk.MLOps

A .NET 10 Native AOT compatible client for the OneNexus MLOps service. Pass the service root (for example, `https://mlops.example.com`) and an `IAccessTokenCredential` from `OneNexus.Sdk.Core`.

```csharp
using OneNexus.Sdk.MLOps;
using OneNexus.Sdk.MLOps.Models;

using var client = new MLOpsClient(serviceUrl, credentials);
var page = await client.ListDatasetsAsync(new RpcListDatasetsRequest { Page = 1 }, cancellationToken);
var created = await client.CreateDatasetAsync(new RpcCreateDatasetRequest { Name = "training" },
    idempotencyKey: batchId, cancellationToken: cancellationToken);
```

Methods mirror the public RPC operation names, and models preserve the service's response envelopes. A list returns `Items` and `TotalPages`. For a delete that can return either an asynchronous action (HTTP 202) or no content (HTTP 204), the result is nullable. Catch `OneNexus.Sdk.MLOps.Models.ProblemResponse` for documented service failures; its `Type`, `Detail`, `Instance`, `Errors` and response headers come from the service.

A replayable mutation receives one MLOps `Idempotency-Key` per invocation. Pass an explicit key to repeat the same logical request across calls. To use only health, inference-key validation or platform-key operations, construct the client with the service URL alone. Control-plane operations require CAS credentials. Model discovery, Composer configuration, and WebTools search/fetch accept an explicit platform API key. The invocation proxy and metered web retrieval send a single request, because the service excludes them from its replay cache.

The package uses the public API exported at `specs/mlops/openapi.json`. Regenerate with `bash scripts/generate-dotnet-clients.sh mlops` from the SDK repository root.
