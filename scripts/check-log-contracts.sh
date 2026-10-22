#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
python3 -m unittest discover -s contracts/log-correlation/tests -v
for directory in contracts/log-correlation/versions/*; do
  version="${directory##*/}"
  digest="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$directory/manifest.json")"
  python3 contracts/log-correlation/check_contract.py verify \
    --version "$version" --expected-digest "$digest"
done
if [[ $# -gt 0 ]]; then
  python3 contracts/log-correlation/check_contract.py immutable --base "$1"
fi
