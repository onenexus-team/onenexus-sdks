# OneNexus for .NET 10

| NuGet package | Purpose |
|---|---|
| [OneNexus.Sdk.Core](src/OneNexus.Sdk.Core/README.md) | Credentials, token refresh, transport options and platform errors |
| [OneNexus.Sdk.Cas](src/OneNexus.Sdk.Cas/README.md) | Customer and account operations on the Central Auth Service |
| [OneNexus.Sdk.Cas.Support](src/OneNexus.Sdk.Cas.Support/README.md) | Tenant and account administration through the CAS Support API |
| [OneNexus.Sdk.MLOps](src/OneNexus.Sdk.MLOps/README.md) | Public MLOps operations, including training, datasets, model serving and quotas |
| [OneNexus.Observability](packages/observability/README.md) | Opt-in logging and trace context |

The Core, CAS, CAS Support and MLOps libraries support .NET 10 Native AOT. A consuming executable enables native compilation with `<PublishAot>true</PublishAot>`.

Applications install the service packages at the chosen SDK release version from the OneNexus GitHub NuGet feed. Each service package brings in the shared core. For local development, build the artifacts below and use their output directory as a NuGet source.

Each CAS, CAS Support and MLOps NuGet package includes its matching service specification at `contracts/openapi.json`. Build tools can read this file from the restored package to access operation descriptions and `x-onenexus` metadata for that SDK version.

## Solutions

`OneNexus.Sdk.slnx` contains four libraries in `src/<ProjectName>/` and one matching project per library in `tests/<ProjectName>.Tests/`. Project names, NuGet IDs, and public namespaces use the same spelling. The separate [observability solution](packages/observability/OneNexus.Observability.slnx) owns the logging package, tests, and executable probe. Each solution manages dependencies in its own `Directory.Packages.props`.

## Build, regenerate and test

From the repository root, use the .NET SDK in `global.json`. The clients ship their generated source. Building and installing the packages therefore works independently of the Kiota command-line tool.

```sh
source scripts/dev-env.sh
dotnet build dotnet/OneNexus.Sdk.slnx
dotnet test --solution dotnet/OneNexus.Sdk.slnx
bash scripts/generate-dotnet-clients.sh
bash scripts/check-dotnet-clients.sh
```

Generation uses the pinned Kiota tool in `python/dotnet-tools.json` and the committed CAS, CAS Support and MLOps OpenAPI contracts. The MLOps generator also derives its public methods from the spec. For CAS, add the corresponding facade method after regeneration. The contract suite exercises every operation through the public client. It checks the HTTP route, retry behavior, required headers and response shape. Each package also owns tests for behavior specific to that package.

The client check builds the four client NuGets into `.artifacts/dotnet-clients/<version>/` and runs the same tests in a clean consumer against those files. It also publishes and runs a native executable for the current platform using the packed clients. The native test requires the platform’s Native AOT build tools, including Clang and the zlib development headers on Linux. Run `bash scripts/build-sdk-artifacts.sh dotnet` for the complete release build, including observability. All packages use the repository's SDK release version.
