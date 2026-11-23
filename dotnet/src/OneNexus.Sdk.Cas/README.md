# OneNexus.Sdk.Cas

A .NET 10 client for CAS customer operations. The application supplies its CAS URL and credentials. Request and response models come from the committed CAS OpenAPI contract.

```csharp
using OneNexus.Sdk.Cas;
using OneNexus.Sdk.Cas.Generated.Models;
using OneNexus.Sdk.Core;

static async Task<CreateUserResponse> InviteAsync(Uri serviceUrl, IAccessTokenCredential credentials, CancellationToken cancellationToken)
{
    using var cas = new CasClient(serviceUrl, credentials);
    return await cas.CreateUserAsync(
        new CreateUserRequest { Email = "member@example.com", DisplayName = "New Member" },
        cancellationToken);
}
```

Reuse a client across calls for the same deployment and identity. Each mutation that requires an idempotency key gets a new key per invocation. Automatic retries reuse that key and the serialized body. For role assumption, configure the global `https://auth.<domain>` origin. An opaque token uses the global origin. A regional issuer must use the same scheme and port and a single region under the configured domain. Role assumption pins the resolved token and returns any HTTP 401 immediately.

Policy documents use the generated `JsonElement.AdditionalData` dictionary for arbitrary JSON members. A policy returned by `GetPolicyAsync` can supply the document for an update.
