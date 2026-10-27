# TypeScript logging raw checks

| Check | Command / expected result |
|---|---|
| Full package validation | From repository root: `bash scripts/check-typescript-observability.sh` |
| Evidence | `.artifacts/typescript-observability/`: tarballs, checksums, adapter observations, four-line log probe, negative controls |
| Installed packages | Same tests run in a temporary consumer using packed artifacts; no source imports |
| Positive probe | One request, two related attempts, one independent system event; correct schema and trace |
| Negative controls | Wrong trace, missing service, false schema observation must fail |

To run the probe manually from a project that installed the two packages:

```bash
node log-probe.mjs emit > probe.ndjson
node log-probe.mjs verify probe.ndjson 11111111111111111111111111111111
```

Copy `log-probe.mjs` into that project first. Use synthetic data only.

**This validates the SDK, not a deployed service.** It needs no cluster credentials and creates no Kubernetes resources.

After Utility adopts a published package, its separate raw tests must:

1. Call the real test gateway and Utility service.
2. Exercise private/public API paths, real durable job retries/restart and concurrent requests.
3. Query Loki/Grafana through authorized access; compare expected service/event sets by canonical ID.
4. Assert no private data, context leaks, duplicate delivery or authorization changes.
5. Record image/config revisions, safe trace IDs, PASS/FAIL/BLOCKED and cleanup.
