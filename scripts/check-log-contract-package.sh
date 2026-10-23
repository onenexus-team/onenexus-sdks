#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
version="$(python3 -c 'import json; print(json.load(open("contracts/log-correlation/manifest.json"))["version"])')"
digest="$(python3 -c 'import json; print(json.load(open("contracts/log-correlation/manifest.json"))["sha256"])')"
python3 scripts/build-log-contract-package.py --version "$version" --expected-digest "$digest" --out-dir "$work/dist"
python3 contracts/log-correlation/check_contract.py build --version "$version" --expected-digest "$digest" --output "$work/contract.tar.gz"
python3 scripts/verify-log-contract-wheel.py --wheel "$work"/dist/*.whl --archive "$work/contract.tar.gz" --version "$version" --expected-digest "$digest"
