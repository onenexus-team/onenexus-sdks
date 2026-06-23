# `onenexus-sdk-core`

Credential primitives and the async HTTP transport shared by every OneNexus
Python SDK. The Python counterpart of `@onenexus-team/sdk-core`.

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

Subclass `ClientBase` and bind operations to `request`:

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
    async with ExampleClient(base_url="https://cas.acme.com", credentials=credentials) as client:
        ...


asyncio.run(main())
```
