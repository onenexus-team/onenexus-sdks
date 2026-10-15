# `onenexus-cas-client`

Typed async client for the OneNexus Central Auth Service Customer API (`/api/*`
and `/account/profile`), the Python counterpart of `@onenexus-team/cas-client`.

- `CasClient` (hand-written, in `client.py`) is the flat facade.
- `generated/` holds the committed Microsoft Kiota output produced from
    `specs/cas/openapi.json`. **Do not edit by hand.**
- `onenexus-sdk-core` adapts its credentials to Kiota's HTTPX request adapter.

`CasClient` accepts `base_url`, `credentials`, an optional `context`, and an
optional `http_client`. It does not subclass `ClientBase` or expose its retry
options. The default HTTP client has no general status-code retry middleware;
to configure retries, supply an HTTPX client with Kiota middleware. API errors
use Kiota's generated `ProblemDetails` and `ValidationProblemDetails` models,
or Kiota's fallback `APIError`, rather than the core `PlatformError` subclasses.

The adapter observes response `Date` headers into the context's clock, including
when an HTTP client is supplied. Existing response hooks are preserved. The
caller owns the lifetime of a supplied HTTP client; otherwise `CasClient`
closes its client on context-manager exit.

For `assume_s3_role()`, `base_url` must be the global `https://auth.<domain>` endpoint.
The method keeps global user and service-client tokens on that endpoint;
regional workload tokens use `https://auth.<region>.<domain>/api/AssumeS3Role`.

## Regenerate

From `python/`:

```sh
dotnet tool restore
dotnet tool run kiota generate \
    --language python \
    --class-name CasGeneratedClient \
    --namespace-name onenexus_cas_client.generated \
    --openapi ../specs/cas/openapi.json \
    --output packages/cas-client/src/onenexus_cas_client/generated \
    --clean-output \
    --exclude-backward-compatible \
    --additional-data false \
    --structured-mime-types application/json \
    --log-level none
```

Commit the regenerated `generated/` diff.

## Usage

```python
import asyncio
from datetime import datetime, timedelta, timezone

from onenexus_sdk_core import AccessToken, TokenGrantCredentials
from onenexus_cas_client import CasClient, CreateUserRequest


async def main() -> None:
    credentials = TokenGrantCredentials(
        token=AccessToken(
            access_token="...",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
    )
    async with CasClient(base_url="https://auth.acme.com", credentials=credentials) as cas:
        result = await cas.create_user(
            CreateUserRequest(
                email="a@b.c",
                display_name="A B",
            )
        )
        assert result.user is not None
        print(result.user.user_id)


asyncio.run(main())
```

Mutation methods add `X-Nx1-Idempotency-Key` automatically when required by the
spec. That key stays the same across transport retries of one method call;
calling the method again creates a new key.
