from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TextIO


CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"

SUCCESS_STATES = {
    "ACTIVE",
    "COMPLETED",
    "DONE",
    "FINALIZED",
    "READY",
    "RUNNING",
    "SUCCEEDED",
}
TRANSITION_STATES = {
    "CANCELING",
    "DEPLOYING",
    "PENDING",
    "QUEUED",
    "RESTARTING",
    "SCHEDULING",
    "STOPPING",
    "UPLOADING",
}
ERROR_STATES = {
    "CANCELED",
    "DELETE_FAILED",
    "FAILED",
    "FORBIDDEN",
    "REJECTED",
}


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def extract_field(value: Any, field: str) -> Any:
    current = to_jsonable(value)
    for part in field.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            current = current[int(part)]
            continue
        raise KeyError(field)
    return current


def render_result(
    value: Any,
    *,
    output: str = "table",
    field: str | None = None,
    no_color: bool = False,
    stream: TextIO = sys.stdout,
) -> None:
    if field:
        value = extract_field(value, field)
    data = to_jsonable(value)
    if output == "json":
        print(json.dumps(data, indent=2, sort_keys=True), file=stream)
        return
    if field:
        print(_format_scalar(data), file=stream)
        return
    use_color = _color_enabled(stream, no_color)
    items = _page_items(data)
    if items is not None:
        _render_rows(items, stream=stream, use_color=use_color)
        return
    if isinstance(data, list):
        _render_rows(data, stream=stream, use_color=use_color)
        return
    if isinstance(data, dict):
        _render_detail(data, stream=stream, use_color=use_color)
        return
    print(_format_scalar(data), file=stream)


def _page_items(data: Any) -> list[Any] | None:
    if not isinstance(data, dict) or "items" not in data:
        return None
    items = data.get("items")
    return items if isinstance(items, list) else None


def _render_detail(data: dict[str, Any], *, stream: TextIO, use_color: bool) -> None:
    rows = _flatten_detail(data)
    key_width = max([len("FIELD"), *(len(key) for key, _ in rows)], default=5)
    print(
        f"{_style('FIELD', CYAN, use_color):<{key_width + _ansi_width(CYAN, use_color)}}  "
        f"{_style('VALUE', CYAN, use_color)}",
        file=stream,
    )
    print(f"{'-' * key_width}  {'-' * 48}", file=stream)
    for key, value in rows:
        color = _value_color(key, value)
        print(f"{key:<{key_width}}  {_style(value, color, use_color)}", file=stream)


def _render_rows(rows: list[Any], *, stream: TextIO, use_color: bool) -> None:
    if not rows:
        print(_style("No results", DIM, use_color), file=stream)
        return
    normalized = [row if isinstance(row, dict) else {"value": row} for row in rows]
    columns = _columns(normalized)
    widths = {
        column: max(
            len(column.upper()),
            *(min(len(_format_value(row.get(column))), 48) for row in normalized),
        )
        for column in columns
    }
    header = "  ".join(
        _style(column.upper(), CYAN, use_color).ljust(
            widths[column] + _ansi_width(CYAN, use_color)
        )
        for column in columns
    )
    print(header, file=stream)
    print("  ".join("-" * widths[column] for column in columns), file=stream)
    for row in normalized:
        cells: list[str] = []
        for column in columns:
            value = _truncate(_format_value(row.get(column)), widths[column])
            color = _value_color(column, value)
            styled = _style(value, color, use_color)
            cells.append(styled.ljust(widths[column] + _ansi_width(color, use_color)))
        print("  ".join(cells), file=stream)


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "id",
        "resource_id",
        "name",
        "status",
        "status_message",
        "flavor",
        "created_at",
        "updated_at",
    ]
    present = {key for row in rows for key in row}
    ordered = [key for key in preferred if key in present]
    ordered.extend(sorted(present - set(ordered)))
    return ordered


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        return _format_mapping(value)
    if isinstance(value, list):
        return ", ".join(_format_value(item) for item in value) or "[]"
    return str(value)


def _flatten_detail(
    value: dict[str, Any],
    *,
    prefix: str = "",
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key, item in value.items():
        field = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, dict) and item:
            rows.extend(_flatten_detail(item, prefix=field))
        elif isinstance(item, list) and item and any(
            isinstance(element, (dict, list)) for element in item
        ):
            for index, element in enumerate(item):
                indexed_field = f"{field}.{index}"
                if isinstance(element, dict):
                    rows.extend(_flatten_detail(element, prefix=indexed_field))
                else:
                    rows.append((indexed_field, _format_value(element)))
        else:
            rows.append((field, _format_value(item)))
    return rows


def _format_mapping(value: dict[Any, Any]) -> str:
    if not value:
        return "{}"
    name = value.get("name")
    identifier = value.get("id")
    if name is not None:
        return str(name)
    if identifier is not None and len(value) == 1:
        return str(identifier)
    if value.get("source") == "huggingface" and value.get("huggingface_id"):
        return str(value["huggingface_id"])
    if value.get("source") == "platform":
        model = value.get("model")
        version = value.get("model_version")
        labels = [
            _format_mapping(item)
            for item in (model, version)
            if isinstance(item, dict) and item
        ]
        if labels:
            return " / ".join(labels)
    return ", ".join(
        f"{key}={_format_value(item)}" for key, item in sorted(value.items())
    )


def _format_scalar(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return _format_value(value)


def _value_color(key: str, value: str) -> str:
    if value == "-":
        return DIM
    normalized = value.upper()
    if key.lower() in {"id", "name", "resource_id"}:
        return CYAN
    if normalized in SUCCESS_STATES:
        return GREEN
    if normalized in TRANSITION_STATES:
        return YELLOW
    if normalized in ERROR_STATES:
        return RED
    return ""


def _color_enabled(stream: TextIO, no_color: bool) -> bool:
    return not no_color and "NO_COLOR" not in os.environ and stream.isatty()


def _style(value: str, color: str, enabled: bool) -> str:
    return f"{color}{value}{RESET}" if enabled and color else value


def _ansi_width(color: str, enabled: bool) -> int:
    return len(color) + len(RESET) if enabled and color else 0


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[: max(width - 1, 0)] + "…"
