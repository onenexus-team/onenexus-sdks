#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
if [[ -x "$root/.dotnet/dotnet" ]]; then export PATH="$root/.dotnet:$PATH"; fi
export DOTNET_CLI_HOME="${DOTNET_CLI_HOME:-$root/.dotnet-home}"
export NUGET_PACKAGES="${NUGET_PACKAGES:-$root/.nuget/packages}"
version="${PACKAGE_VERSION:-$(cat VERSION)}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Invalid package version' >&2; exit 1; }
out="${1:-$root/.artifacts/dotnet-clients/$version}"
mkdir -p "$out"
out="$(cd "$out" && pwd)"
solution=dotnet/OneNexus.Sdk.slnx
dotnet restore "$solution" --locked-mode
dotnet test --solution "$solution" --no-restore -c Release
dotnet pack "$solution" --no-restore -c Release -p:Version="$version" -p:PackageOutputPath="$out"

# Run the client test projects in an application workspace with no SDK source or cached OneNexus packages.
consumer="$(mktemp -d)"
trap 'rm -rf "$consumer"' EXIT
mkdir -p "$consumer/dotnet/tests/Shared" "$consumer/specs"
cp global.json "$consumer/"
cp dotnet/Directory.Packages.props "$consumer/dotnet/"
cp dotnet/tests/Shared/*.cs "$consumer/dotnet/tests/Shared/"
cp -R specs/cas specs/cas-support specs/mlops "$consumer/specs/"
export NUGET_PACKAGES="$consumer/packages" ONENEXUS_LOCAL_NUGET="$out"
for project in dotnet/tests/OneNexus.Sdk.*.Tests; do
  mkdir -p "$consumer/$project"
  cp "$project"/*.cs "$project"/*.csproj "$consumer/$project/"
  dotnet restore "$consumer/$project" -p:PackageUnderTest="$version" --configfile "$root/scripts/dotnet-package-probe.NuGet.Config"
  dotnet run --project "$consumer/$project" --no-restore -c Release -p:PackageUnderTest="$version" -- --timeout 2m
done

# Compile and execute a native consumer. Root all SDK assemblies so the compiler also
# checks operations outside the smoke scenario. Use the locally packed NuGets.
probe=dotnet/tests/OneNexus.Sdk.NativeAotProbe
mkdir -p "$consumer/$probe"
cp "$probe"/*.cs "$probe"/*.csproj "$consumer/$probe/"
dotnet publish "$consumer/$probe" --use-current-runtime -c Release -p:PublishAot=true -p:PackageUnderTest="$version" \
  -p:RestoreConfigFile="$root/scripts/dotnet-package-probe.NuGet.Config" -o "$consumer/native"
"$consumer/native/OneNexus.Sdk.NativeAotProbe"
