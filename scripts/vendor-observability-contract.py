#!/usr/bin/env python3
"""Verify or refresh the package's copy of an explicitly pinned release archive."""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "python/packages/observability"
TARGET = PACKAGE / "src/onenexus_observability/_contract"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Already-downloaded authenticated GitHub asset")
    args = parser.parse_args()
    pin = json.loads((PACKAGE / "contract-release.json").read_text())
    if args.archive:
        if args.archive.stat().st_size > 1024 * 1024:
            raise ValueError("archive_too_large")
        if hashlib.sha256(args.archive.read_bytes()).hexdigest() != pin["archive_sha256"]:
            raise ValueError("archive_digest_mismatch")
        verified = {}
        with tarfile.open(args.archive) as archive:
            for name, digest in pin["files"].items():
                item = archive.getmember(name)
                if not item.isfile() or item.size > 1024 * 1024:
                    raise ValueError("invalid_archive_member")
                data = archive.extractfile(item).read()
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError("file_digest_mismatch")
                verified[name] = data
        TARGET.mkdir(parents=True, exist_ok=True)
        for name, data in verified.items():
            (TARGET / name).write_bytes(data)
    for name, digest in pin["files"].items():
        if hashlib.sha256((TARGET / name).read_bytes()).hexdigest() != digest:
            raise ValueError("bundled_contract_changed")
    print("PASS: bundled contract matches pinned release")


if __name__ == "__main__":
    main()
