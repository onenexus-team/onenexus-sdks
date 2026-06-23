# `onenexus-cas-client`

Typed async client for the OneNexus Central Auth Service Customer API (`/api/*`),
the Python counterpart of `@onenexus-team/cas-client`.

- `CasClient` (hand-written, in `client.py`) is the flat facade.
- `generated/` holds the committed Microsoft Kiota output produced from
    `specs/cas/openapi.json`. **Do not edit by hand.**
- Credentials and transport come from `onenexus-sdk-core`.

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
from onenexus_cas_client import CasClient
from onenexus_cas_client.generated.models.create_user_request import CreateUserRequest


async def main() -> None:
    credentials = TokenGrantCredentials(
        token=AccessToken(
            access_token="...",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
    )
    async with CasClient(base_url="https://cas.acme.com", credentials=credentials) as cas:
        result = await cas.create_user(
            CreateUserRequest(
                email="a@b.c",
                display_name="A B",
                client_token="01HV8XR4D0YPRNNK8YY8VJ3QK2",
            )
        )
        print(result.user.user_id)


asyncio.run(main())
```
