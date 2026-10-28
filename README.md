# OneNexus SDKs

## Shared logging

Each language has one self-contained logging package: Python, TypeScript, Go and .NET.
All use SDK release `vX.Y.Z`; no separate contract release or dependency is needed.

| Language | Logging package |
|---|---|
| Python | `onenexus-observability-python` |
| TypeScript | `@onenexus-team/observability` |
| Go | `github.com/onenexus-team/onenexus-sdks/go/observability` |
| .NET | `OneNexus.Observability` |

[Release, upgrade and validation guide](docs/logging.md).
Shared inputs and expected results live in `tests/logging/scenarios.json`.
Each language tests its real implementation against those cases, both from source and as an installed package.

## Install packages from GitHub Packages

TypeScript SDK packages are published to the OneNexus GitHub Packages npm
registry. To install them from a consuming application, configure npm for the
`@onenexus-team` scope before running your package manager.

Add your GitHub personal access token and scope mapping to your home `.npmrc`
(`~/.npmrc`):

```ini
@onenexus-team:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=<YOUR_GITHUB_PAT>
always-auth=true
```

Use a personal access token with `read:packages` access; if the package or
repository is private, the token may also need repository read access. Do not
commit token values to source control.

Then install the packages normally:

```sh
pnpm add @onenexus-team/sdk-core @onenexus-team/cas-client
pnpm add @onenexus-team/cas-support-client
```

Python SDK packages are distributed as wheel assets on GitHub releases rather
than through the npm registry. See [`python/README.md`](python/README.md) for
the direct wheel URL format.

This repository contains the client SDKs that apps use to call OneNexus platform services.

## Client convention & generation

The SDKs expose typed operations for OneNexus services. CAS customer operations
usually use `POST /api/<OperationName>` with a JSON request and response, for example:

```http
POST /api/CreateUser HTTP/1.1
Host: auth.acme.com
Authorization: Bearer <access-token>
Content-Type: application/json
X-Nx1-Idempotency-Key: 0193fabc-1234-7def-abcd-1234567890ab

{
    "email": "a@b.c",
    "displayName": "A B"
}
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "user": {
        "userId": "0193fabc-1234-7def-abcd-1234567890ab",
        "userUri": "onenexus:user/0193fabc-1234-7def-abcd-1234567890ab",
        "tenantId": "0193fabc-1234-7def-abcd-1234567890ac",
        "email": "a@b.c",
        "displayName": "A B",
        "emailConfirmed": false,
        "createdAt": "2026-05-13T10:00:00Z"
    }
}
```

The committed OpenAPI specs define each operation's path, request, response, and
required headers. CAS support operations use `/support-api/*`, and account
profile updates use `/account/profile`. The MLOps spec uses REST routes with path
and query parameters; no MLOps SDK package is implemented here yet.

CAS failures use RFC 9457 Problem Details. Successful operations usually return
JSON, but some, such as `ResendUserInvitation`, return no body. Authenticated
operations require a CAS bearer token; `AcceptInvitation` is anonymous in the
API contract, although the SDK client constructors still require credentials.
The current CAS specs and generated clients do not use `X-Api-Version`.

Mutation operations that require `X-Nx1-Idempotency-Key` receive a new key from
the hand-written client wrapper. The same key is retained for transport retries
within that call. A separate method invocation gets a new key. There is no
`clientToken` request-body field for these operations.

Applications construct a client with a service URL and credentials, then call
its typed methods. This **TypeScript** function performs the request above using
credentials supplied by the application:

```typescript
import { CasClient, type CreateUserRequest, type CreateUserResponse } from '@onenexus-team/cas-client';
import type { Credentials } from '@onenexus-team/sdk-core';

async function inviteUser(credentials: Credentials): Promise<CreateUserResponse> {
    const cas = new CasClient({ baseUrl: 'https://auth.acme.com', credentials });
    const request: CreateUserRequest = { email: 'a@b.c', displayName: 'A B' };
    return await cas.createUser(request);
}
```

And in **Python**:

```python
from onenexus_cas_client import CasClient, CreateUserRequest, CreateUserResponse
from onenexus_sdk_core import Credentials


async def invite_user(credentials: Credentials) -> CreateUserResponse:
    async with CasClient(base_url="https://auth.acme.com", credentials=credentials) as cas:
        return await cas.create_user(CreateUserRequest(email="a@b.c", display_name="A B"))
```

Tenant creation belongs to the TypeScript `CasSupportClient.createTenant()`
operation at `/support-api/CreateTenant`. Its request contains `tenantSlug`,
`displayName`, `rootEmail`, and `rootDisplayName`. There is currently no Python
CAS Support package.

### OpenAPI & Code generation
To make client development quick, we utilize OpenAPI specs and generator tools to generate client SDK for the services.
The OpenAPI specs are published at `specs/<service-name>/openapi.json`.
The client SDK code lives under each language workspace, such as `python/` and `ts/`.
For each language, there is a "core" library that implements shared logic such as credentials, transports, resiliency etc.
and service-specific client library package. 
Refer to README.md file in each language for instructions on how to generate & build the code. 

