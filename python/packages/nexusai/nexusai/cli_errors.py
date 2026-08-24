from __future__ import annotations

import sys
import traceback
from enum import IntEnum
from typing import TextIO

from .cli_render import RED, _color_enabled, _style
from .errors import OneNexusAPIError, OneNexusError


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE = 2
    AUTH = 3
    VALIDATION_OR_CONFLICT = 4
    NOT_FOUND = 5
    TRANSIENT_EXHAUSTED = 6
    UNEXPECTED = 70
    CANCELED = 130


def render_error(
    error: BaseException,
    *,
    no_color: bool = False,
    debug: bool = False,
    stream: TextIO = sys.stderr,
) -> ExitCode:
    status: str = "-"
    code = type(error).__name__
    detail = str(error) or "Unexpected failure"
    request_id = "-"

    if isinstance(error, OneNexusAPIError):
        status = str(error.status_code)
        code = error.problem_type or "about:blank"
        detail = error.detail
        request_id = error.request_id or "-"

    use_color = _color_enabled(stream, no_color)
    print(_style("ERROR", RED, use_color), file=stream)
    for key, value in (
        ("HTTP status", status),
        ("Code", code),
        ("Detail", detail),
        ("Request ID", request_id),
    ):
        print(f"{key:<12}  {value}", file=stream)
    if debug:
        traceback.print_exception(error, file=stream)
    return exit_code_for(error)


def exit_code_for(error: BaseException) -> ExitCode:
    if isinstance(error, KeyboardInterrupt):
        return ExitCode.CANCELED
    if isinstance(error, OneNexusAPIError):
        if error.status_code in {401, 403}:
            return ExitCode.AUTH
        if error.status_code == 404:
            return ExitCode.NOT_FOUND
        if error.status_code in {400, 409, 422}:
            return ExitCode.VALIDATION_OR_CONFLICT
        if error.status_code in {408, 429} or error.status_code >= 500:
            return ExitCode.TRANSIENT_EXHAUSTED
    if isinstance(error, (OneNexusError, TimeoutError, ConnectionError)):
        return ExitCode.TRANSIENT_EXHAUSTED
    return ExitCode.UNEXPECTED
