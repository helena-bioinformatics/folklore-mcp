import json
import urllib.error
import urllib.request
from typing import Any

ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"
PROTOCOL = "2026-07-28"


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments, "_meta": {"io.modelcontextprotocol/protocolVersion": PROTOCOL, "io.modelcontextprotocol/clientCapabilities": {}}}}
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), headers={"Accept": "application/json", "Content-Type": "application/json", "MCP-Protocol-Version": PROTOCOL, "Mcp-Method": "tools/call", "Mcp-Name": name, "User-Agent": "dify-helena-folklore/0.1.0"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            document = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Folklore is temporarily unavailable.") from exc
    if "error" in document:
        raise RuntimeError(str(document["error"].get("message", "Folklore MCP error")))
    result = document.get("result", {})
    if result.get("isError"):
        content = result.get("content") or []
        raise RuntimeError(content[0].get("text", "Folklore tool error") if content else "Folklore tool error")
    value = result.get("structuredContent")
    return value if isinstance(value, dict) else result
