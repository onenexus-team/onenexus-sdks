#!/usr/bin/env python3
"""Build and publish immutable contract artifacts for every implemented language."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
go_spec = importlib.util.spec_from_file_location("go_modules", ROOT / "scripts/go-module-release.py")
go_modules = importlib.util.module_from_spec(go_spec)
go_spec.loader.exec_module(go_modules)
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def run(args: list[str], *, env: dict[str, str] | None = None, capture: bool = False):
    return subprocess.run(args, cwd=ROOT, env=env, check=True, text=True,
                          capture_output=capture, timeout=600)


def names(version: str) -> list[str]:
    if not VERSION.fullmatch(version):
        raise ValueError("invalid_contract_version")
    return [f"log-correlation-{version}.tar.gz",
            f"onenexus_log_contract-{version}-py3-none-any.whl",
            f"onenexus-team-log-contract-{version}.tgz",
            f"OneNexus.LogContract.{version}.nupkg",
            f"log-contract-go-v{version}.zip"]


def verify(directory: Path, version: str) -> dict:
    names(version)  # Validate before interpolating a version into any path.
    metadata = json.loads((directory / "release-manifest.json").read_text())
    canonical = json.loads((ROOT / "contracts/log-correlation/manifest.json").read_text())
    if metadata["version"] != version or canonical["version"] != version:
        raise ValueError("contract_version_mismatch")
    if metadata["contract_sha256"] != canonical["sha256"]:
        raise ValueError("contract_digest_mismatch")
    if metadata["source_commit"] != run(["git", "rev-parse", "HEAD"], capture=True).stdout.strip():
        raise ValueError("release_source_mismatch")
    artifacts = metadata["artifacts"]
    expected = names(version)
    if set(artifacts) != set(expected):
        raise ValueError("incomplete_language_artifacts")
    if {path.name for path in directory.iterdir()} != set(expected) | {"release-manifest.json", "SHA256SUMS"}:
        raise ValueError("unexpected_release_files")
    for name, digest in artifacts.items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
            raise ValueError("artifact_hash_mismatch")
    with tarfile.open(directory / expected[2]) as package:
        npm = json.load(package.extractfile("package/package.json"))
    if npm["name"] != "@onenexus-team/log-contract" or npm["version"] != version:
        raise ValueError("npm_identity_mismatch")
    with zipfile.ZipFile(directory / expected[3]) as package:
        nuspec = ET.fromstring(package.read("OneNexus.LogContract.nuspec"))
    identity = {node.tag.split("}")[-1]: node.text for node in nuspec.iter()}
    if identity.get("id") != "OneNexus.LogContract" or identity.get("version") != version:
        raise ValueError("nuget_identity_mismatch")
    go_modules.verify("contract", version, directory / expected[4])
    checksums = "".join(f"{artifacts[name]}  {name}\n" for name in sorted(artifacts))
    if (directory / "SHA256SUMS").read_text() != checksums:
        raise ValueError("checksum_manifest_mismatch")
    return metadata


def build(directory: Path, version: str) -> None:
    names(version)
    manifest = json.loads((ROOT / "contracts/log-correlation/manifest.json").read_text())
    digest = manifest["sha256"]
    checker = "contracts/log-correlation/check_contract.py"
    run([sys.executable, checker, "verify", "--version", version, "--expected-digest", digest])
    directory.mkdir(parents=True, exist_ok=False)
    # The existing language checks build source and independent installed consumers.
    # Restore tracked package metadata after their temporary release-version overrides.
    saved = {path: path.read_bytes() for path in (ROOT / "ts/packages").glob("*/package.json")}
    lockfile = ROOT / "ts/pnpm-lock.yaml"
    saved[lockfile] = lockfile.read_bytes()
    env = {**os.environ, "PACKAGE_VERSION": version, "SDK_PACKAGE_VERSION": version,
           "LOG_CONTRACT_PACKAGE_VERSION": version, "REQUIRE_PUBLISHED_LOG_CONTRACT": "0"}
    try:
        archive = directory / f"log-correlation-{version}.tar.gz"
        run([sys.executable, checker, "build", "--version", version,
             "--expected-digest", digest, "--output", str(archive)])
        run([sys.executable, "scripts/build-log-contract-package.py", "--version", version,
             "--expected-digest", digest, "--out-dir", str(directory)])
        wheel, = directory.glob("*.whl")
        run([sys.executable, "scripts/verify-log-contract-wheel.py", "--wheel", str(wheel),
             "--archive", str(archive), "--version", version, "--expected-digest", digest])
        run(["bash", "scripts/check-typescript-observability.sh"], env=env)
        shutil.copyfile(ROOT / f".artifacts/typescript-observability/onenexus-team-log-contract-{version}.tgz",
                        directory / f"onenexus-team-log-contract-{version}.tgz")
        run(["bash", "scripts/check-dotnet-observability.sh"], env=env)
        shutil.copyfile(ROOT / f".artifacts/dotnet/{version}/OneNexus.LogContract.{version}.nupkg",
                        directory / f"OneNexus.LogContract.{version}.nupkg")
        run(["bash", "scripts/check-go-observability.sh"], env=env)
        go_modules.build("contract", version, directory)
        artifacts = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(directory.iterdir()) if p.is_file()}
        metadata = {"version": version, "contract_sha256": digest,
                    "source_commit": run(["git", "rev-parse", "HEAD"], capture=True).stdout.strip(),
                    "artifacts": artifacts}
        (directory / "release-manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
        (directory / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(artifacts.items())))
        verify(directory, version)
    finally:
        for path, content in saved.items():
            path.write_bytes(content)


def ensure_available(version: str) -> None:
    """Check every registry before the first write; registries also reject races."""
    names(version)
    go_modules.preflight("contract", version)
    npm = subprocess.run(["npm", "view", "@onenexus-team/log-contract",
                          "versions", "--json", "--registry=https://npm.pkg.github.com"],
                         cwd=ROOT, capture_output=True, text=True, timeout=60)
    def check_versions(versions: list[str], registry: str) -> None:
        requested = tuple(map(int, version.split('.')))
        for published in versions:
            if published.lower() == version.lower():
                raise ValueError(f"{registry}_version_already_exists")
            if VERSION.fullmatch(published) and tuple(map(int, published.split('.'))) > requested:
                raise ValueError(f"{registry}_newer_version_exists")

    try:
        response = json.loads(npm.stdout)
    except ValueError:
        raise ValueError("npm_preflight_failed") from None
    if npm.returncode == 0:
        if isinstance(response, str):
            response = [response]
        if not isinstance(response, list) or not all(isinstance(item, str) for item in response):
            raise ValueError("npm_preflight_failed")
        check_versions(response, "npm")
    elif not isinstance(response, dict) or response.get("error", {}).get("code") != "E404":
        raise ValueError("npm_preflight_failed")
    for page in range(1, 11):
        # This package already exists; auth errors/404 are never treated as absence.
        response = run(["gh", "api", f"orgs/onenexus-team/packages/nuget/OneNexus.LogContract/versions?per_page=100&page={page}"], capture=True)
        versions = json.loads(response.stdout)
        check_versions([item["name"] for item in versions], "nuget")
        if len(versions) < 100:
            return
    raise ValueError("nuget_version_scan_limit")


def publish(directory: Path, version: str) -> None:
    verify(directory, version)
    token = os.environ.get("NUGET_AUTH_TOKEN")
    if not token:
        raise ValueError("missing_nuget_publish_token")
    ensure_available(version)
    # No skip-duplicate or overwrite: a competing/stale publisher must fail.
    run(["npm", "publish", str(directory / f"onenexus-team-log-contract-{version}.tgz"),
         "--ignore-scripts", "--registry=https://npm.pkg.github.com",
         "--tag", "latest"])
    run(["dotnet", "nuget", "push", str(directory / f"OneNexus.LogContract.{version}.nupkg"),
         "--api-key", token, "--source", "https://nuget.pkg.github.com/onenexus-team/index.json"])
    go_modules.publish("contract", version, directory / f"log-contract-go-v{version}.zip")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "verify", "preflight", "publish"])
    parser.add_argument("--version", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            verify(args.directory.resolve(), args.version)
            ensure_available(args.version)
        else:
            globals()[args.command](args.directory.resolve(), args.version)
        print(f"PASS: contract release {args.command} {args.version}")
    except subprocess.CalledProcessError as error:
        # Commands can include credentials. Never serialize CalledProcessError.cmd.
        print(f"FAIL: release command exited {error.returncode}", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("FAIL: release command timed out; inspect publication state before retry", file=sys.stderr)
        sys.exit(1)
