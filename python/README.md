# `python/` — Python SDKs

`uv` workspace for the OneNexus platform Python client SDKs.

The credential object system that underpins every client is documented in
[`../README.md`](../README.md). This workspace is the Python counterpart of
[`../ts/`](../ts/); it follows the same language-agnostic credential design but
uses idiomatic, modern, async Python (`asyncio`, `httpx`, `typing.Protocol`,
timezone-aware `datetime`).

## Packages

| Package             | Description                                                                                                                                     |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `onenexus-sdk-core` | Credential primitives (`AccessToken`, `Credentials`, `ClientContext`), `ClientBase`, an `httpx`-based async transport, RFC 9457 error mapping. |
| `onenexus-cas-client` | Kiota-generated async client for the CAS Customer API, with a small facade wired to `onenexus-sdk-core` credentials. |
| `onenexus-boto3` | boto3 credential bridge that exchanges OneNexus credentials for temporary S3 credentials through CAS. |

## Prerequisites

- Python >= 3.11
- [`uv`](https://docs.astral.sh/uv/)

## Commands

Run from `python/`:

```sh
uv sync --all-extras          # create the venv and install workspace + dev deps
uv sync --all-extras --group examples  # also install example-only deps such as boto3
uv run pytest                 # run the test suite
uv run mypy packages          # type-check (strict)
uv run ruff check .           # lint
bash ../scripts/build-python-wheels.sh --version 0.0.5  # build release wheels for a given version

# regenerate the CAS client from the OpenAPI spec
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

Without `uv`:

```sh
python -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -e 'packages/sdk-core[dev]' boto3
.venv/bin/pytest packages/sdk-core
```

## Release wheels

Local Python wheel builds pass the package version explicitly via
`--version`. Publishing a GitHub release with a tag such as `v0.0.6`
triggers the SDK release workflow, which derives `0.0.6` from the tag and
builds wheels for:

- `onenexus-sdk-core`
- `onenexus-cas-client`
- `onenexus-boto3`

The workflow runs in parallel with the TypeScript release job, caches uv package
restores, uploads the wheels as a workflow artifact, and attaches them to the
GitHub release that triggered the workflow.

Consumers can install from the release asset URLs directly. For example, for
version `0.0.1`:

```txt
onenexus-sdk-core @ https://github.com/<owner>/<repo>/releases/download/v0.0.1/onenexus_sdk_core-0.0.1-py3-none-any.whl
onenexus-cas-client @ https://github.com/<owner>/<repo>/releases/download/v0.0.1/onenexus_cas_client-0.0.1-py3-none-any.whl
onenexus-boto3 @ https://github.com/<owner>/<repo>/releases/download/v0.0.1/onenexus_boto3-0.0.1-py3-none-any.whl
```

Include the internal OneNexus dependencies your selected package needs. For
example, `onenexus-cas-client` needs `onenexus-sdk-core`, and `onenexus-boto3`
needs both `onenexus-sdk-core` and `onenexus-cas-client`.
