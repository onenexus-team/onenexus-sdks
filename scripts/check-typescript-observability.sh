#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
out="$root/.artifacts/typescript-observability"
mkdir -p "$out"
export ONENEXUS_LOGGING_SCENARIOS="$root/tests/logging/scenarios.json"
checker=tests/logging/check_results.py
pnpm --dir ts sync-version
pnpm --dir ts --filter @onenexus-team/observability build
pnpm --dir ts --filter @onenexus-team/observability typecheck
pnpm --dir ts exec eslint packages/observability
ONENEXUS_LOGGING_RESULTS="$out/source-results.json" pnpm --dir ts --filter @onenexus-team/observability test
python3 "$checker" "$out/source-results.json"
pnpm --dir ts/packages/observability pack --pack-destination "$out"
consumer="$(mktemp -d)"
trap 'rm -rf "$consumer"' EXIT
python3 - "$root" "$consumer" "$out" <<'PY'
import json, pathlib, shutil, sys
root, consumer, out = map(pathlib.Path, sys.argv[1:])
version = json.loads((root / 'ts/packages/observability/package.json').read_text())['version']
dev = json.loads((root / 'ts/package.json').read_text())['devDependencies']
dev.update(json.loads((root / 'ts/packages/observability/package.json').read_text())['devDependencies'])
# Reuse the complete locked test toolchain, not fresh transitive test-tool ranges.
shutil.copy(root / 'ts/pnpm-lock.yaml', consumer / 'pnpm-lock.yaml')
deps = {
    '@opentelemetry/api': '1.10.0',
    '@onenexus-team/observability': 'file:' + str(out / f'onenexus-team-observability-{version}.tgz'),
}
shutil.copytree(root / 'ts/packages/observability/test', consumer / 'test/observability')
shutil.copy(root / 'ts/packages/observability/test/integration/log-probe.mjs', consumer / 'log-probe.mjs')
(consumer / 'package.json').write_text(json.dumps({'private': True, 'type': 'module', 'dependencies': deps, 'devDependencies': dev}))
import re
lock = (root / 'ts/pnpm-lock.yaml').read_text()
# Use the workspace's already tested Vite version for this separate test harness.
vite = re.search(r'^  vite@([^:(]+)', lock, re.M).group(1)
overrides = {'vite': vite}
(consumer / 'pnpm-workspace.yaml').write_text((root / 'ts/pnpm-workspace.yaml').read_text() + '\noverrides:\n' + ''.join('  ' + json.dumps(k) + ': ' + json.dumps(v) + '\n' for k, v in overrides.items()))
(consumer / 'tsconfig.json').write_text(json.dumps({'compilerOptions': {'target':'ESNext', 'module':'NodeNext', 'moduleResolution':'NodeNext', 'types':['node'], 'strict':True, 'skipLibCheck':True, 'noEmit':True}, 'include':['test/**/*.ts', 'consumer.*']}))
(consumer / 'consumer.mts').write_text('import { createLogger } from "@onenexus-team/observability"; void createLogger;\n')
(consumer / 'consumer.cts').write_text('import { createLogger } from "@onenexus-team/observability"; void createLogger;\n')
PY
# The temporary consumer adds one local tarball to the copied toolchain lock.
# Repository installation remains frozen; only this disposable lock is updated.
pnpm --dir "$consumer" install --prefer-offline --ignore-scripts --no-frozen-lockfile
pnpm --dir "$consumer" exec tsc --noEmit
ONENEXUS_LOGGING_RESULTS="$out/installed-results.json" pnpm --dir "$consumer" exec vitest run
python3 "$checker" "$out/installed-results.json"
(cd "$consumer" && node --input-type=module -e '
import { createRequire } from "node:module";
import * as esm from "@onenexus-team/observability";
const cjs = createRequire(import.meta.url)("@onenexus-team/observability");
if (cjs.withIncomingContext !== esm.withIncomingContext) throw Error("duplicate_context_store");
esm.withIncomingContext([["traceparent", "00-11111111111111111111111111111111-2222222222222222-01"]], {trusted:true}, () => {
    if (cjs.currentTraceId() !== "11111111111111111111111111111111") throw Error("mixed_module_trace_lost");
});')
(cd "$consumer" && node log-probe.mjs emit) > "$out/probe.ndjson"
(cd "$consumer" && node log-probe.mjs verify "$out/probe.ndjson" 11111111111111111111111111111111)
if (cd "$consumer" && node log-probe.mjs verify "$out/probe.ndjson" 33333333333333333333333333333333) > "$out/wrong-trace.log" 2>&1; then
    echo 'Wrong trace unexpectedly accepted' >&2; exit 1
fi
if (cd "$consumer" && node log-probe.mjs verify "$out/probe.ndjson" 11111111111111111111111111111111 missing-service) > "$out/missing-service.log" 2>&1; then
    echo 'Missing service unexpectedly accepted' >&2; exit 1
fi
python3 - "$out" <<'PY'
import hashlib, json, pathlib, sys
out = pathlib.Path(sys.argv[1])
result = json.loads((out / 'installed-results.json').read_text())
next(row for row in result['results'] if row.get('errors'))['errors'] = []
(out / 'negative-results.json').write_text(json.dumps(result))
(out / 'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in sorted(out.glob('*.tgz'))))
PY
if python3 "$checker" "$out/negative-results.json" > "$out/negative-check.log" 2>&1; then
    echo 'False contract observation unexpectedly accepted' >&2; exit 1
fi
echo "PASS: source, installed packages, shared cases, integration probe and negative controls. Artifacts: $out"
