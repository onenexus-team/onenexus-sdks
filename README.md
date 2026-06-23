# OneNexus SDKs

This repository contains the client SDKs that apps use to call OneNexus platform services.

## Client convention & generation
Client SDKs are built to make it easier for customers to interact with OneNexus platform using their programming languages of choice. 
OneNexus APIs generally has RPC-like structure, with each API calls being a POST request
with a request and a response object, for example:

```http
POST /api/CreateTenant HTTP/1.1
Host: cas.acme.com
Authorization: Bearer <access-token>
Content-Type: application/json
X-Api-Version: v1

{
    "tenantId":    "tn_acme",
    "name":        "Acme Inc",
    "clientToken": "01HV8XR4D0YPRNNK8YY8VJ3QK2"
}
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "tenantId":  "tn_acme",
    "name":      "Acme Inc",
    "status":    1,
    "userCount": 0,
    "createdAt": "2026-05-13T10:00:00Z"
}
```

Every operation across every service follows this same wire shape:

- The URL is always `POST /api/<OperationName>` — no path parameters, no nested
  REST routes. The operation name (PascalCase) is the entire routing decision.
- The request body is a single JSON object whose schema is one
  `<OperationName>Request` type in the OpenAPI spec.
- The success response is a single JSON object whose schema is one
  `<OperationName>Response` type. Failure responses use the RFC 9457
  Problem Details envelope.
- `Authorization` carries a CAS-issued bearer token; `X-Api-Version` selects
  the API version. Both are required.

Each SDK translates this calls into the SDK operation API. The specific syntax depends on the language,
but generally speaking, the SDK libraries have the following APIs:
- Create a new "client" object for the service being targeted. Credentials and other options are passed as input.
- Calling operation APIs using language-specific syntax.

For example, the `POST /api/CreateTenant` call above looks like this in **TypeScript**:

```typescript
const cas = new CasClient({
    baseUrl:     'https://cas.acme.com',
  credentials: new TokenGrantCredentials({ /* ... */ }),
});

const request: CreateTenantResquest = {
    tenantId:    'tn_acme',
    name:        'Acme Inc',
    clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
};

const response: CreateTenantResponse = await cas.createTenant(request);
```

And in **Python**:

```python
cas = CasClient(
    base_url="https://cas.acme.com",
  credentials=TokenGrantCredentials(...),
)

response = await cas.create_tenant(
    tenant_id="tn_acme",
    name="Acme Inc",
    client_token="01HV8XR4D0YPRNNK8YY8VJ3QK2",
)
```

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

SDK package versions are specified by the repository-level `VERSION` file.
Python packages use that file as their wheel metadata version, and TypeScript
packages are synchronized to that version before packaging and publishing. When
`VERSION` changes on the `main` branch, the SDK release workflow builds the
Python wheels and TypeScript package tarballs, uploads them as workflow
artifacts, attaches them to the GitHub release tagged `v<VERSION>`, and
publishes the TypeScript SDK packages to GitHub Packages' npm registry.

For local builds and consumption examples, see [`python/README.md`](python/README.md)
and [`ts/README.md`](ts/README.md).

## Credentials systems

Every call into a platform API crosses a trust boundary and must carry a
short-lived bearer token issued by the Central Auth Service (CAS). The
CAS auth architecture defines four scenarios that produce such a token:

| Scenario | Caller | Grant |
|---|---|---|
| 3.1a | A human user via browser / mobile / CLI | Authorization Code + PKCE |
| 3.1b | A customer's backend with a registered keypair | Client Credentials + `private_key_jwt` |
| 3.2  | A platform pod calling another platform service | Client Credentials + K8s SA assertion |
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

Active implementations cache, single-flight concurrent refreshes, and honor
cancellation. The supplied `ClientContext` carries the per-client clock used for
expiry decisions. The transport calls `resolve(...)` before each request and
sets the `Authorization: Bearer <token>` header from the returned
`AccessToken`.

There is no cache-invalidation hook. A target API `401` is retried according to
the transport retry policy; observed server time from the response updates the
client clock, so the next `resolve(...)` evaluates expiry against the server
clock. Early revocation is treated as a terminal identity problem and is allowed
to surface to the application.

The default transport retry policy retries twice for retryable statuses using
exponential backoff with full jitter, capped at 5 seconds per retry. Service
clients expose `retry.limit` and `retry.backoffLimitMs` at construction time.

Two credential errors are part of the contract:

- **`StaleCredentialsError`** — the held token is stale by expiry rules and the
  current credential cannot refresh it itself.
- **`AuthenticationError`** — a refresh or mint attempt was rejected by the
  authentication authority. Retrying the same credential source is not expected
  to recover.

#### `ClientContext` and `Clock`

Each service client owns a `ClientContext`. Today it contains a skew-aware
`Clock` and a `refreshLeewayMs` preemptive refresh window. The HTTP transport
observes the server `Date` header on responses and records it in the clock;
credential implementations call `clock.serverNow()` when deciding whether a
cached access token is near expiry.

The shared `ClientBase` class creates the default context (`SystemClock`) and
the Ky transport for every generated service client. A caller may inject a
custom `ClientContext` when multiple clients should share clock observations,
or pass `refreshLeewayMs` when constructing a client. `TokenGrantCredentials`
also accepts `refreshLeewayMs` as a credential-specific override.

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
    issuer:       "https://cas.example.com",
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
