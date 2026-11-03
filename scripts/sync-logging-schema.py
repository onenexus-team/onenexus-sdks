#!/usr/bin/env python3
"""Generate embedded logging schemas, or check that committed copies are current."""

import argparse
import json
from pathlib import Path

SOURCE = Path("schemas/logging.schema.json")
TARGETS = (
    Path("python/packages/observability/src/onenexus_observability/schema.json"),
    Path("ts/packages/observability/src/schema.json"),
    Path("go/packages/observability/schema.json"),
    Path("dotnet/packages/observability/src/schema.json"),
)


def sync_schema(root: Path, *, check: bool = False) -> list[Path]:
    """Return stale paths; write canonical bytes to them unless checking only."""
    source = (root / SOURCE).read_bytes()
    json.loads(source)  # Reject malformed input before changing any package.
    stale = []
    for relative in TARGETS:
        target = root / relative
        if not target.exists() or target.read_bytes() != source:
            stale.append(relative)
            if not check:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source)
    return stale


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail on stale or missing copies without writing.")
    args = parser.parse_args()
    stale = sync_schema(Path(__file__).resolve().parents[1], check=args.check)
    for path in stale:
        print(f"{'Stale' if args.check else 'Updated'}: {path}")
    if args.check and stale:
        print("Run python3 scripts/sync-logging-schema.py and commit the generated copies.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
