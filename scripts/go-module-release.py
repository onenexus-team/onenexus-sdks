#!/usr/bin/env python3
"""Build deterministic Go module archives; publish immutable, source-backed tags."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "github.com/onenexus-team/onenexus-sdks/"
MODULES = {"contract": "contracts/log-correlation", "observability": "go/observability"}
SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def identity(kind: str, version: str) -> tuple[str, str]:
    if kind not in MODULES or not SEMVER.fullmatch(version) or version.split(".")[0] not in {"0", "1"}:
        raise ValueError("invalid_go_module_version")
    path = MODULES[kind]
    return PREFIX + path, path + "/v" + version


def files(kind: str) -> dict[str, bytes]:
    root = ROOT / MODULES[kind]
    selected = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part.startswith(".") or part in {"node_modules", "__pycache__", "bin", "obj"} for part in relative.parts):
            continue
        if path.is_file() and (path.suffix == ".go" or str(relative) in {"go.mod", "go.sum", "manifest.json", "schema.json", "vectors.json"}):
            if path.is_symlink():
                raise ValueError("symlink_in_go_module")
            selected[str(relative)] = path.read_bytes()
    if b"replace " in selected["go.mod"] or b"\nexclude " in selected["go.mod"]:
        raise ValueError("source_override_in_release")
    if not selected["go.mod"].startswith(("module " + PREFIX + MODULES[kind] + "\n").encode()):
        raise ValueError("wrong_go_module_identity")
    return selected


def archive(kind: str, version: str) -> bytes:
    module, _ = identity(kind, version)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in files(kind).items():
            info = zipfile.ZipInfo(f"{module}@v{version}/{name}", (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    return out.getvalue()


def verify(kind: str, version: str, path: Path) -> None:
    # Compare file contents too: a checksum alone can authenticate the wrong module.
    module, _ = identity(kind, version)
    expected = {f"{module}@v{version}/{name}": data for name, data in files(kind).items()}
    with zipfile.ZipFile(path) as z:
        if len(z.namelist()) != len(expected) or set(z.namelist()) != set(expected):
            raise ValueError("go_archive_inventory_mismatch")
        if any(z.read(name) != data for name, data in expected.items()):
            raise ValueError("go_archive_source_mismatch")


def build(kind: str, version: str, directory: Path) -> Path:
    module, _ = identity(kind, version)
    directory.mkdir(parents=True, exist_ok=True)
    name = ("log-contract-go" if kind == "contract" else "observability-go") + f"-v{version}.zip"
    path = directory / name
    with path.open("xb") as f:
        f.write(archive(kind, version))
    verify(kind, version, path)
    return path


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True,
                          check=True, timeout=60).stdout.strip()


def preflight(kind: str, version: str) -> None:
    _, tag = identity(kind, version)
    files(kind)
    if git("status", "--porcelain", "--", MODULES[kind]):
        raise ValueError("uncommitted_go_module")
    if kind == "contract":
        if json.loads((ROOT / MODULES[kind] / "manifest.json").read_text())["version"] != version:
            raise ValueError("go_contract_version_mismatch")
    git("merge-base", "--is-ancestor", "HEAD", "origin/main")
    # Authentication/network failures raise; they are never interpreted as absence.
    refs = git("ls-remote", "--refs", "origin", "refs/tags/" + MODULES[kind] + "/v*")
    requested = tuple(map(int, version.split(".")))
    for line in refs.splitlines():
        ref = line.split()[1]
        published = ref.removeprefix("refs/tags/" + MODULES[kind] + "/v")
        if ref == "refs/tags/" + tag:
            raise ValueError("go_module_tag_exists")
        if SEMVER.fullmatch(published) and tuple(map(int, published.split("."))) > requested:
            raise ValueError("newer_go_module_exists")


def publish(kind: str, version: str, path: Path) -> None:
    verify(kind, version, path)
    preflight(kind, version)
    _, tag = identity(kind, version)
    # Atomic creation at GitHub rejects a racing publisher even at the same SHA.
    # No force update, tag deletion or 'skip duplicate'. No locally-generated code.
    sha = git("rev-parse", "HEAD")
    subprocess.run(["gh", "api", "repos/onenexus-team/onenexus-sdks/git/refs",
                    "--method", "POST", "-f", "ref=refs/tags/" + tag, "-f", "sha=" + sha],
                   cwd=ROOT, check=True, capture_output=True, text=True, timeout=60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "verify", "preflight", "publish"])
    parser.add_argument("--kind", required=True, choices=MODULES)
    parser.add_argument("--version", required=True)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "build":
            if args.directory is None: parser.error("--directory required")
            print(build(args.kind, args.version, args.directory.resolve()))
        elif args.command == "preflight":
            preflight(args.kind, args.version)
        else:
            if args.archive is None: parser.error("--archive required")
            globals()[args.command](args.kind, args.version, args.archive.resolve())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise SystemExit("Go release operation failed; inspect tag before retrying") from None
