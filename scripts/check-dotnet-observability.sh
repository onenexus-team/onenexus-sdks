#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
if [[ -x "$root/.dotnet/dotnet" ]]; then export PATH="$root/.dotnet:$PATH"; fi
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
export DOTNET_CLI_HOME="${DOTNET_CLI_HOME:-$root/.dotnet-home}"
export NUGET_PACKAGES="${NUGET_PACKAGES:-$root/.nuget/packages}"
version="${PACKAGE_VERSION:-$(cat VERSION)}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Invalid package version' >&2; exit 1; }
out="$root/.artifacts/dotnet/$version"
mkdir -p "$out"
manifest=contracts/log-correlation/manifest.json
contract_version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$manifest")"
digest="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$manifest")"
checker=contracts/log-correlation/check_contract.py
python3 "$checker" verify --version "$contract_version" --expected-digest "$digest"
project=dotnet/tests/OneNexus.Observability.Tests
dotnet restore "$project" --locked-mode
ONENEXUS_CONTRACT_RESULTS="$out/source-results.json" dotnet run --project "$project" --no-restore -c Release -- --timeout 2m
python3 "$checker" check-results --version "$contract_version" --expected-digest "$digest" --results "$out/source-results.json"
dotnet pack dotnet/src/OneNexus.LogContract --no-restore -c Release -p:Version="$version" -o "$out"
dotnet pack dotnet/src/OneNexus.Observability --no-restore -c Release -p:Version="$version" -o "$out"

# A separate consumer directory and package cache prove that .nupkg dependency metadata works.
consumer="$(mktemp -d)"
trap 'rm -rf "$consumer"' EXIT
cp global.json "$consumer/global.json"
cp dotnet/Directory.Build.props "$consumer/Directory.Build.props"
cp dotnet/README.md "$consumer/README.md"
cp -R dotnet/tests/OneNexus.Observability.Tests "$consumer/tests"
rm -rf "$consumer/tests/bin" "$consumer/tests/obj" "$consumer/tests/TestResults"
cp -R dotnet/raw_tests/LogProbe "$consumer/probe"
rm -rf "$consumer/probe/bin" "$consumer/probe/obj"
cache="$consumer/packages"
dotnet restore "$consumer/tests" -p:Version="$version" -p:PackageUnderTest="$version" --packages "$cache" --source "$out" --source https://api.nuget.org/v3/index.json --force-evaluate
ONENEXUS_CONTRACT_RESULTS="$out/installed-results.json" dotnet run --project "$consumer/tests" --no-restore -c Release -p:Version="$version" -p:PackageUnderTest="$version" -- --timeout 2m
python3 "$checker" check-results --version "$contract_version" --expected-digest "$digest" --results "$out/installed-results.json"
# Deliberately wrong observation must fail the language-neutral checker.
python3 - "$out/installed-results.json" "$out/rejected-results.json" <<'PY'
import json, sys
result = json.load(open(sys.argv[1]))
next(item for item in result['results'] if item.get('errors'))['errors'] = []
with open(sys.argv[2], 'w') as stream:
    json.dump(result, stream)
PY
if python3 "$checker" check-results --version "$contract_version" --expected-digest "$digest" --results "$out/rejected-results.json" > "$out/negative-check.log" 2>&1; then
  echo 'Negative control unexpectedly accepted' >&2; exit 1
fi
dotnet restore "$consumer/probe" -p:Version="$version" -p:PackageUnderTest="$version" --packages "$cache" --source "$out" --source https://api.nuget.org/v3/index.json
dotnet build "$consumer/probe" --no-restore -c Release -p:Version="$version" -p:PackageUnderTest="$version"
probe="$consumer/probe/bin/Release/net10.0/LogProbe.dll"
dotnet "$probe" emit > "$out/probe.ndjson"
python3 - "$out/probe.ndjson" "$out/correlated.ndjson" <<'PY'
import json, sys
lines = open(sys.argv[1]).readlines()
records = [json.loads(line) for line in lines]
assert len(records) == 3 and 'trace_id' not in records[-1]
assert [row['attempt'] for row in records[:2]] == [1, 2]
with open(sys.argv[2], 'w') as stream:
    stream.writelines(lines[:2])
PY
trace=11111111111111111111111111111111
dotnet "$probe" verify "$out/correlated.ndjson" "$trace" development region-1 dotnet-package-probe
if dotnet "$probe" verify "$out/correlated.ndjson" 33333333333333333333333333333333 development region-1 dotnet-package-probe > "$out/raw-negative.log" 2>&1; then
  echo 'Wrong trace unexpectedly accepted' >&2; exit 1
fi
if dotnet "$probe" verify "$out/correlated.ndjson" "$trace" development region-1 missing-service > "$out/raw-missing-service.log" 2>&1; then
  echo 'Missing service unexpectedly accepted' >&2; exit 1
fi
python3 - "$out" <<'PY'
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1])
with (root / 'SHA256SUMS').open('w') as stream:
    for path in sorted(root.glob('*.nupkg')):
        stream.write(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n')
PY
echo "PASS: source, installed packages, shared contract, raw log checker and negative controls. Artifacts: $out"
