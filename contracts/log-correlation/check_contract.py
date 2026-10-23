"""Offline contract integrity and cross-language test-result checks; no runtime SDK."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import re
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ("contract-v1.schema.json", "contract-v1.vectors.json")
MAX_BYTES = 1024 * 1024
VERSION_PATTERN = r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9]+(?:\.[a-z0-9]+)*)?"
ERRORS = {
    "unknown_profile",
    "schema_invalid",
    "missing_or_invalid_trace_id",
    "missing_or_invalid_message",
    "record_too_large",
    "invalid_json_record",
}


class ContractError(ValueError):
    """Only fixed, safe codes may reach command output."""


def require(condition, code):
    if not condition:
        raise ContractError(code)


def read_bytes(path):
    require(not path.is_symlink(), "symlink_not_allowed")
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, "input_limit_exceeded")
    return data


def parse_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def invalid(_value):
        raise ContractError("non_finite_json_number")

    def finite(value):
        number = float(value)
        require(math.isfinite(number), "non_finite_json_number")
        return number

    return json.loads(
        data, object_pairs_hook=unique, parse_constant=invalid, parse_float=finite
    )


def load_bundle(version, root=ROOT, expected_digest=None):
    require(re.fullmatch(VERSION_PATTERN, version) is not None, "invalid_version")
    directory = root / "versions" / version
    require(not directory.is_symlink(), "symlink_not_allowed")
    manifest = parse_json(read_bytes(directory / "manifest.json"))
    require(
        manifest["contract"] == "log-correlation" and manifest["version"] == version,
        "contract_version_mismatch",
    )
    require(
        [item["path"] for item in manifest["files"]] == list(ARTIFACTS),
        "unexpected_artifact_set",
    )
    digest = hashlib.sha256()
    snapshots = {}
    for item in manifest["files"]:
        data = read_bytes(directory / item["path"])
        snapshots[item["path"]] = data
        require(
            hashlib.sha256(data).hexdigest() == item["sha256"],
            "artifact_digest_mismatch",
        )
        digest.update(item["path"].encode() + b"\0" + data)
    actual = digest.hexdigest()
    require(actual == manifest["sha256"], "contract_digest_mismatch")
    if expected_digest is not None:
        require(actual == expected_digest, "trusted_contract_pin_mismatch")
    schema = parse_json(snapshots[ARTIFACTS[0]])
    vectors = parse_json(snapshots[ARTIFACTS[1]])
    require(
        schema["x-contract-version"] == version == vectors["contract_version"],
        "contract_version_mismatch",
    )
    require(sorted(schema["$defs"]) == sorted(manifest["profiles"]), "profile_mismatch")
    require(manifest["adapter_protocol"] == 1, "unsupported_adapter_protocol")
    ids = set()
    for kind in ("record", "context"):
        cases = vectors[kind + "_cases"]
        require(
            isinstance(cases, list)
            and 0 < len(cases) <= 500
            and len(cases) == manifest[kind + "_cases"],
            "invalid_case_count",
        )
        for case in cases:
            require(
                isinstance(case["id"], str)
                and re.fullmatch(r"[a-z0-9_]{1,80}", case["id"]),
                "invalid_case_id",
            )
            require(case["id"] not in ids, "duplicate_case_id")
            ids.add(case["id"])
            if kind == "record":
                require(case["profile"] in manifest["profiles"], "unknown_profile")
                require(
                    isinstance(case["errors"], list)
                    and all(isinstance(e, str) and e in ERRORS for e in case["errors"])
                    and case["errors"] == sorted(set(case["errors"])),
                    "invalid_expected_errors",
                )
            else:
                require(
                    type(case["trusted"]) is bool
                    and type(case["preserve_trace"]) is bool
                    and isinstance(case["traceparent"], str),
                    "invalid_context_case",
                )
    return manifest, vectors, snapshots


def check_results(version, expected_digest, results_path, root=ROOT):
    manifest, vectors, _ = load_bundle(version, root, expected_digest)
    result = parse_json(read_bytes(results_path))
    require(
        result["contract_version"] == version
        and result["contract_sha256"] == expected_digest,
        "result_contract_mismatch",
    )
    require(
        result["adapter_protocol"] == manifest["adapter_protocol"],
        "unsupported_adapter_protocol",
    )
    cases = {
        (kind, case["id"]): case
        for kind in ("record", "context")
        for case in vectors[kind + "_cases"]
    }
    require(
        isinstance(result["results"], list) and len(result["results"]) == len(cases),
        "incomplete_case_coverage",
    )
    seen = set()
    fresh_ids = set()
    for item in result["results"]:
        key = (item["kind"], item["id"])
        require(key in cases and key not in seen, "unexpected_or_duplicate_case")
        seen.add(key)
        case = cases[key]
        if item["kind"] == "record":
            require(item["errors"] == case["errors"], "record_result_mismatch")
        else:
            trace_id = item["trace_id"]
            require(
                isinstance(trace_id, str)
                and re.fullmatch(r"[0-9a-f]{32}", trace_id)
                and trace_id != "0" * 32,
                "invalid_trace_id",
            )
            incoming = case["traceparent"].split("-")
            parent_id = incoming[1] if len(incoming) >= 4 else None
            if case["preserve_trace"]:
                require(trace_id == parent_id, "trusted_context_not_preserved")
            else:
                require(
                    trace_id != parent_id and trace_id not in fresh_ids,
                    "fresh_context_not_isolated",
                )
                fresh_ids.add(trace_id)
            outgoing = item["outgoing_traceparent"]
            require(
                isinstance(outgoing, str)
                and re.fullmatch(r"00-" + trace_id + r"-[0-9a-f]{16}-00", outgoing)
                and outgoing.split("-")[2] != "0" * 16,
                "invalid_outgoing_context",
            )
            require(item["after_trace_id"] is None, "context_not_cleared")
    return len(cases)


def check_immutable(base, root=ROOT):
    repo = root.parents[1]
    prefix = root.relative_to(repo).as_posix() + "/versions/"

    def git(*args):
        return subprocess.check_output(
            ["git", *args], cwd=repo, stderr=subprocess.DEVNULL, timeout=10
        )

    commit = (
        git("rev-parse", "--verify", "--end-of-options", base + "^{commit}")
        .decode()
        .strip()
    )
    paths = (
        git("ls-tree", "-r", "--name-only", commit, "--", prefix).decode().splitlines()
    )
    versions = {path[len(prefix) :].split("/")[0] for path in paths}
    for version in versions:
        old_paths = {path for path in paths if path.startswith(prefix + version + "/")}
        directory = root / "versions" / version
        require(
            directory.is_dir() and not directory.is_symlink(),
            "existing_version_changed",
        )
        current_paths = {
            path.relative_to(repo).as_posix()
            for path in directory.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        require(old_paths == current_paths, "existing_version_changed")
        for path in sorted(old_paths):
            require(
                read_bytes(repo / path) == git("show", commit + ":" + path),
                "existing_version_changed",
            )
    return len(versions)


def build_archive(version, expected_digest, output, root=ROOT):
    manifest, _, snapshots = load_bundle(version, root, expected_digest)
    files = {f"versions/{version}/{name}": data for name, data in snapshots.items()}
    files[f"versions/{version}/manifest.json"] = (
        json.dumps(manifest, indent=2) + "\n"
    ).encode()
    for name in ("check_contract.py", "README.md", "design-and-validation.md"):
        files[name] = read_bytes(root / name)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as archive:
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            archive.addfile(info, io.BytesIO(data))
    compressed = io.BytesIO()
    # GzipFile fixes the OS header across supported Python versions/platforms.
    with gzip.GzipFile(
        filename="", fileobj=compressed, mode="wb", compresslevel=9, mtime=0
    ) as stream:
        stream.write(raw.getvalue())
    payload = compressed.getvalue()
    # Exclusive create: retries cannot silently replace an existing release artifact.
    with output.open("xb") as stream:
        stream.write(payload)
    return hashlib.sha256(payload).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("verify", "check-results", "build", "immutable")
    )
    parser.add_argument("--version", default="0.3.1")
    parser.add_argument("--expected-digest")
    parser.add_argument("--results", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--base")
    args = parser.parse_args(argv)
    report = {
        "gate": "FAIL",
        "scope": "contract artifacts and adapter results only; not package adoption or live-service proof",
    }
    try:
        if args.command == "immutable":
            require(bool(args.base), "base_required")
            report["unchanged_versions"] = check_immutable(args.base)
        else:
            require(bool(args.expected_digest), "trusted_contract_pin_required")
            manifest, _, _ = load_bundle(
                args.version, expected_digest=args.expected_digest
            )
            report.update(
                contract_version=args.version, contract_sha256=manifest["sha256"]
            )
            if args.command == "check-results":
                require(args.results is not None, "results_required")
                report["cases_passed"] = check_results(
                    args.version, args.expected_digest, args.results
                )
            elif args.command == "build":
                require(args.output is not None, "output_required")
                report["archive_sha256"] = build_archive(
                    args.version, args.expected_digest, args.output
                )
            else:
                report.update(
                    record_cases=manifest["record_cases"],
                    context_cases=manifest["context_cases"],
                )
        report["gate"] = "PASS"
    except ContractError as exc:
        report["error"] = str(exc)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RecursionError,
        subprocess.SubprocessError,
    ):
        report["error"] = "contract_check_failed"
    print(json.dumps(report, sort_keys=True))
    return 0 if report["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
