# AGENTS.md — OneNexus SDKs

Guidance for AI coding agents working in the standalone OneNexus SDK repository.

## Repository shape

- `README.md` documents the language-agnostic SDK architecture and credential model.
- `contracts/log-correlation/` owns the current schema and shared language-adapter cases.
- `specs/` contains committed OpenAPI specifications used for code generation.
- `python/` is a `uv` workspace for Python SDK packages.
- `ts/` is a `pnpm` workspace for TypeScript SDK packages.
- `dotnet/` contains the generated contract and shared `ILogger` packages; run `bash scripts/check-dotnet-observability.sh`.

## Core rules

1. SDK changes affect downstream apps. Keep changes minimal, versionable, and covered by tests.
2. Apps must consume SDKs through package artifacts/version pins, not by importing source paths.
3. Every new SDK function needs unit tests in the corresponding package `tests/` or `test/` directory.
4. Do not add a new package manager, framework, or third-party dependency unless the existing workspace cannot solve the problem.
5. No secrets in code, config, tests, docs, or commit messages. If you find hardcoded credentials, stop and tell the user.
6. Do not publish packages (`npm publish`, `pnpm publish`, `uv publish`, etc.) unless explicitly asked.

## Common commands

Run Python commands from `python/`:

```sh
uv sync --all-extras
uv run pytest
uv run mypy packages
uv run ruff check .
```

Run TypeScript commands from `ts/`:

```sh
pnpm install
pnpm package
```

## Log contract checks

```sh
bash scripts/check-log-contracts.sh
```

Keep one current schema, vector file and manifest in source. Preserve historical
versions through protected tags and release artifacts; never replace published
assets. Bump the manifest/schema/vector version and recompute digests for a new
contract release. A checker pass proves reported case agreement, not service
adoption. Runtime packages must execute the shared cases through their actual APIs.
