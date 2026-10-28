#!/usr/bin/env python3
"""Source/race checks, independently installed Go modules and raw output controls."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("go_release", ROOT / "scripts/go-module-release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def run(args, *, cwd=ROOT, env=None, capture=False, success=True):
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=capture, timeout=300)
    if (result.returncode == 0) != success:
        raise RuntimeError("validation command returned unexpected status: " + str(args[:3]))
    return result


def main():
    out = ROOT / ".artifacts/go-observability"
    out.mkdir(parents=True, exist_ok=True)
    sdk = os.environ.get("SDK_PACKAGE_VERSION", (ROOT / "VERSION").read_text().strip())
    checker = [sys.executable, str(ROOT / "tests/logging/check_results.py")]
    env = {**os.environ, "GOTOOLCHAIN": "local", "ONENEXUS_LOGGING_SCENARIOS": str(ROOT / "tests/logging/scenarios.json")}
    with tempfile.TemporaryDirectory(prefix="onenexus-go-check-") as temp:
        temp = Path(temp)
        source_env = {**env, "GOWORK": "off", "ONENEXUS_LOGGING_RESULTS": str(out / "source-results.json")}
        go_files = [str(p) for path in release.MODULES.values() for p in (ROOT / path).rglob("*.go")]
        if run(["gofmt", "-l", *go_files], capture=True).stdout.strip():
            raise ValueError("go_formatting_required")
        for path in release.MODULES.values():
            flags = ["-mod=readonly"]
            run(["go", "vet", *flags, "./..."], cwd=ROOT / path, env=source_env)
            run(["go", "test", *flags, "-race", "-count=1", "./..."], cwd=ROOT / path, env=source_env)
        run(checker + [str(out / "source-results.json")])
        # A private local proxy serves real module ZIPs, not source replacements.
        proxy = temp / "proxy"
        for kind, version in [("observability", sdk)]:
            module_path, _ = release.identity(kind, version)
            entry = proxy / module_path / "@v"
            entry.mkdir(parents=True)
            (entry / f"v{version}.zip").write_bytes(release.archive(kind, version))
            (entry / f"v{version}.mod").write_bytes((ROOT / release.MODULES[kind] / "go.mod").read_bytes())
            (entry / f"v{version}.info").write_text(json.dumps({"Version": "v" + version, "Time": "2000-01-01T00:00:00Z"}))
            (entry / "list").write_text("v" + version + "\n")
        consumer = temp / "consumer"
        consumer.mkdir()
        (consumer / "go.mod").write_text("module example.com/installed-consumer\n\ngo 1.26.0\nrequire " + release.PREFIX + "go/observability v" + sdk + "\n")
        shutil.copytree(ROOT / "go/observability/tests", consumer / "tests")
        shutil.copytree(ROOT / "go/observability/raw_tests", consumer / "raw_tests")
        installed_env = {**env, "GOWORK": "off", "GOMODCACHE": str(temp / "module-cache"),
                         "GOPROXY": proxy.as_uri() + ",https://proxy.golang.org", "GONOPROXY": "none",
                         "GONOSUMDB": release.PREFIX + "*", "ONENEXUS_LOGGING_RESULTS": str(out / "installed-results.json")}
        run(["go", "mod", "tidy"], cwd=consumer, env=installed_env)
        resolved = run(["go", "list", "-m", "-json", "all"], cwd=consumer, env=installed_env, capture=True).stdout
        if '"Replace"' in resolved:
            raise ValueError("installed_test_used_source_override")
        (out / "installed-modules.json").write_text(resolved)
        run(["go", "test", "-mod=readonly", "-race", "-count=1", "./..."], cwd=consumer, env=installed_env)
        run(checker + [str(out / "installed-results.json")])
        if os.environ.get("RUN_GO_VULNCHECK") == "1":
            scan = run(["govulncheck", "./..."], cwd=consumer, env=installed_env, capture=True)
            (out / "vulnerability-scan.txt").write_text(scan.stdout)
        run(["go", "build", "-mod=readonly", "-o", str(temp / "log-probe"), "./raw_tests/log-probe"], cwd=consumer, env=installed_env)
        probe = str(temp / "log-probe")
        emitted = run([probe, "emit"], capture=True).stdout
        capture = out / "probe.ndjson"
        capture.write_text(emitted)
        trace = "1" * 32
        run([probe, "verify", str(capture), trace, "go-log-probe"])
        if len(emitted.splitlines()) != 4:
            raise ValueError("missing_raw_probe_events")
        for name, target, expected, service in [
            ("wrong-trace", capture, "3" * 32, "go-log-probe"),
            ("wrong-service", capture, trace, "missing-service"),
        ]:
            result = run([probe, "verify", str(target), expected, service], capture=True, success=False)
            (out / (name + ".log")).write_text(result.stderr)
        damaged = out / "missing-field.ndjson"
        records = [json.loads(line) for line in emitted.splitlines()]
        del records[0]["environment"]
        damaged.write_text("\n".join(json.dumps(row) for row in records))
        run([probe, "verify", str(damaged), trace, "go-log-probe"], capture=True, success=False)
        damaged.write_text(emitted + "plain progress bypass\n")
        run([probe, "verify", str(damaged), trace, "go-log-probe"], capture=True, success=False)
        result = json.loads((out / "installed-results.json").read_text())
        next(row for row in result["results"] if row.get("errors"))["errors"] = []
        negative = out / "negative-results.json"
        negative.write_text(json.dumps(result))
        run(checker + [str(negative)], capture=True, success=False)
        benchmark = run(["go", "test", "-run=^$", "-bench=BenchmarkHandler", "-benchmem", "./tests"], cwd=consumer, env=installed_env, capture=True)
        (out / "benchmark.txt").write_text(benchmark.stdout)
    for kind, version in [("observability", sdk)]:
        name = "observability-go" + f"-v{version}.zip"
        (out / name).write_bytes(release.archive(kind, version))
        release.verify(kind, version, out / name)
    print("PASS: Go source, installed modules, race tests, shared cases and raw controls. " + str(out))


if __name__ == "__main__":
    main()
