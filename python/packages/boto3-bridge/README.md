# onenexus-boto3

boto3 credential bridge for the OneNexus platform.

It turns OneNexus credentials into **auto-refreshing boto3 credentials**: a
workload or service client authenticates to CAS (e.g. with
`WorkloadIdentityFileCredentials` or `PrivateKeyJwtCredentials`), CAS mints
temporary S3 credentials via `AssumeS3Role`, and botocore refreshes them
automatically shortly before they expire.

## Install

This package lives in the `python/` uv workspace. From `python/`:

```sh
uv sync
```

## Usage

### Workload identity

```python
from onenexus_sdk_core import WorkloadIdentityFileCredentials
from onenexus_boto3 import OneNexusBoto3Bridge, WorkloadIdentityS3Credentials

# 1. The workload identity: a token file CAS exchanges for an access token.
credentials = WorkloadIdentityFileCredentials(
    issuer="https://cas.onenexus.local",
    token_path="/var/run/secrets/onenexus/token",
)

# 2. Bridge it to boto3. Each refresh runs resolve_sync() -> AssumeS3Role.
s3_credentials = WorkloadIdentityS3Credentials(
    cas_base_url="https://cas.onenexus.local",
    role_name="S3ObjectFullAccess",
    credentials=credentials,
    s3_endpoint_url="http://s3.onenexus.local",
)

s3 = OneNexusBoto3Bridge.create_s3_client(s3_credentials)
print(s3.list_buckets())
```

### Service client private-key JWT

```python
import json
from pathlib import Path

import jwt
from onenexus_boto3 import OneNexusBoto3Bridge, WorkloadIdentityS3Credentials
from onenexus_sdk_core import PrivateKeyJwtCredentials

private_jwk = json.loads(Path("service-client-private.jwk.json").read_text())

credentials = PrivateKeyJwtCredentials(
    issuer="https://cas.onenexus.local",
    client_id="<service-client-client-id>",
    signing_key=jwt.PyJWK.from_dict(private_jwk).key,
    signing_key_id=private_jwk["kid"],
    signing_algorithm=private_jwk.get("alg", "ES256"),
)

s3_credentials = WorkloadIdentityS3Credentials(
    cas_base_url="https://cas.onenexus.local",
    role_name="S3ObjectFullAccess",
    credentials=credentials,
    s3_endpoint_url="http://s3.onenexus.local",
)

s3 = OneNexusBoto3Bridge.create_s3_client(s3_credentials)
print(s3.list_buckets())
```

The bridge owns no background event loop. It uses the synchronous credential
resolution path because botocore refreshes credentials synchronously.

## How it works

```
Credentials.resolve_sync()  ->  CAS access token
    -> sync POST /api/AssumeS3Role  ->  temporary S3 creds (+ expiry)
        -> botocore RefreshableCredentials  ->  auto-refresh before expiry
```

The temporary credentials carry the STS expiration, so botocore re-runs the
exchange on its own schedule; callers never manage expiry by hand.
