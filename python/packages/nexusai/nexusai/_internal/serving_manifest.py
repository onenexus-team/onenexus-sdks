import hashlib
import json
import unicodedata
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Optional

from .._version import __version__
from .storage import StorageTransferFile

_WEIGHT_FORMATS = {
    ".safetensors": "safetensors",
    ".gguf": "gguf",
    ".bin": "pytorch",
    ".pt": "pytorch",
    ".pth": "pytorch",
    ".ckpt": "pytorch",
}
_TOKENIZER_FILES = {
    "added_tokens.json",
    "merges.txt",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "spiece.model",
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "vocab.json",
    "vocab.txt",
}
_CONFIG_FILES = {
    "config.json",
    "generation_config.json",
    "preprocessor_config.json",
    "processor_config.json",
}


def build_serving_manifest(
    files: Iterable[StorageTransferFile],
    *,
    storage_prefix: str,
    model_version_id: str,
    artifact_format: Optional[str] = None,
    model_architecture: Optional[str] = None,
    runtime: str = "sglang",
    accelerators: Iterable[str] = ("amd",),
) -> dict[str, Any]:
    uploaded = sorted(files, key=lambda file: file.relative_path)
    if not uploaded:
        raise ValueError("Model upload contains no files")

    paths = [_canonical_path(file.relative_path) for file in uploaded]
    if len(paths) != len(set(paths)):
        raise ValueError("Model upload contains duplicate file paths")

    inferred_format = _infer_artifact_format(paths)
    resolved_format = (artifact_format or inferred_format).strip()
    architecture = (model_architecture or _read_model_architecture(uploaded)).strip()
    compatible_accelerators = [item.strip() for item in accelerators if item.strip()]
    if not resolved_format or not architecture:
        raise ValueError("artifact_format and model_architecture are required")
    if not runtime.strip() or not compatible_accelerators:
        raise ValueError("runtime and at least one accelerator are required")

    published_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest: dict[str, Any] = {
        "schema_version": "onenexus.serving-manifest/v1",
        "manifest_digest": None,
        "artifact_kind": "full_weights",
        "artifact_format": resolved_format,
        "producer": {
            "run_id": None,
            "execution_id": model_version_id,
            "tool": "nexusai",
            "tool_version": __version__,
            "image": None,
        },
        "files": [
            {
                "path": path,
                "size_bytes": int(file.size_bytes),
                "digest": _sha256(Path(file.local_path)),
            }
            for file, path in zip(uploaded, paths, strict=True)
        ],
        "model_architecture": architecture,
        "tokenizer_files": [
            path for path in paths if PurePosixPath(path).name in _TOKENIZER_FILES
        ],
        "config_files": [
            path for path in paths if PurePosixPath(path).name in _CONFIG_FILES
        ],
        "compatibility": {
            "runtime": runtime.strip(),
            "accelerators": compatible_accelerators,
            "min_runtime_version": None,
            "max_runtime_version": None,
        },
        "dependencies": [],
        "storage_prefix": storage_prefix.strip("/"),
        "published_at": published_at,
    }
    if not manifest["storage_prefix"]:
        raise ValueError("storage_prefix is required")
    manifest["manifest_digest"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    return manifest


def _canonical_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not value
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts)
        or unicodedata.normalize("NFC", value) != value
        or any(unicodedata.category(character) == "Cc" for character in value)
    ):
        raise ValueError(f"Unsafe model artifact path: {value!r}")
    normalized = path.as_posix()
    if normalized != value:
        raise ValueError(f"Model artifact path is not canonical: {value!r}")
    return normalized


def _infer_artifact_format(paths: Iterable[str]) -> str:
    formats = {
        artifact_format
        for path in paths
        if (artifact_format := _WEIGHT_FORMATS.get(PurePosixPath(path).suffix.lower()))
    }
    if not formats:
        raise ValueError("Model upload contains no supported weight file")
    if len(formats) > 1:
        raise ValueError("artifact_format is required for mixed weight formats")
    return formats.pop()


def _read_model_architecture(files: Iterable[StorageTransferFile]) -> str:
    config = next(
        (
            file
            for file in files
            if PurePosixPath(file.relative_path).name == "config.json"
        ),
        None,
    )
    if config is None:
        raise ValueError("model_architecture is required when config.json is absent")
    try:
        payload = json.loads(Path(config.local_path).read_text(encoding="utf-8"))
        architectures = payload.get("architectures") or []
        architecture = architectures[0] if architectures else payload.get("model_type")
    except (OSError, json.JSONDecodeError, AttributeError, TypeError) as error:
        raise ValueError(
            "Unable to read model architecture from config.json"
        ) from error
    if not isinstance(architecture, str) or not architecture.strip():
        raise ValueError("config.json does not declare model architecture")
    return architecture.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()
