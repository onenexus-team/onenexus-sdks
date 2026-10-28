# TypeScript package integration tests

Run from the repository root:

```bash
pnpm --dir ts install --frozen-lockfile
bash scripts/check-typescript-observability.sh
```

| Check | Evidence |
|---|---|
| Installed npm package | A temporary consumer installs the packed artifact |
| Log output | One request, two related attempts and one independent system event |
| Context | Related records share a trace; independent work stays uncorrelated |
| Negative controls | Wrong trace, missing service and false scenario results fail |

`log-probe.mjs` runs locally with synthetic data. It needs no credentials, cluster or monitoring backend. Results are saved in `.artifacts/typescript-observability/`; the temporary consumer is removed.

End-to-end `raw_tests` belong to the consuming service. See [test ownership](../../../../../docs/logging.md#test-ownership).
