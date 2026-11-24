# OneNexus.Sdk.Core

Shared authentication and HTTP behavior for OneNexus .NET 10 clients. Pass an `IAccessTokenCredential` to either service client.

| Credential | Use |
|---|---|
| `TokenGrantCredentials` | Wrap a CAS bearer token from your application's login flow. Supply a `TokenGrant` containing a refresh token and `OidcOptions` with a client ID to enable refresh. Read `Snapshot` to persist the latest grant after rotation. |
| `PrivateKeyJwtCredentials` | Pass `OidcOptions` with a client ID and Microsoft IdentityModel `SigningCredentials` for the registered key. Set the key's ID and use RS256, PS256 or ES256. |
| `WorkloadIdentityFileCredentials` | Exchange a runtime-projected JWT. The default file is `/var/run/secrets/onenexus/token`. The credential reads it again for each refresh. |

The OAuth issuer belongs on the credential. The service URL belongs on the client. Credentials discover the token endpoint or accept a trusted explicit endpoint. Await `GetTokenAsync` once per call. A fresh cached token completes its `ValueTask<AccessToken>` synchronously. All three credentials share refresh work across callers. Cancellation of one caller stops its wait. An expired token without a refresh grant raises `StaleCredentialsException`.

`SdkClientOptions` accepts a caller-owned HTTP client, a shared `ClientContext`, a timeout and retry limits. Defaults allow two retries, cap retry delays at five seconds, and time out a logical service call after 30 seconds. The credential clock uses Date headers from the service and token endpoint, including rejected responses. Credentials refresh 30 seconds before expiry by default. For tokens obtained from CAS, the refresh window is capped at half the issued lifetime. A 401 can trigger an immediate retry if the credential returns a different bearer token. A server-requested Retry-After longer than the configured maximum returns the original HTTP error immediately. The service URL and token endpoint require HTTPS except for loopback HTTP. The default HTTP transport disables redirects and cookies and supports compressed responses. When supplying a transport for credentials, disable automatic redirects to keep token grant bodies at the intended endpoint.

To add HTTP middleware, set the innermost `DelegatingHandler.InnerHandler` to `SdkClientOptions.CreateDefaultHttpHandler()`. Construct an `HttpClient` from the outer handler and pass it in `SdkClientOptions.HttpClient`. Each handler manages its own connections with a five-minute pooled connection lifetime. Reuse the client across requests and dispose it when you are finished. The SDK sends each retry through this client, so the middleware sees each attempt.

Problem Details responses from every service client raise `PlatformException`, which is an `HttpRequestException`. Use `ProblemType` or `Code` to distinguish conflicts such as `failed_precondition` and `already_exists`. HTTP status, detail, and validation messages grouped by field are available when supplied. `RequestId` and `TraceId` come from the problem body, or else from the `X-Request-ID` and `X-Trace-Id` response headers. An error response without a problem body raises a plain `HttpRequestException` with its status.
