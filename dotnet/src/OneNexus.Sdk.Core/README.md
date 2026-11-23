# OneNexus.Sdk.Core

Shared authentication and HTTP behavior for OneNexus .NET 10 clients. Pass an `IAccessTokenCredential` to either service client.

| Credential | Use |
|---|---|
| `TokenGrantCredentials` | Wrap a CAS bearer token from your application's login flow. Supply a `TokenGrant` containing a refresh token and `OidcOptions` with a client ID to enable refresh. Read `Snapshot` to persist the latest grant after rotation. |
| `PrivateKeyJwtCredentials` | Pass `OidcOptions` with a client ID and Microsoft IdentityModel `SigningCredentials` for the registered key. Set the key's ID and use RS256, PS256 or ES256. |
| `WorkloadIdentityFileCredentials` | Exchange a runtime-projected JWT. The default file is `/var/run/secrets/onenexus/token`. The credential reads it again for each refresh. |

The OAuth issuer belongs on the credential. The service URL belongs on the client. Credentials discover the token endpoint or accept a trusted explicit endpoint. Await `GetTokenAsync` once per call. A fresh cached token completes its `ValueTask<AccessToken>` synchronously. All three credentials share refresh work across callers. Dispose the credential after its clients have finished using it. Cancellation of one caller stops its wait. An expired token without a refresh grant raises `StaleCredentialsException`.

`SdkClientOptions` accepts a caller-owned HTTP client, a shared `ClientContext`, a timeout and retry limits. Defaults allow two retries, cap backoff at five seconds, and time out a logical service call after 30 seconds. The credential clock uses service Date headers and refreshes 30 seconds before expiry. The default HTTP transport disables redirects and cookies. When supplying a transport for credentials, disable automatic redirects to keep token grant bodies at the intended endpoint.

CAS Problem Details responses raise `PlatformException`. Use `ProblemType` or `Code` to distinguish conflicts such as `failed_precondition` and `already_exists`. HTTP status, validation messages, detail and request ID are available when supplied.
