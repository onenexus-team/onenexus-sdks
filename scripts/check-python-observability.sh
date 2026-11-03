#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
export ONENEXUS_LOGGING_SCENARIOS="$root/tests/logging/scenarios.json"
cd python
uv sync --package onenexus-observability-python --group dev --frozen
.venv/bin/ruff check packages/observability
.venv/bin/mypy --strict packages/observability/src/onenexus_observability
.venv/bin/python -m pytest packages/observability/tests -q
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
if [[ -n "${SDK_CHECK_WHEEL:-}" ]]; then
  cp "$SDK_CHECK_WHEEL" "$out/"
else
  uv build --package onenexus-observability-python --wheel --out-dir "$out"
fi
# Resolve the wheel's real metadata in a clean environment; no editable imports.
uv venv --python .venv/bin/python "$out/venv"
uv pip install --python "$out/venv/bin/python" "$out"/*.whl 'pytest>=8.2' 'pytest-asyncio>=0.24' 'opentelemetry-sdk>=1.42,<2'
"$out/venv/bin/python" -c 'import importlib.util, onenexus_observability; assert "site-packages" in onenexus_observability.__file__; assert importlib.util.find_spec("onenexus_log_contract") is None'
"$out/venv/bin/python" -m pytest packages/observability/tests -q
run_id=51386ccb-5346-4e7a-a040-bc32bf742cc1
"$out/venv/bin/python" packages/observability/tests/integration/log_probe.py \
  --environment development --region test --run-id "$run_id" > "$out/logs.ndjson"
"$out/venv/bin/python" packages/observability/tests/integration/log_probe.py \
  --environment development --region test --run-id "$run_id" --verify "$out/logs.ndjson"
