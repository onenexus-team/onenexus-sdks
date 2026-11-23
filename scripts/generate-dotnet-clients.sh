#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
# Share the pinned Kiota tool manifest with the Python SDK.
cd "$root/python"
dotnet tool restore
for service in cas cas-support; do
  namespace=OneNexus.Sdk.Cas
  client=CasGeneratedClient
  if [[ "$service" == cas-support ]]; then
    namespace=OneNexus.Sdk.Cas.Support
    client=CasSupportGeneratedClient
  fi
  dotnet tool run kiota generate --language CSharp --class-name "$client" \
    --namespace-name "$namespace.Generated" --openapi "../specs/$service/openapi.json" \
    --output "../dotnet/src/$namespace/Generated" --clean-output \
    --exclude-backward-compatible --structured-mime-types application/json
done
