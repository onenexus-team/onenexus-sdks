# .NET package integration tests

Run from the repository root:

```bash
bash scripts/check-dotnet-observability.sh
```

| Check | Evidence |
|---|---|
| Installed NuGet package | A temporary consumer restores the built `.nupkg` through `PackageReference` |
| Log output | Two related attempts and one independent system record |
| Context cleanup | Attempt records preserve the trace; the system record has no trace |
| Negative controls | Wrong trace, missing service and false scenario results fail |

`LogProbe` runs locally with synthetic data. It needs no CAS deployment, credentials, cluster or monitoring backend. Results are saved in `.artifacts/dotnet/<version>/`; the temporary consumer is removed.

Unit tests live in `../unit/` so their project does not compile the integration probe's separate entry point.

End-to-end `raw_tests` belong to the consuming service. See [test ownership](../../../../../docs/logging.md#test-ownership).
