# Python package integration tests

Run from the repository root:

```bash
bash scripts/check-python-observability.sh
```

| Check | Evidence |
|---|---|
| Installed wheel | A clean environment imports the built package from site-packages |
| Log output | Three related lifecycle records and one independent system record |
| Retry context | Both attempts retain the trace; the final system record has no trace |
| Negative control | Removing the trace from a correlated record fails validation |

`log_probe.py` runs locally with synthetic data. It needs no container, credentials, cluster or monitoring backend. Temporary captures are cleaned up by the test script.

End-to-end `raw_tests` belong to the consuming service. See [test ownership](../../../../../docs/logging.md#test-ownership).
