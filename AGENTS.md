# AGENTS.md — OneNexus SDKs

Guidance for AI coding agents working in the standalone OneNexus SDK repository.

## Repository shape

- `README.md` documents the language-agnostic SDK architecture and credential model.
- `tests/logging/` owns shared behavior scenarios and the independent result checker.
- Each language logging package owns its runtime validation rules. CI checks those rules and runs the same scenarios across languages.
- `specs/` contains committed OpenAPI specifications used for code generation.
- `python/` is a `uv` workspace for Python SDK packages.
- `ts/` is a `pnpm` workspace for TypeScript SDK packages.
- `go/observability/` is the opt-in Go `slog` and trace-context module. Run `bash scripts/check-go-observability.sh`.
- `dotnet/` contains the self-contained `ILogger` logging package; run `bash scripts/check-dotnet-observability.sh`.

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

## Logging and SDK release checks

```sh
python3 -m unittest discover -s tests/logging -p 'test_*.py'
python3 scripts/test-sdk-release.py
bash scripts/build-sdk-artifacts.sh python
bash scripts/build-sdk-artifacts.sh typescript
bash scripts/build-sdk-artifacts.sh dotnet
bash scripts/build-sdk-artifacts.sh go
```

Use fresh artifact output directories for a full build. Run language checks independently while iterating.
SDK release `vX.Y.Z` assigns `X.Y.Z` to every logging package. Go also needs the automatically created `go/observability/vX.Y.Z` module tag at the same commit. There is no separate logging-contract release.
Never delete or replace already published packages/tags. Publishing still requires explicit user authorization.
Applications consume installed packages, never repository source overrides. Test source and installed artifacts before publication. Shared scenarios must call actual logging/context APIs; passing these checks does not prove live service adoption.
