#!/usr/bin/env python3
import argparse
import json
import urllib.error
import urllib.request
from uuid import UUID

PROTOCOL = "2026-07-28"
ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"


def journey_metadata(analytics=None):
    """Project caller-owned, explicitly enabled analytics; never infer identity."""
    if not isinstance(analytics, dict) or analytics.get("analytics_opt_in") is not True:
        return {}

    def valid_id(value):
        if not isinstance(value, str):
            return False
        try:
            parsed = UUID(value)
        except (ValueError, AttributeError):
            return False
        return parsed.version == 4 and str(parsed) == value

    user_id = analytics.get("analytics_user_id")
    if not valid_id(user_id):
        return {}
    context = {"opt_in": True, "user_id": user_id}
    session_id = analytics.get("analytics_session_id")
    if valid_id(session_id):
        context["session_id"] = session_id
    intent = analytics.get("analytics_intent")
    if intent in (
        "variant_evidence",
        "literature_review",
        "gene_disease_review",
        "infrastructure_support",
    ):
        context["intent"] = intent
    return {"io.helena/analytics": context}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interpret a public germline variant with Folklore MCP"
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--analytics-opt-in", action="store_true")
    parser.add_argument("--analytics-user-id")
    parser.add_argument("--analytics-session-id")
    parser.add_argument(
        "--analytics-intent",
        choices=[
            "variant_evidence",
            "literature_review",
            "gene_disease_review",
            "infrastructure_support",
        ],
    )
    args = parser.parse_args()
    analytics = vars(args)
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_variant_evidence",
            "arguments": {"assembly": "GRCh38", "query": args.query},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": PROTOCOL,
                "io.modelcontextprotocol/clientCapabilities": {},
                **journey_metadata(analytics),
            },
        },
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode(),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": PROTOCOL,
            "Mcp-Method": "tools/call",
            "Mcp-Name": "search_variant_evidence",
            "User-Agent": "galaxy-folklore-mcp/0.1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            document = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        parser.error(f"Folklore is unavailable: {exc}")
    result = document.get("result", {})
    if "error" in document or result.get("isError"):
        parser.error("Folklore returned a bounded tool error")
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(
            result.get("structuredContent", result),
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
