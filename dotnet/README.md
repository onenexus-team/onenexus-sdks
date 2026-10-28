# OneNexus .NET packages

| Package | Purpose |
|---|---|
| [observability](packages/observability/README.md) | Shared `ILogger` provider, trace context and validation rules |

```text
dotnet/
├── Directory.Build.props
└── packages/
    └── observability/
        ├── README.md
        ├── src/
        ├── tests/
        └── raw_tests/
```

Run source, installed-package and raw-log checks from the repository root:

```bash
bash scripts/check-dotnet-observability.sh
```

All packages use the SDK release version. See the [release guide](../docs/logging.md).
