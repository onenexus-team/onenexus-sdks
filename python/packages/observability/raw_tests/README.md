# Installed-package log probe

Run from an image containing the built wheel. The probe emits three related lifecycle records
(two retry attempts), then one unrelated system record. No business calls or credentials.

```bash
python log_probe.py --environment development --region region-1 \
  --run-id 51386ccb-5346-4e7a-a040-bc32bf742cc1 > logs.ndjson
python log_probe.py --environment development --region region-1 \
  --run-id 51386ccb-5346-4e7a-a040-bc32bf742cc1 --verify logs.ndjson
```

Use a fresh UUID per live run. Stderr reports the run ID and canonical trace ID.

| Step | Development-cluster action | Required result |
|---|---|---|
| 1 | Build approved test image with wheel, locked dependencies and probe | Record image digest, wheel version/hash and contract digest |
| 2 | Run command in an authorized disposable pod in `development-region-1`; use deployed region | Exit 0; four stdout NDJSON records |
| 3 | Capture stdout; filter metadata if container logs merge stderr | `--verify` passes for selected run ID |
| 4 | Query authorized Loki/Grafana by service `observability-package-probe` and emitted trace ID | Three lifecycle logs, correct environment/region/run ID, attempts 1 and 2 |
| 5 | Query by run ID without trace filter | Fourth system record has no trace ID |
| 6 | Inspect stream labels | No per-trace or per-operation ID labels |
| 7 | Remove trace_id from a copied lifecycle record; rerun verification | Nonzero exit |
| 8 | Delete only disposable test resources | Confirm cleanup |

- Follow cluster repository deployment/cleanup approval rules. Never substitute production kubeconfig.
- For JSON bodies, filter with `| json | trace_id="<ID>"`; use the actual deployed stream selector/metadata mapping.
- This validates package output and collection, not MLOps middleware, HTTP propagation, durable business jobs or tenant authorization.
- Local installed-wheel lane runs in CI. Live cluster lane is **NOT RUN** in this package PR.
- MLOps #796 must supply live service evidence before jobs/retries #797 begins.
