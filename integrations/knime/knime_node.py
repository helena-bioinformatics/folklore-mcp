"""KNIME Python Script node for Folklore germline variant evidence."""

import json
import urllib.error
import urllib.request

import knime.scripting.io as knio
import pyarrow as pa

ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"
PROTOCOL = "2026-07-28"


def call_folklore(query: str) -> dict:
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
    rows.append({"variant": value, "folklore_result_json": json.dumps(call_folklore(value))})

knio.output_tables[0] = knio.Table.from_pyarrow(pa.Table.from_pylist(rows))
