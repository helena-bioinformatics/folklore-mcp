#!/usr/bin/env python3
"""Read-only live discovery smoke test that sends no variant data."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "registry" / "discovery-contract.json").read_text())


def call(method: str) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": CONTRACT["protocolVersion"],
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {
                    "name": "folklore-public-smoke",
                    "version": "1.0",
                },
            }
        },
    }
    request = Request(
        CONTRACT["endpoint"],
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "MCP-Protocol-Version": CONTRACT["protocolVersion"],
            "Mcp-Method": method,
            "User-Agent": "Helena-Folklore-Public-Smoke/1.0",
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed public URL
        return json.load(response)


def main() -> int:
    observed: dict[str, list[str] | str] = {}
    discover = call("server/discover")["result"]
    observed["protocol"] = discover["supportedVersions"][0]
    for method, key, field in (
        ("tools/list", "tools", "tools"),
        ("prompts/list", "prompts", "prompts"),
        ("resources/list", "resources", "resources"),
    ):
        result = call(method)["result"]
        identity = "uri" if key == "resources" else "name"
        observed[key] = [item[identity] for item in result[field]]

    expected = {
        "protocol": CONTRACT["protocolVersion"],
        "tools": CONTRACT["tools"],
        "prompts": CONTRACT["prompts"],
        "resources": CONTRACT["resources"],
    }
    print(json.dumps(observed, indent=2))
    return 0 if observed == expected else 1


if __name__ == "__main__":
    sys.exit(main())