## Development environment

This repository includes a direnv-compatible activation script for a repo-local
toolchain. On activation it installs the pinned .NET SDK into `.dotnet/`,
installs the pinned Node.js runtime under `.tools/`, installs the pinned pnpm
version into that local Node.js installation, installs the pinned `uv` binary
into `.tools/uv/`, and exports the environment variables needed by the Python
and TypeScript workspaces.

Install and configure direnv on Ubuntu/Debian with bash:

```sh
sudo apt install direnv
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
exec bash
```

Install and configure direnv on macOS with Homebrew and zsh:

```sh
brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
exec zsh
```

Then allow this repository's environment file once:

```sh
direnv allow
```

After that, entering the repository activates the environment automatically.
Without direnv, source the same script manually:

```sh
source scripts/dev-env.sh
```

The script sets `DOTNET_HOME` and `DOTNET_ROOT` to the repository's `.dotnet/`
directory, keeps NuGet packages under `.nuget/`, and keeps uv state under
`.uv-cache/`. Node.js, pnpm, Corepack state when available, and npm caches stay
under `.tools/`. The .NET SDK version is read from `global.json`, the Node.js
version is read from `.node-version`, the pnpm version is read from
`ts/package.json`, and the `uv` version is pinned in `scripts/dev-env.sh`. They
can be overridden with `ONENEXUS_DOTNET_SDK_VERSION`, `ONENEXUS_NODE_VERSION`,
`ONENEXUS_PNPM_VERSION`, and `ONENEXUS_UV_VERSION`.

## Publishing SDK packages

Local SDK versions come from `VERSION`. Publishing a GitHub Release `vX.Y.Z`
builds and tests every language before any SDK package is published.

| Package | Destination |
|---|---|
| Python SDKs and logging wheel | GitHub Release assets |
| TypeScript SDKs and logging package | GitHub npm registry and Release assets |
| .NET logging package | GitHub NuGet registry and Release asset |
| Go logging module | Automatic `go/observability/vX.Y.Z` tag at the SDK commit and Release ZIP |

PR/main checks use the same build workflow without publishing. Existing releases are retained.
See the [release guide](docs/logging.md) for failure recovery and service validation.

For local builds and consumption examples, see [`python/README.md`](python/README.md)
and [`ts/README.md`](ts/README.md).

## Credentials systems

Authenticated platform API calls carry a short-lived bearer token issued by
the Central Auth Service (CAS). The auth architecture defines these scenarios:

| Scenario | Caller | Grant |
|---|---|---|
| 3.1a | A human user via browser / mobile / CLI | Authorization Code + PKCE |
| 3.1b | A customer's backend with a registered keypair | Client Credentials + `private_key_jwt` |
| 3.2  | A platform pod calling another platform service | Custom workload-identity grant with a runtime-mounted token |
| 3.3  | A platform service acting on behalf of a user | Token Exchange (RFC 8693) |
| 3.4  | A customer workload running on the platform | Same mechanics as 3.2, tenant-scoped at CAS |

The credential system gives apps **one mental model and one extension point**
for the grant patterns currently exposed through the SDK. App authors pick the
right credential object for their situation; the SDK does the rest. Interactive
auth flows are owned by login libraries and then handed to the SDK as token
grants.

---

### Core concepts

The model has three shared pieces: a narrow **access-token value**, a
**credential producer**, and a per-client **context**.

#### `AccessToken` — the API value

`AccessToken` is a plain, immutable value carrying only what is needed to call
OneNexus APIs: the bearer token string, token type, and absolute expiry time.
It has **no behavior** and deliberately does not carry grant metadata such as
refresh token, ID token, or scopes.

Design note: **expiry is absolute** (`expiresAt`), not relative (`expires_in`).
Absolute timestamps are unambiguous across process restarts, log records, and
clock observations; relative durations are not.

#### `TokenGrantCredentials` — externally obtained grants

`TokenGrantCredentials` is the credential used when the application already has
a token grant from CAS or from an external login library. It owns the access
token plus optional grant metadata (`refreshToken`, `idToken`, `scopes`). If it
has enough refresh-token configuration, it refreshes transparently when the
access token is near expiry. If the access token is stale and cannot be
refreshed, it raises `StaleCredentialsError`.

Interactive Authorization Code + PKCE is handled outside the service SDKs, for
example by `oidc-client-ts` in TypeScript browser applications. The resulting
grant can be wrapped in `TokenGrantCredentials`; there is no separate
authorization-code credential type in the service SDKs.

#### `Credentials` — the producer interface

`Credentials` is the interface every credential source implements:

```typescript
resolve(context: ClientContext, signal?: AbortSignal): Promise<AccessToken>
```

