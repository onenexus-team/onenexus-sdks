#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
out="$root/.artifacts/typescript-observability"
mkdir -p "$out"
manifest=contracts/log-correlation/manifest.json
version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$manifest")"
digest="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$manifest")"
checker=contracts/log-correlation/check_contract.py
python3 "$checker" verify --version "$version" --expected-digest "$digest"
pnpm --dir ts sync-version
if [[ -n "${LOG_CONTRACT_PACKAGE_VERSION:-}" ]]; then
    # The tag build temporarily changes only the local workspace contract pin.
    # Reconcile that link using already restored dependencies, without network resolution.
    pnpm --dir ts install --offline --ignore-scripts --no-frozen-lockfile
fi
pnpm --dir ts --filter @onenexus-team/log-contract --filter @onenexus-team/observability build
pnpm --dir ts --filter @onenexus-team/log-contract --filter @onenexus-team/observability typecheck
pnpm --dir ts exec eslint packages/log-contract packages/observability
ONENEXUS_CONTRACT_RESULTS="$out/source-results.json" pnpm --dir ts --filter @onenexus-team/log-contract --filter @onenexus-team/observability test
python3 "$checker" check-results --version "$version" --expected-digest "$digest" --results "$out/source-results.json"
for package in log-contract observability; do
    pnpm --dir "ts/packages/$package" pack --pack-destination "$out"
done
consumer="$(mktemp -d)"
trap 'rm -rf "$consumer"' EXIT
python3 - "$root" "$consumer" "$out" <<'PY'
import json, pathlib, shutil, sys
root, consumer, out = map(pathlib.Path, sys.argv[1:])
version = json.loads((root / 'ts/packages/observability/package.json').read_text())['version']
contract_version = json.loads((root / 'ts/packages/log-contract/package.json').read_text())['version']
import os
published = os.environ.get('REQUIRE_PUBLISHED_LOG_CONTRACT') == '1'
dev = json.loads((root / 'ts/package.json').read_text())['devDependencies']
dev.update(json.loads((root / 'ts/packages/observability/package.json').read_text())['devDependencies'])
# Reuse the complete locked test toolchain, not fresh transitive test-tool ranges.
shutil.copy(root / 'ts/pnpm-lock.yaml', consumer / 'pnpm-lock.yaml')
deps = {'@opentelemetry/api': '1.10.0'}
for name in ('log-contract', 'observability'):
    package_version = contract_version if name == 'log-contract' else version
    deps['@onenexus-team/' + name] = contract_version if published and name == 'log-contract' else 'file:' + str(out / f'onenexus-team-{name}-{package_version}.tgz')
    shutil.copytree(root / f'ts/packages/{name}/test', consumer / f'test/{name}')
shutil.copy(root / 'ts/packages/observability/raw_tests/log-probe.mjs', consumer / 'log-probe.mjs')
(consumer / 'package.json').write_text(json.dumps({'private': True, 'type': 'module', 'dependencies': deps, 'devDependencies': dev}))
# Substitute only the exact expected version with its unpublished local artifact.
# A wrong dependency version still fails resolution instead of being hidden.
import re
lock = (root / 'ts/pnpm-lock.yaml').read_text()
# Use the workspace's already tested Vite version for this separate test harness.
vite = re.search(r'^  vite@([^:(]+)', lock, re.M).group(1)
overrides = {'vite': vite}
if not published:
    overrides['@onenexus-team/log-contract@' + contract_version] = deps['@onenexus-team/log-contract']
(consumer / 'pnpm-workspace.yaml').write_text((root / 'ts/pnpm-workspace.yaml').read_text() + '\noverrides:\n' + ''.join('  ' + json.dumps(k) + ': ' + json.dumps(v) + '\n' for k, v in overrides.items()))
(consumer / 'tsconfig.json').write_text(json.dumps({'compilerOptions': {'target':'ESNext', 'module':'NodeNext', 'moduleResolution':'NodeNext', 'types':['node'], 'strict':True, 'skipLibCheck':True, 'noEmit':True}, 'include':['test/**/*.ts', 'consumer.*']}))
(consumer / 'consumer.mts').write_text('import { createLogger } from "@onenexus-team/observability"; void createLogger;\n')
(consumer / 'consumer.cts').write_text('import { createLogger } from "@onenexus-team/observability"; void createLogger;\n')
PY
# The temporary consumer adds two local tarballs to the copied toolchain lock.
# Repository installation remains frozen; only this disposable lock is updated.
pnpm --dir "$consumer" install --prefer-offline --ignore-scripts --no-frozen-lockfile
pnpm --dir "$consumer" exec tsc --noEmit
ONENEXUS_CONTRACT_RESULTS="$out/installed-results.json" pnpm --dir "$consumer" exec vitest run
python3 "$checker" check-results --version "$version" --expected-digest "$digest" --results "$out/installed-results.json"
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
if python3 "$checker" check-results --version "$version" --expected-digest "$digest" --results "$out/negative-results.json" > "$out/negative-check.log" 2>&1; then
    echo 'False contract observation unexpectedly accepted' >&2; exit 1
fi
echo "PASS: source, installed packages, shared cases, raw probe and negative controls. Artifacts: $out"
