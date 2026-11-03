#!/usr/bin/env bash
# Build, test, then stage the exact package bytes used by the SDK publisher.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
language="${1:?language required}"
version="${2:-$(cat VERSION)}"
[[ "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] || exit 1
export SDK_PACKAGE_VERSION="$version" PACKAGE_VERSION="$version"
export ONENEXUS_LOGGING_SCENARIOS="$root/tests/logging/scenarios.json"
out="$root/.artifacts/sdk/$language"
mkdir -p "$out"
# Callers use a fresh build directory; do not silently include old versions.
[[ -z "$(ls -A "$out")" ]] || { echo "Output already exists: $out" >&2; exit 1; }
case "$language" in
  python)
    (cd python && uv sync --all-extras --frozen && uv run --frozen pytest -q)
    bash scripts/build-python-wheels.sh --version "$version" --out-dir "$out"
    # uv adds an output-directory marker; only package bytes belong in the release.
    rm -f "$out/.gitignore"
    SDK_CHECK_WHEEL="$out/onenexus_observability_python-$version-py3-none-any.whl" bash scripts/check-python-observability.sh
    ;;
  typescript)
    pnpm --dir ts install --frozen-lockfile
    pnpm --dir ts package
    bash scripts/check-typescript-observability.sh
    cp ".artifacts/typescript-observability/onenexus-team-observability-$version.tgz" "$out/"
    for name in sdk-core cas-client cas-support-client; do
      cp "ts/.local-packages/onenexus-team-$name-$version.tgz" "$out/"
    done
    ;;
  dotnet)
    bash scripts/check-dotnet-observability.sh
    cp ".artifacts/dotnet/$version/OneNexus.Observability.$version.nupkg" "$out/"
    ;;
  go)
    bash scripts/check-go-observability.sh
    cp ".artifacts/go-observability/observability-go-v$version.zip" "$out/"
    ;;
  *) echo 'Unknown SDK language' >&2; exit 1 ;;
esac
python3 scripts/verify-sdk-artifacts.py "$language" "$version" "$out"
