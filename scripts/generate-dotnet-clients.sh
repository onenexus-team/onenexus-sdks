#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
# Share the pinned Kiota tool manifest with the Python SDK.
cd "$root/python"
dotnet tool restore
services=(cas cas-support mlops)
if (( $# )); then services=("$@"); fi
for service in "${services[@]}"; do
  spec="../specs/$service/openapi.json"
  namespace=OneNexus.Sdk.Cas
  client=CasGeneratedClient
  if [[ "$service" == cas-support ]]; then
    namespace=OneNexus.Sdk.Cas.Support
    client=CasSupportGeneratedClient
  elif [[ "$service" == mlops ]]; then
    namespace=OneNexus.Sdk.MLOps
    client=MLOpsGeneratedClient
    python3 "$root/scripts/generate-dotnet-mlops.py"
    spec="../dotnet/src/$namespace/obj/kiota/openapi.json"
  elif [[ "$service" != cas ]]; then
    echo "Unknown service: $service" >&2
    exit 1
  fi
  dotnet tool run kiota generate --language CSharp --class-name "$client" \
    --namespace-name "$namespace" --openapi "$spec" \
    --output "../dotnet/src/$namespace/Generated" --clean-output \
    --serializer Microsoft.Kiota.Serialization.Json.JsonSerializationWriterFactory \
    --deserializer Microsoft.Kiota.Serialization.Json.JsonParseNodeFactory \
    --exclude-backward-compatible --structured-mime-types application/json
done
