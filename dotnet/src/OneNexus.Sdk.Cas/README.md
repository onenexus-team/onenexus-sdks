# OneNexus.Sdk.Cas

A .NET 10 client for CAS customer operations. The application supplies its CAS URL and credentials. Request and response models come from the committed CAS OpenAPI contract.

```csharp
using OneNexus.Sdk.Cas;
using OneNexus.Sdk.Cas.Models;
using OneNexus.Sdk.Core;

static async Task<CreateUserResponse> InviteAsync(Uri serviceUrl, IAccessTokenCredential credentials, CancellationToken cancellationToken)
{
    using var cas = new CasClient(serviceUrl, credentials);
    return await cas.CreateUserAsync(
        new CreateUserRequest { Email = "member@example.com", DisplayName = "New Member" },
        cancellationToken);
}
```

Reuse a client across calls for the same deployment and identity. Keyed mutations generate a key by default. To replay the same logical request across calls, create a key before the first call and pass it as `idempotencyKey` on every invocation with the same body. A key accepts 16–128 ASCII letters, digits, dots, underscores or hyphens. Automatic retries reuse the key and the serialized body. For role assumption, configure the global `https://auth.<domain>` origin. An opaque token uses the global origin. A regional issuer must use the same scheme and port and a single region under the configured domain. Role assumption pins the resolved token and returns any HTTP 401 immediately.

A list paged by cursor also has a `ListAll…Async` method, such as `ListAllUsersAsync`, that follows `After` through every page with up to 200 items each. Use it with `await foreach`. The request's filters apply to every page. Its `Limit`, `After` and `Before` are ignored, and the request itself is not modified. A cursor that repeats raises `InvalidDataException`. `ListRolesAsync` has no cursor and returns at most 200 roles.

Policy documents use the generated `JsonElement.AdditionalData` dictionary for arbitrary JSON members. A policy returned by `GetPolicyAsync` can supply the document for an update.
