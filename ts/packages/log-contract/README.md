# OneNexus log contract

| Item | Meaning |
|---|---|
| Package | `@onenexus-team/log-contract` |
| Source | `contracts/log-correlation/` in this repository |
| Build | Generates bundled schema, vectors and manifest; verifies canonical SHA-256 digests |
| Runtime | AJV validates the bundled schema; no download or registry connection |
| Version | New contract packages follow `log-correlation-vX.Y.Z`; SDK releases preserve the reviewed dependency pin |

- Usually installed automatically by `@onenexus-team/observability`.
- Never edit `src/generated/`; builds regenerate it from the canonical contract.
- Updating an application dependency changes its contract only when that package release includes a new contract.
- A new mandatory field must pass shared vectors and all language adapter tests before release.

```ts
import { CONTRACT_VERSION, CONTRACT_DIGEST, validateRecord, parseRecord } from '@onenexus-team/log-contract';

const record = parseRecord(jsonLine);
const errors = validateRecord(record, 'correlated'); // [] or safe error codes
```

| API | Behavior |
|---|---|
| `parseRecord(json)` | Keeps integer timestamps as `bigint`; avoids rounding int64 values |
| `validateRecord(record, profile)` | `common`, `correlated`, or `lifecycle`; stable error codes |
| `encodeRecord(record, profile)` | Validates, then emits compact JSON; exact numeric timestamp |
| `loadContract()` | Fresh copies of manifest, schema and shared cases |

- Use `bigint` for nanosecond timestamps created in JavaScript. Unsafe numeric timestamps are rejected; parse JSON with `parseRecord` to retain exact digits.
- Plain JSON extensions are supported; getters, `toJSON`, cycles, non-finite numbers and malformed Unicode are rejected.
- This Node.js package does not provide a browser logger or an application security boundary.

- [Release and upgrade guide](../../../contracts/log-correlation/release-guide.md): one contract tag builds Python, npm and NuGet packages.
