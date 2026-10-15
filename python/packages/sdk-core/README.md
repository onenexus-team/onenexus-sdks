# `onenexus-sdk-core`

Credential primitives, an async HTTP transport, and a Kiota adapter for OneNexus
Python SDKs. The Python counterpart of `@onenexus-team/sdk-core`.

The language-agnostic credential design is documented in
[`../../../README.md`](../../../README.md).

## Design

- **Interfaces are `typing.Protocol`** (PEP 544). `Credentials`, `Clock`, and the
  transport `Transport` are structural protocols — implementations satisfy them
  without inheriting. `Credentials` and `Clock` are `@runtime_checkable`.
- **Async-first, sync-capable credentials.** SDK clients use `resolve()`, while sync-only integrations such as botocore use the same credential object through `resolve_sync()`.
- **Absolute expiry.** `AccessToken.expires_at` is a timezone-aware `datetime`.
- **Server-clock skew correction.** The transport records the server `Date`
  header into the per-client `Clock`, so credential expiry checks use server time.

## Credential types

| Class                                  | Scenario | Behaviour |
| -------------------------------------- | -------- | --------- |
| `TokenGrantCredentials`                | seeded   | Wraps an externally obtained grant; refreshes via refresh token when configured. |
| `PrivateKeyJwtCredentials`             | 3.1b     | Signs `private_key_jwt` client assertions for the client-credentials grant. |
| `WorkloadIdentityFileCredentials`           | 3.2/3.4  | Exchanges a runtime-mounted token file under the custom workload-identity grant. |

All three cache the access token, single-flight concurrent refreshes on their
async path (`asyncio.Lock`) and guard sync refreshes separately, and raise
`StaleCredentialsError` / `AuthenticationError` per the credential contract.

## Building a service client

For a client using the core transport directly, subclass `ClientBase` and bind
operations to `request`. This provides `RetryConfig` and `PlatformError` mapping.
The existing `CasClient` instead uses `create_kiota_request_adapter` with Kiota's
generated request builders and error models; see its
[package README](../cas-client/README.md).

The following example assumes application-defined `CreateThingRequest` and
`CreateThingResponse` types with `to_dict()` and `from_dict()` methods:

```python
from onenexus_sdk_core import ClientBase


class ExampleClient(ClientBase):
    async def create_thing(self, request: CreateThingRequest) -> CreateThingResponse:
        response = await self.request("POST", "/api/CreateThing", json=request.to_dict())
        return CreateThingResponse.from_dict(response.json())
```

```python
import asyncio
from datetime import datetime, timedelta, timezone

from onenexus_sdk_core import AccessToken, TokenGrantCredentials


async def main() -> None:
    credentials = TokenGrantCredentials(
        token=AccessToken(
            access_token="...",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
    )
    async with ExampleClient(base_url="https://auth.acme.com", credentials=credentials) as client:
        ...


asyncio.run(main())
```
