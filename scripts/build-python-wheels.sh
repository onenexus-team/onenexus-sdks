#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(tr -d '[:space:]' < "$repo_root/VERSION")"
out_dir="${1:-$repo_root/python/dist}"

case "$out_dir" in
    /*) ;;
    *) out_dir="$(pwd)/$out_dir" ;;
esac

if [[ -z "$version" ]]; then
    printf 'VERSION must not be empty\n' >&2
    exit 1
fi

rm -rf "$out_dir"
mkdir -p "$out_dir"

cd "$repo_root/python"

for package_dir in \
    packages/sdk-core \
    packages/cas-client \
    packages/boto3-bridge
do
    uv build --wheel "$package_dir" --out-dir "$out_dir"
done

wheel_count="$(find "$out_dir" -maxdepth 1 -type f -name "*-$version-py3-none-any.whl" | wc -l | tr -d '[:space:]')"
if [[ "$wheel_count" != "3" ]]; then
    printf 'Expected 3 Python wheels for version %s, found %s in %s\n' "$version" "$wheel_count" "$out_dir" >&2
    find "$out_dir" -maxdepth 1 -type f -name '*.whl' -print >&2
    exit 1
fi

find "$out_dir" -maxdepth 1 -type f -name '*.whl' -print | sort