Active implementations cache tokens and coordinate concurrent refreshes so
callers share one refresh. `ClientContext` supplies the clock used for expiry
decisions. Python credentials expose both async `resolve(context)` and
`resolve_sync(context)` for synchronous integrations such as boto3, with separate
locks for async and sync refreshes.

TypeScript service calls accept an `AbortSignal` for the API request. Built-in
credential implementations currently ignore that signal during token discovery
and refresh, so cancellation does not stop token acquisition. Python async
credentials use normal asyncio task cancellation.

There is no credential cache-invalidation hook. Resolving again can refresh a
token that has become stale, but does not force replacement of a still-live token
that the server has revoked.

TypeScript clients use the shared Ky transport. Its default policy retries twice
for statuses `401`, `408`, `429`, `500`, `502`, `503`, and `504`, with exponential
backoff and full jitter capped at 5 seconds. Constructors expose `retry.limit`
and `retry.backoffLimitMs`. `AssumeS3Role` resolves one token for both routing and
authorization and does not retry `401` responses.

Python `CasClient` uses Kiota's request adapter with HTTPX and generated error
models. It does not use Python `ClientBase` or expose the TypeScript retry
options. Its default HTTP client has no general status-code retry middleware;
callers can supply a configured `http_client`. Python `ClientBase` is a separate
core building block with `RetryConfig` and platform error mapping.

Two credential errors are part of the contract:

- **`StaleCredentialsError`** — the held token is stale by expiry rules and the
  current credential cannot refresh it itself.
- **`AuthenticationError`** — a refresh or mint attempt was rejected by the
  authentication authority. Retrying the same credential source is not expected
  to recover.

#### `ClientContext` and `Clock`

Each service client owns a `ClientContext` containing a clock corrected by
observed server time and a preemptive refresh window, defaulting to 30 seconds.
TypeScript uses `clock.serverNow()` and `refreshLeewayMs`; Python uses
`clock.server_now()` and a `timedelta` named `refresh_leeway`. The TypeScript
transport and Python Kiota adapter record response `Date` headers in this clock.

TypeScript `ClientBase` creates the context and Ky transport. Its constructors
accept `context` and a `refreshLeewayMs` override. Python `CasClient` accepts
`context=ClientContext(refresh_leeway=timedelta(...))` and creates its Kiota
adapter separately. Both languages' `TokenGrantCredentials` also accept a
credential-specific refresh-window override. Clients can share a context to
share clock observations.

---

#### The concrete credential types

The currently supported credential types are:

- **`TokenGrantCredentials`** — wraps an externally obtained token grant and,
  when configured with a refresh token plus issuer/client metadata, refreshes
  it transparently.

- **`PrivateKeyJwtCredentials`** — Scenario 3.1b. Holds a private key
  registered with CAS, signs short-lived client assertions for the Client
  Credentials grant, and caches the resulting access token.

- **`WorkloadIdentityFileCredentials`** — Scenarios 3.2 and 3.4. Reads a
  runtime-mounted identity token from disk on each CAS exchange (on Kubernetes,
  the projected ServiceAccount token), presents it under the custom workload-identity
  grant, and caches the resulting access token until shortly before expiry.

Scenario 3.3 token exchange remains part of the auth architecture, but there is
no token-exchange credential type in the SDK yet. It will be added when the CAS
token-exchange contract is ready to expose through the client libraries.

### Use cases (pseudocode)

The pseudocode below is illustrative. Field names, constructor shapes, and
imports are not fixed by this document.

#### Scenario 3.1a — interactive browser flow
Please use https://github.com/authts/oidc-client-ts library for this flow. 

#### Scenario 3.1b — customer backend with a registered keypair

```typescript
let credentials = new PrivateKeyJwtCredentials({
    issuer:       "https://auth.example.com",
    clientId:     "acme-overnight-batch",
    audience:     "inference-api",
    scopes:       ["inference:run"],
    signingKey:   loadPrivateKey("/etc/secrets/acme.pem"),
    signingKeyId: "acme-2025-01",
})

let inference = new InferenceClient({ baseUrl: ..., credentials })
```

#### Scenario 3.2 — pod calling another platform service

```typescript
let credentials = new WorkloadIdentityFileCredentials({
    issuer:    env.CAS_ISSUER,
    tokenPath: "/var/run/secrets/onenexus/token",
    audience:  "datastore-api",
    scopes:    ["datastore:read"],
})

let datastore = new DatastoreClient({
    baseUrl:     env.DATASTORE_URL,
    credentials: credentials,
})

await datastore.query(...)
```

#### Scenario 3.3 — on-behalf-of a user

Token exchange is not exposed as a credential type yet. Until CAS's RFC 8693
surface is ready for SDK consumption, services that need on-behalf-of behavior
should use the service-specific CAS API/flow documented by the auth platform
team rather than constructing SDK credentials directly.


### Shared logging

Python, TypeScript, Go and .NET logging packages share the SDK release version.
See [usage, validation and releases](docs/logging.md).
