# Go package integration tests

Run from the repository root:

```bash
bash scripts/check-go-observability.sh
```

| Check | Evidence |
|---|---|
| Installed module | A temporary consumer installs the versioned module ZIP without source replacements |
| Log output | Four JSON records; three share one trace ID |
| Context cleanup | Independent system work has no inherited trace |
| Negative controls | Wrong trace/service, missing field, plain-text output and false scenario results fail |

`log-probe` runs locally with synthetic data. It needs no credentials, cluster or monitoring backend. Results are saved in `.artifacts/go-observability/`; the temporary consumer is removed.

End-to-end `raw_tests` belong to the consuming service. See [test ownership](../../../../docs/logging.md#test-ownership).
