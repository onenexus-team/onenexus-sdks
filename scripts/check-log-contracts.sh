#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
python3 -m unittest discover -s contracts/log-correlation/tests -v
manifest=contracts/log-correlation/manifest.json
version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$manifest")"
digest="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$manifest")"
python3 contracts/log-correlation/check_contract.py verify \
  --version "$version" --expected-digest "$digest"
