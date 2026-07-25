#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version_file="$repo_root/VERSION"
version=""
out_dir=""

usage() {
    printf '%s\n' "Usage: $(basename "$0") --version <X.Y.Z> [--out-dir <DIR>]" >&2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version)
            [[ $# -ge 2 ]] || { usage; exit 2; }
            version="$2"
            shift 2
            ;;
        --out-dir)
            [[ $# -ge 2 ]] || { usage; exit 2; }
            out_dir="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf '%s\n' "Unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

if [[ -z "$version" ]]; then
    printf '%s\n' "--version is required" >&2
    usage
    exit 2
fi

out_dir="${out_dir:-$repo_root/python/dist}"
case "$out_dir" in
    /*) ;;
    *) out_dir="$(pwd)/$out_dir" ;;
esac

# Hatchling reads the version from VERSION via [tool.hatch.version] in each
# package's pyproject.toml. Write the requested version there for the build,
# then restore the original content (or remove it if it didn't exist) so the
# working tree is left untouched.
if [[ -f "$version_file" ]]; then
    saved_version="$(cat "$version_file")"
else
    saved_version=""
fi
trap 'if [[ -n "$saved_version" ]]; then printf "%s\n" "$saved_version" > "$version_file"; elif [[ -f "$version_file" ]]; then rm -f "$version_file"; fi' EXIT

printf '%s\n' "$version" > "$version_file"

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
    printf '%s\n' "Expected 3 Python wheels for version $version, found $wheel_count in $out_dir" >&2
    find "$out_dir" -maxdepth 1 -type f -name '*.whl' -print >&2
    exit 1
fi

find "$out_dir" -maxdepth 1 -type f -name '*.whl' -print | sort
