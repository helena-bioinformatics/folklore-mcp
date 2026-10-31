#!/usr/bin/env python3
"""Read-only live discovery smoke test that sends no variant data."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from client_rate_budget import RateBudget, RateLimited

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "registry" / "discovery-contract.json").read_text())


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


urlopen = build_opener(NoRedirect()).open


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key in discovery response")
        value[key] = item
    return value


def call(method: str, *, budget: RateBudget, deadline: float) -> dict:
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
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": CONTRACT["protocolVersion"],
            "Mcp-Method": method,
            "User-Agent": "Helena-Folklore-Public-Smoke/1.0",
        },
    )

    def send_once(remaining: float) -> dict:
        try:
            with urlopen(request, timeout=min(20.0, remaining)) as response:  # noqa: S310 - fixed public URL
                if response.headers.get_content_type() != "application/json":
                    raise ValueError(
                        "This hosted discovery smoke requires JSON, not SSE"
                    )
                raw = response.read(2_097_153)
                if len(raw) > 2_097_152:
                    raise ValueError("Discovery response exceeded the 2 MiB bound")
                document = json.loads(raw, object_pairs_hook=unique_object)
                if (
                    not isinstance(document, dict)
                    or document.get("jsonrpc") != "2.0"
                    or type(document.get("id")) is not int
                    or document["id"] != 1
                    or not isinstance(document.get("result"), dict)
                    or "error" in document
                ):
                    raise ValueError("Invalid or failed discovery RPC response")
                return document
        except HTTPError as error:
            if error.code == 429:
                raise RateLimited(error.headers.get("Retry-After")) from error
            raise

    return budget.execute(send_once, deadline=deadline)


def main() -> int:
    observed: dict[str, list[str] | str] = {}
    budget = RateBudget(max_attempts=4)
    deadline = time.monotonic() + 90.0
    discover = call("server/discover", budget=budget, deadline=deadline)["result"]
    observed["protocol"] = discover["supportedVersions"][0]
    for method, key, field in (
        ("tools/list", "tools", "tools"),
        ("prompts/list", "prompts", "prompts"),
        ("resources/list", "resources", "resources"),
    ):
        result = call(method, budget=budget, deadline=deadline)["result"]
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
