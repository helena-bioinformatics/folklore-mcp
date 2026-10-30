"""KNIME Python Script node for Folklore germline variant evidence."""

import json
import urllib.error
import urllib.request
from uuid import UUID

import knime.scripting.io as knio
import pyarrow as pa

ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"
PROTOCOL = "2026-07-28"


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


def call_folklore(query: str, *, analytics=None) -> dict:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_variant_evidence",
            "arguments": {"assembly": "GRCh38", "query": query},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": PROTOCOL,
                "io.modelcontextprotocol/clientCapabilities": {},
                **journey_metadata(analytics),
            },
        },
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": PROTOCOL,
            "Mcp-Method": "tools/call",
            "Mcp-Name": "search_variant_evidence",
            "User-Agent": "knime-folklore-mcp/0.1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            document = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Folklore is temporarily unavailable") from exc
    result = document.get("result", {})
    if "error" in document or result.get("isError"):
        raise RuntimeError("Folklore returned a bounded tool error")
    return result.get("structuredContent", result)


input_table = knio.input_tables[0].to_pyarrow()
variants = input_table.column(0).to_pylist()
rows = []
for variant in variants:
    if variant is None or not str(variant).strip():
        continue
    value = str(variant).strip()
    rows.append(
        {
            "variant": value,
            "folklore_result_json": json.dumps(
                call_folklore(value, analytics=dict(knio.flow_variables))
            ),
        }
    )

knio.output_tables[0] = knio.Table.from_pyarrow(pa.Table.from_pylist(rows))
