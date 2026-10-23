#!/usr/bin/env python3
"""Install the wheel in a clean environment; verify archive parity and corruption rejection."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zipfile


def verify(wheel: Path, archive: Path, version: str, digest: str) -> None:
    wheel = wheel.resolve()
    with zipfile.ZipFile(wheel) as package, tarfile.open(archive) as bundle:
        for name in ("schema.json", "vectors.json", "check_contract.py"):
            assert (
                package.read("onenexus_log_contract/" + name)
                == bundle.extractfile(name).read()
            ), name
        assert json.loads(
            package.read("onenexus_log_contract/manifest.json")
        ) == json.load(bundle.extractfile("manifest.json"))
    with tempfile.TemporaryDirectory(prefix="contract-install-") as directory:
        work = Path(directory)
        subprocess.run(
            ["uv", "venv", "--python", sys.executable, str(work / "venv")],
            check=True,
            timeout=60,
        )
        python = work / "venv/bin/python"
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel)],
            check=True,
            timeout=60,
        )
        code = r"""import importlib.metadata as md
import json
from pathlib import Path
import sys
import onenexus_log_contract as contract
assert "site-packages" in contract.__file__
assert md.version("onenexus-log-contract") == contract.CONTRACT_VERSION == sys.argv[1]
assert contract.CONTRACT_DIGEST == sys.argv[2]
manifest, schema, cases = contract.load()
assert schema["x-contract-version"] == manifest["version"] == cases["contract_version"] == sys.argv[1]
assert len(cases["record_cases"]) == manifest["record_cases"] == 56
assert len(cases["context_cases"]) == manifest["context_cases"] == 10
# Caller mutation cannot corrupt later consumers.
schema.clear()
assert contract.load()[1]["$defs"]
# Negative control: installed resource tampering must fail closed.
resource = Path(contract.__file__).parent / "schema.json"
resource.write_text("{}")
try:
    contract.load()
except ValueError as error:
    assert str(error) == "artifact_digest_mismatch"
else:
    raise AssertionError("corrupt installed resource accepted")
print("PASS: installed wheel, pinned identity, all case data, archive parity, corruption rejection")
"""
        subprocess.run(
            [str(python), "-I", "-c", code, version, digest],
            cwd=work,
            check=True,
            timeout=30,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-digest", required=True)
    args = parser.parse_args()
    verify(args.wheel, args.archive, args.version, args.expected_digest)
