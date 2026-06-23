# AGENTS.md — OneNexus SDKs

Guidance for AI coding agents working in the standalone OneNexus SDK repository.

## Repository shape

- `README.md` documents the language-agnostic SDK architecture and credential model.
- `specs/` contains committed OpenAPI specifications used for code generation.
- `python/` is a `uv` workspace for Python SDK packages.
- `ts/` is a `pnpm` workspace for TypeScript SDK packages.

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
