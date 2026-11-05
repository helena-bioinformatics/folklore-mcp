"""Bounded source-object relay invariants (CR026)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .common import CaseError

PACKET = json.loads(
    (Path(__file__).with_name("data") / "source-browse-contract.json").read_text()
)
TOOL = "browse_source_objects"
MAX_BODY_BYTES = 32768
MAX_API_BYTES = 262144
TOTAL_TIMEOUT = 30
UNAVAILABLE_REASONS = frozenset(
    (
        "not_found",
        "access_denied",
        "timeout",
        "provider_unavailable",
        "unsupported_version",
    )
)


def supported_input_key(key):
    return not (
        key.startswith("/")
        or "\\" in key
        or any(ord(c) < 32 for c in key)
        or any(part in {".", ".."} for part in key.split("/"))
    )


def _require(condition):
    if not condition:
        raise CaseError("source_contract_mismatch")


def _timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0))


def validate_page(value, args):
    """Reject inconsistent authority, metadata or selection without disclosing a page."""
    try:
        _require(value["context_binding_id"] == args["context_binding_id"])
        _require(value["connection_id"] == args["connection_id"])
        records = value["records"]
        _require(value["returned_count"] == len(records))
        _require(len(records) <= args.get("limit", 10))
        _require(value["has_more"] == (value["next_cursor"] is not None))
        parent = value["parent"]
        _require((parent is None) == (args.get("parent_handle") is None))
        seen = set()
        for record in records:
            kind = record["kind"]
            if parent is None:
                _require(kind == "root")
                identity = record["root_index"]
                _require(identity not in seen)
                seen.add(identity)
                prefix = record["key_prefix"]
                _require(prefix.endswith("/") and not prefix.startswith("/"))
                _require(supported_input_key(prefix))
                continue
            _require(kind in {"folder", "file"})
            prefix = parent["prefix"]
            _require(prefix.endswith("/"))
            key = record["prefix"] if kind == "folder" else record["key"]
            _require(key.startswith(prefix))
            tail = key[len(prefix) :]
            if kind == "folder":
                _require(tail.endswith("/") and "/" not in tail[:-1])
            else:
                _require("/" not in tail)
            identity = (kind, key)
            _require(identity not in seen)
            seen.add(identity)
            if kind == "folder":
                continue
            state = record["metadata_state"]
            version, size, modified = (
                record["version_id"],
                record["size_bytes"],
                record["last_modified"],
            )
            reason = record["reason"]
            selection = record["selection"]
            if state == "versioned":
                _require(
                    isinstance(version, str)
                    and version.lower() not in {"null", "latest"}
                    and not any(ord(c) < 32 for c in version)
                    and size is not None
                    and modified is not None
                )
                _timestamp(modified)
                expected = supported_input_key(key)
                _require(record["selectable"] is expected)
                _require(reason == (None if expected else "unsupported_input_key"))
                if expected:
                    _require(
                        selection
                        == {
                            "connection_id": args["connection_id"],
                            "bucket": parent["bucket"],
                            "key": key,
                            "version_id": version,
                            "size_bytes": size,
                        }
                    )
                else:
                    _require(selection is None)
            elif state == "unversioned":
                _require(
                    version is None
                    and size is not None
                    and modified is not None
                    and reason == "versioning_required"
                    and record["selectable"] is False
                    and selection is None
                )
                _timestamp(modified)
            else:
                _require(
                    state == "unavailable"
                    and all(v is None for v in (version, size, modified))
                    and reason in UNAVAILABLE_REASONS
                    and record["selectable"] is False
                    and selection is None
                )
        return value
    except CaseError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError):
        raise CaseError("source_contract_mismatch") from None
