#!/usr/bin/env python3
"""One read-only BRCA1 identity/snapshot probe of the hosted JSON response path."""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"
PROTOCOL = "2026-07-28"
REQUEST_ID = "brca1-identity-smoke"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 150


class SmokeFailure(ValueError):
    """The bounded identity smoke did not meet its acceptance criteria."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_request() -> Request:
    payload = {
        "jsonrpc": "2.0",
        "id": REQUEST_ID,
        "method": "tools/call",
        "params": {
            "name": "resolve_gene",
            "arguments": {"query": "BRCA1"},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": PROTOCOL,
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }
    return Request(
        ENDPOINT,
        data=json.dumps(payload, allow_nan=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL,
            "Mcp-Method": "tools/call",
            "Mcp-Name": "resolve_gene",
            "User-Agent": "Folklore-Identity-Snapshot-Smoke/1.0",
        },
    )


def unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SmokeFailure("Duplicate JSON key.")
        result[key] = value
    return result


def reject_constant(value: str):
    raise SmokeFailure(f"Non-finite JSON value: {value}.")


def check_identity(message: dict) -> dict:
    if not isinstance(message, dict):
        raise SmokeFailure("JSON-RPC response must be an object.")
    if message.get("jsonrpc") != "2.0" or message.get("id") != REQUEST_ID:
        raise SmokeFailure("JSON-RPC version or request identity mismatch.")
    if "error" in message or "result" not in message:
        raise SmokeFailure("JSON-RPC error or missing result.")
    tool = message["result"]
    if not isinstance(tool, dict) or tool.get("isError", False) is not False:
        raise SmokeFailure("MCP tool error or invalid result.")
    envelope = tool.get("structuredContent")
    if not isinstance(envelope, dict):
        raise SmokeFailure("Missing structured gene envelope.")
    if (
        envelope.get("contract_version") != "2"
        or "adapter_error" not in envelope
        or envelope["adapter_error"] is not None
    ):
        raise SmokeFailure("Adapter error or unknown envelope version.")
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise SmokeFailure("Missing gene identity result.")
    candidates = result.get("candidates")
    if (
        result.get("schema_version") != "1.0"
        or result.get("status") != "exact"
        or result.get("normalized_query") != "BRCA1"
        or result.get("complete") is not True
        or type(result.get("candidate_total")) is not int
        or result["candidate_total"] != 1
        or not isinstance(candidates, list)
        or len(candidates) != 1
    ):
        raise SmokeFailure(
            "Expected one exact BRCA1 identity; preserve other outcomes."
        )
    snapshot = result.get("identity_snapshot_id")
    if not isinstance(snapshot, str) or not re.fullmatch("[a-f0-9]{64}", snapshot):
        raise SmokeFailure("Invalid identity snapshot.")
    candidate = candidates[0]
    identity = candidate.get("identity") if isinstance(candidate, dict) else None
    if (
        not isinstance(identity, dict)
        or identity.get("gene_id") != "HGNC:1100"
        or identity.get("symbol") != "BRCA1"
        or identity.get("status") != "Approved"
        or not isinstance(identity.get("source_id"), str)
        or not identity["source_id"].strip()
    ):
        raise SmokeFailure("BRCA1 identity or source reference mismatch.")
    return envelope


def run_probe(opener=None) -> dict:
    """Send once. No discovery, initialization, redirect or automatic retry."""
    sender = opener if opener is not None else build_opener(NoRedirect())
    with sender.open(make_request(), timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise SmokeFailure(f"HTTP {response.status}; no scientific success.")
        if response.headers.get_content_type() != "application/json":
            raise SmokeFailure("Non-JSON response; SSE is not qualified by this smoke.")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise SmokeFailure("Response exceeds the 2 MiB smoke limit.")
    message = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )
    return check_identity(message)


def main() -> int:
    try:
        envelope = run_probe()
    except HTTPError as exc:
        detail = " Shared IP budget refused admission." if exc.code == 429 else ""
        print(f"FAIL: HTTP {exc.code}.{detail} No automatic retry.", file=sys.stderr)
        return 1
    except (URLError, OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "checked_at": datetime.now(UTC).isoformat(),
                "status": "PASS",
                "scope": "2026-07-28 raw HTTP JSON BRCA1 identity and snapshot only",
                "structuredContent": envelope,
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
