# OneNexus.Sdk.Cas.Support

A .NET 10 client for the CAS Support API. Use credentials authorized for the corresponding administrative operation.

```csharp
using OneNexus.Sdk.Cas.Support;
using OneNexus.Sdk.Cas.Support.Models;
using OneNexus.Sdk.Core;

static async Task<CreateTenantResponse> CreateTenantAsync(Uri serviceUrl, IAccessTokenCredential credentials, CancellationToken cancellationToken)
{
    using var support = new CasSupportClient(serviceUrl, credentials);
    return await support.CreateTenantAsync(
        new CreateTenantRequest { DisplayName = "Example", RootEmail = "admin@example.com", RootDisplayName = "Admin" },
        cancellationToken);
}
```

Reuse the client for subsequent calls. Keyed operations such as `CreateTenantAsync` accept an explicit `idempotencyKey` to reuse with the same request after a timeout. Omit it for a new automatically generated key. The SDK sets required mutation headers, sends an empty JSON object for argumentless S3 administration operations, and returns a plain Task for operations with a 204 response.
