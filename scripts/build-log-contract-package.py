#!/usr/bin/env python3
"""Generate a data-only Python wheel from the canonical, verified contract."""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1] / "contracts/log-correlation"
spec = importlib.util.spec_from_file_location(
    "contract_gate", ROOT / "check_contract.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def stage(source: Path, destination: Path, version: str, digest: str) -> None:
    manifest, _, snapshots = gate.load_bundle(version, source, digest)
    package = destination / "src/onenexus_log_contract"
    package.mkdir(parents=True)
    for name, data in snapshots.items():
        (package / name).write_bytes(data)
    # Serialize the already verified manifest, not a second read of mutable source.
    (package / "manifest.json").write_text(gate.json.dumps(manifest, indent=2) + "\n")
    shutil.copyfile(source / "check_contract.py", package / "check_contract.py")
    shutil.copyfile(source / "python/__init__.py", package / "__init__.py")
    shutil.copyfile(source / "python/pyproject.toml", destination / "pyproject.toml")
    (package / "_version.py").write_text(
        f"__version__ = {version!r}\nCONTRACT_DIGEST = {digest!r}\n"
    )
    (package / "py.typed").touch()


def build(source: Path, output: Path, version: str, digest: str) -> Path:
    with tempfile.TemporaryDirectory(prefix="log-contract-build-") as directory:
        work = Path(directory)
        stage(source, work / "project", version, digest)
        subprocess.run(
            [
                "uv",
                "build",
                "--wheel",
                "--python",
                os.sys.executable,
                str(work / "project"),
                "--out-dir",
                str(work / "dist"),
            ],
            check=True,
            timeout=120,
            env={**os.environ, "SOURCE_DATE_EPOCH": "1704067200"},
        )
        wheels = list((work / "dist").glob("*.whl"))
        if len(wheels) != 1:
            raise ValueError("unexpected_wheel_count")
        output.mkdir(parents=True, exist_ok=True)
        target = output / wheels[0].name
        # Exclusive creation also rejects a concurrent publisher. Failed copies
        # remain invalid; callers must use a fresh output directory to retry.
        with target.open("xb") as stream:
            stream.write(wheels[0].read_bytes())
        return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-digest", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    print(build(ROOT, args.out_dir, args.version, args.expected_digest))
