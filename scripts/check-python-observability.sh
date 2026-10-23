#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
python3 scripts/vendor-observability-contract.py
cd python
uv sync --package onenexus-observability-python --group dev --frozen
.venv/bin/ruff check packages/observability --exclude _contract
.venv/bin/mypy --strict packages/observability/src/onenexus_observability --exclude _contract
.venv/bin/python -m pytest packages/observability/tests -q
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
uv build --package onenexus-observability-python --wheel --out-dir "$out"
uv pip install --python .venv/bin/python --no-deps --reinstall "$out"/*.whl
# Do not use `uv run` here: it would replace the wheel with the editable workspace.
.venv/bin/python -c 'import onenexus_observability; assert "site-packages" in onenexus_observability.__file__'
.venv/bin/python -m pytest packages/observability/tests -q
run_id=51386ccb-5346-4e7a-a040-bc32bf742cc1
.venv/bin/python packages/observability/raw_tests/log_probe.py \
  --environment development --region test --run-id "$run_id" > "$out/logs.ndjson"
.venv/bin/python packages/observability/raw_tests/log_probe.py \
  --environment development --region test --run-id "$run_id" --verify "$out/logs.ndjson"
