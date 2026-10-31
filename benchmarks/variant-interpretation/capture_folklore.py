#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, build_opener

ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"
ROOT = Path(__file__).resolve().parent


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_rpc_response(value: Any, request_id: int) -> dict[str, Any]:
    valid = (
        isinstance(value, dict)
        and value.get("jsonrpc") == "2.0"
        and type(value.get("id")) is type(request_id)
        and value.get("id") == request_id
        and (("result" in value) != ("error" in value))
    )
    if valid and "result" in value:
        valid = isinstance(value["result"], dict)
    if valid and "error" in value:
        error = value["error"]
        valid = (
            isinstance(error, dict)
            and type(error.get("code")) is int
            and isinstance(error.get("message"), str)
        )
    if not valid:
        return {
            "error": {
                "code": "invalid_rpc_response",
                "message": "JSON-RPC envelope or request identity mismatch.",
            },
            "unvalidated_response": value,
        }
    return value


def _request(query: str, assembly: str, request_id: int) -> dict[str, Any]:
    name = "classify_germline_variant"
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": {"query": query, "assembly": assembly},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "folklore-public-variant-benchmark/1.7",
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": "tools/call",
            "Mcp-Name": name,
        },
        method="POST",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=150) as response:
            if response.headers.get_content_type() != "application/json":
                raise ValueError("Expected JSON response")
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("Response exceeds 2 MiB")
            return validate_rpc_response(json.loads(raw), request_id)
    except HTTPError as exc:
        return {
            "error": {
                "http_status": exc.code,
                "retry_after": exc.headers.get("Retry-After"),
                "message": "HTTP request failed; no automatic retry.",
            }
        }


def _availability(interpretation: dict[str, Any]) -> dict[str, str]:
    evidence = interpretation.get("evidence") or {}
    fields = (
        "clinvar",
        "expert",
        "predictors",
        "spliceai",
        "conservation",
        "gene_constraints",
        "dosage",
        "population",
    )
    return {
        field: str((evidence.get(field) or {}).get("availability", "not_reported"))
        for field in fields
    }


def _record(
    case: dict[str, str], response: dict[str, Any], elapsed_ms: int
) -> dict[str, Any]:
    rpc_result = response.get("result") or {}
    structured = rpc_result.get("structuredContent") or {}
    result = structured.get("result") or {}
    interpretation = result.get("interpretation") or {}
    classification = interpretation.get("classification") or {}
    annotation = interpretation.get("annotation") or {}
    provenance = interpretation.get("provenance") or {}
    identity = result.get("identity")
    return {
        **case,
        "observed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "endpoint": ENDPOINT,
        "rpc_error": response.get("error"),
        "tool_error": bool(rpc_result.get("isError")),
        "contract_version": structured.get("contract_version"),
        "search_contract_version": result.get("search_contract_version"),
        "status": result.get("status"),
        "normalized_query": (result.get("resolution") or {}).get("normalized_query"),
        "identity": identity,
        "candidates": result.get("candidates") or [],
        "adapter_error": structured.get("adapter_error"),
        "interpretation_status": interpretation.get("status"),
        "raw_response": response,
        "gene_symbol": annotation.get("gene_symbol"),
        "transcript_id": annotation.get("transcript_id"),
        "automated_class": classification.get("automated_class"),
        "criteria": classification.get("criteria"),
        "evidence_availability": _availability(interpretation),
        "classifier_version": provenance.get("classifier_version"),
        "reference_versions": provenance.get("reference_versions") or [],
        "elapsed_ms": elapsed_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture the public Folklore benchmark baseline."
    )
    parser.add_argument("--cases", type=Path, default=ROOT / "cases.csv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay-seconds", type=float, default=10.0)
    args = parser.parse_args()
    if args.delay_seconds < 10:
        parser.error("--delay-seconds must be at least 10 for the shared IP allowance")
    with args.cases.open(newline="", encoding="utf-8") as source:
        cases = list(csv.DictReader(source))
    with args.output.open("x", encoding="utf-8") as output:
        for request_id, case in enumerate(cases, start=1):
            started = time.perf_counter()
            try:
                response = _request(case["input"], case["assembly"], request_id)
            except Exception as exc:
                response = {"error": {"type": type(exc).__name__, "message": str(exc)}}
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            output.write(
                json.dumps(_record(case, response, elapsed_ms), sort_keys=True) + "\n"
            )
            output.flush()
            print(
                case["case_id"],
                _record(case, response, elapsed_ms)["status"],
                flush=True,
            )
            if (response.get("error") or {}).get("http_status") == 429:
                break
            if request_id < len(cases):
                time.sleep(max(args.delay_seconds, 0.0))


if __name__ == "__main__":
    main()
