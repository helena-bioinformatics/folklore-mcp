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

ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"
ROOT = Path(__file__).resolve().parent


def _request(
    query: str, assembly: str, request_id: int, max_retries: int
) -> dict[str, Any]:
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": "search_variant_evidence",
                "arguments": {"query": query, "assembly": assembly},
            },
        }
    ).encode()
    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "folklore-public-variant-benchmark/1",
        },
        method="POST",
    )
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code != 429 or attempt == max_retries:
                try:
                    return json.loads(exc.read())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    raise
            retry_after = exc.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after else 2**attempt
            time.sleep(min(max(wait_seconds, 1.0), 30.0))
    raise RuntimeError("unreachable retry state")


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
    boundary = structured.get("usage_boundary") or {}
    identity = result.get("identity")
    if identity is None:
        candidates = result.get("candidates") or []
        identity = (candidates[0].get("identity") if candidates else None) or {}
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
        "gene_symbol": annotation.get("gene_symbol"),
        "transcript_id": annotation.get("transcript_id"),
        "automated_class": classification.get("automated_class"),
        "criteria": classification.get("criteria"),
        "evidence_availability": _availability(interpretation),
        "classifier_version": provenance.get("classifier_version"),
        "reference_versions": provenance.get("reference_versions") or [],
        "review_required": boundary.get("review_required"),
        "patient_context_evaluated": boundary.get("patient_context_evaluated"),
        "not_for": boundary.get("not_for") or [],
        "elapsed_ms": elapsed_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture the public Folklore benchmark baseline."
    )
    parser.add_argument("--cases", type=Path, default=ROOT / "cases.csv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args()
    with args.cases.open(newline="", encoding="utf-8") as source:
        cases = list(csv.DictReader(source))
    with args.output.open("w", encoding="utf-8") as output:
        for request_id, case in enumerate(cases, start=1):
            started = time.perf_counter()
            try:
                response = _request(
                    case["input"], case["assembly"], request_id, args.max_retries
                )
            except Exception as exc:
                response = {"error": {"type": type(exc).__name__, "message": str(exc)}}
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            output.write(
                json.dumps(_record(case, response, elapsed_ms), sort_keys=True) + "\n"
            )
            if request_id < len(cases):
                time.sleep(max(args.delay_seconds, 0.0))


if __name__ == "__main__":
    main()
