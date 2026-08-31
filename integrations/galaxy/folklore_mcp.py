#!/usr/bin/env python3
import argparse
import json
import urllib.error
import urllib.request

PROTOCOL = "2026-07-28"
ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interpret a public germline variant with Folklore MCP"
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
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
