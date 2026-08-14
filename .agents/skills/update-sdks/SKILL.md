---
name: update-sdks
description: Regenerate and update the OneNexus Python and TypeScript SDKs after changes to the committed CAS or CAS Support OpenAPI specs, including facade wrappers, generated documentation, required headers such as idempotency keys, retry-safe behavior, tests, builds, and package validation. Use for changes under specs/cas/openapi.json or specs/cas-support/openapi.json.
---

# Update OneNexus SDKs

Update generated clients and hand-written facades from the canonical specs:

- `specs/cas/openapi.json`
- `specs/cas-support/openapi.json`

## 1. Establish the current architecture

1. Check the branch and working tree. Preserve all user spec edits; never reset or rewrite unrelated changes.
2. Read each affected package's `generate` script and generator config before acting.
   - `main` may use Orval/Ky for TypeScript.
   - Preview branches may use Kiota for TypeScript.
   - Treat checked-in configuration as authoritative; never migrate generators as part of regeneration.
3. Generate only existing packages. There is currently no Python CAS Support package; report that limitation instead of inventing one unless explicitly requested.
4. Do not add dependencies, publish, commit, or edit generated files by hand.

## 2. Inventory contract changes

Compare each modified spec with `HEAD` and identify:

- added/removed `operationId`s;
- changed request bodies, responses, required fields, and types;
- added required parameters or headers;
- removed compatibility fields such as `requestId` or `clientToken`;
- stale summaries/descriptions that contradict the new schema.

Correct an obviously contradictory source description only when necessary, then regenerate. Keep all other spec edits intact.

## 3. Regenerate

Run commands from the repository root through the development environment.

### Python CAS (Kiota)

```sh
bash -lc 'source scripts/dev-env.sh && env --chdir=python dotnet tool run kiota generate --language python --class-name CasGeneratedClient --namespace-name onenexus_cas_client.generated --openapi ../specs/cas/openapi.json --output packages/cas-client/src/onenexus_cas_client/generated --clean-output --exclude-backward-compatible --additional-data false --structured-mime-types application/json --log-level none'
```

### TypeScript CAS and CAS Support

Use the package scripts so the checked-out branch selects Orval or Kiota:

```sh
bash -lc 'source scripts/dev-env.sh && pnpm --dir ts --filter @onenexus-team/cas-client run generate && pnpm --dir ts --filter @onenexus-team/cas-support-client run generate'
```

Regenerate only the affected service when only one canonical spec changed.

## 4. Update the public facades

Generated code owns wire types and request builders; facades own the ergonomic API.

- Python CAS: `python/packages/cas-client/src/onenexus_cas_client/client.py`
- Python exports: `python/packages/cas-client/src/onenexus_cas_client/__init__.py`
- TypeScript CAS: `ts/packages/cas-client/src/client.ts`
- TypeScript CAS Support: `ts/packages/cas-support-client/src/client.ts`

For every added operation:

1. Add a documented flat facade method.
2. Export its public request/response types consistently with the package.
3. Apply all generated signature changes and remove obsolete body fields from examples/tests.
4. Add a unit test for the new public method.

Do not expose transport internals or generated grouped clients through the facade.

## 5. Required idempotency headers

When an operation requires `X-Nx1-Idempotency-Key`, callers must not create it.

1. Generate one key per logical facade invocation, matching `^[a-zA-Z0-9_.-]{16,128}$`.
   - Python: `uuid4().hex` in a `RequestConfiguration` header.
   - TypeScript: `globalThis.crypto.randomUUID()` passed through the generated header argument/configuration.
   - On Orval branches, enable `headers: true` in the affected `orval.config.ts` so required header types/signatures are generated.
2. Create the key before entering transport or retry middleware. Never generate it in a per-attempt hook.
3. Pass the same request/header object into Kiota or Ky so all automatic retries reuse the key.
4. A separate facade invocation is a new logical request and should receive a new key.
5. Apply this to every operation identified from the spec, not only newly added operations.

Add focused tests proving:

- a valid header is added without a caller argument;
- the generator is called once per facade invocation;
- all retry attempts receive the identical key;
- removed idempotency fields are absent from serialized bodies.

Use a retryable response supported by the active transport; do not assume Kiota and Ky retry the same status set.

## 6. Validate

Do not use editor diagnostics. Build and test instead.

```sh
bash -lc 'source scripts/dev-env.sh && uv --directory python sync --all-extras --frozen && uv --directory python run pytest'
bash -lc 'source scripts/dev-env.sh && pnpm --dir ts -r run build && pnpm --dir ts -r run test'
```

Run package lint/typecheck scripts when changes affect their source contracts. If artifact validation is needed, read the literal tracked `VERSION` and run:

```sh
bash -lc 'source scripts/dev-env.sh && bash scripts/build-python-wheels.sh --version <X.Y.Z>'
```

Never publish.

Finally:

- verify generated code reflects every changed operation/schema;
- search wrappers and generated docs for removed field names;
- run `git diff --check` and `git --no-optional-locks status --short`;
- if Kiota emits known trailing whitespace or generated deprecation warnings, report them rather than hand-editing generated files;
- confirm build artifacts are ignored and `VERSION` was not unintentionally changed.

Report regenerated services, facade/signature changes, idempotency behavior, test/build results, and any missing language package.