"""Installed, verified contract data. No network calls or logging hooks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._version import CONTRACT_DIGEST, __version__
from .check_contract import load_bundle  # type: ignore[no-untyped-call]

CONTRACT_VERSION = __version__


def load() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return independent manifest, schema and test cases after integrity checks."""
    manifest, vectors, snapshots = load_bundle(
        CONTRACT_VERSION, Path(__file__).resolve().parent, CONTRACT_DIGEST
    )
    return manifest, json.loads(snapshots["schema.json"]), vectors
