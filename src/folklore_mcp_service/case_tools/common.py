"""Shared case-tool errors and exact JSON encoding (CR024)."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
SOFTWARE_VERSION = "1.2.0"
MAX_RESPONSE_BYTES = 65536
API_ORIGIN = "https://api.helena.bio"
API_PREFIX = "/folklore/v1"


class CaseError(Exception):
    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        retryable: bool = False,
        request_id: str | None = None,
        details: dict | None = None,
    ):
        self.code = code
        self.message = message or code.replace("_", " ").capitalize()
        self.retryable = retryable
        self.request_id = request_id
        self.details = details or {}
        super().__init__(self.message)

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "request_id": self.request_id,
            "details": self.details,
        }


def decimal_string(value: int | Decimal) -> str:
    if isinstance(value, bool):
        raise CaseError("invalid_input")
    if isinstance(value, int):
        result = str(value)
    elif isinstance(value, Decimal) and value.is_finite():
        sign, digits, exponent = value.as_tuple()
        if abs(exponent) > 1024 or len(digits) > 1024:
            raise CaseError(
                "export_budget_exceeded",
                details={"limit_name": "number_characters", "limit": 1024},
            )
        result = format(value, "f")
        if "." in result:
            result = result.rstrip("0").rstrip(".")
        if value == 0:
            result = "0"
    else:
        raise CaseError("unsupported_export_shape")
    if len(result) > 1024:
        raise CaseError(
            "export_budget_exceeded",
            details={"limit_name": "number_characters", "limit": 1024},
        )
    return result


def _number(token: str) -> int | Decimal:
    if len(token) > 1024:
        raise CaseError(
            "export_budget_exceeded",
            details={"limit_name": "number_characters", "limit": 1024},
        )
    match = re.search(r"[eE]([+-]?\d+)$", token)
    if match and (len(match[1].lstrip("+-")) > 4 or abs(int(match[1])) > 1024):
        raise CaseError(
            "export_budget_exceeded",
            details={"limit_name": "number_exponent", "limit": 1024},
        )
    value = Decimal(token) if any(c in token for c in ".eE") else int(token)
    decimal_string(value)
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CaseError(
                "unsupported_export_shape", details={"reason": "duplicate_json_key"}
            )
        result[key] = value
    return result


def _nonfinite(_: str):
    raise CaseError("unsupported_export_shape", details={"reason": "nonfinite_number"})


def parse_json(raw: bytes) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            parse_int=_number,
            parse_float=_number,
            parse_constant=_nonfinite,
            object_pairs_hook=_pairs,
        )
    except CaseError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise CaseError(
            "unsupported_export_shape", details={"reason": "invalid_json"}
        ) from None


def wire_numbers(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, Decimal)):
        return decimal_string(value)
    if isinstance(value, list):
        return [wire_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: wire_numbers(item) for key, item in value.items()}
    raise CaseError("unsupported_export_shape")


def json_bytes(value: Any) -> bytes:
    def encode(item):
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=True)
        if isinstance(item, (int, Decimal)):
            return decimal_string(item)
        if isinstance(item, float):
            return decimal_string(Decimal(str(item)))
        if isinstance(item, list):
            return "[" + ",".join(encode(element) for element in item) + "]"
        if isinstance(item, dict) and all(isinstance(key, str) for key in item):
            return (
                "{"
                + ",".join(
                    encode(key) + ":" + encode(item[key]) for key in sorted(item)
                )
                + "}"
            )
        raise TypeError("Unsupported JSON value")

    return encode(value).encode("utf-8")


def _private_directory(path: Path) -> Path:
    import os
    import stat

    path = path.absolute()
    if ".." in path.parts:
        raise CaseError("invalid_state_directory")
    # Every ancestor must be stable under the configured user's authority.
    for parent in reversed(path.parents):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            parent.mkdir(mode=0o700, exist_ok=True)
            info = parent.lstat()
        mode = stat.S_IMODE(info.st_mode)
        sticky_root = info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX)
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid not in (0, os.geteuid())
            or (mode & 0o022 and not sticky_root)
        ):
            raise CaseError("invalid_state_directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    before = path.lstat()
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700
            or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)
        ):
            raise CaseError("invalid_state_directory")
    finally:
        os.close(fd)
    return path


def private_directory(path: Path) -> Path:
    try:
        return _private_directory(path)
    except OSError:
        raise CaseError("invalid_state_directory") from None
