"""Transparent stdio bridge to Folklore Clinical Variant Interpretation MCP."""

import asyncio
import time
from typing import Any

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server import create_proxy

ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"
SERVER_NAME = "Folklore Clinical Variant Interpretation MCP"
CLIENT_NAME = "Biorouter Folklore Clinical Variant Interpretation MCP extension"
INSTRUCTIONS = (
    "Use classify_germline_variant for germline variant classification. "
    "Retrieve gene identities, profiles, disease associations and publications with the matching tools. "
    "Preserve returned typed outcomes, source provenance and snapshot identity. "
    "Present ambiguous candidates for selection."
)


class PublicPostBudget:
    """Space metadata and tool POSTs together; stop this bridge after a 429."""

    def __init__(self, clock=time.monotonic, sleep=asyncio.sleep):
        self.clock = clock
        self.sleep = sleep
        self.lock = asyncio.Lock()
        self.next_at = 0.0
        self.blocked = False

    async def before_request(self, request: httpx.Request) -> None:
        if request.method != "POST":
            return
        async with self.lock:
            if self.blocked:
                raise RuntimeError("Upstream rate limit: stop and reconnect later.")
            delay = self.next_at - self.clock()
            if delay > 0:
                await self.sleep(delay)
            if self.blocked:
                raise RuntimeError("Upstream rate limit: stop and reconnect later.")
            self.next_at = self.clock() + 10.1

    async def after_response(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            self.blocked = True

    def http_client(self, **kwargs: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            **{
                "timeout": httpx.Timeout(60, read=60),
                **kwargs,
                "follow_redirects": False,
                "event_hooks": {
                    "request": [self.before_request],
                    "response": [self.after_response],
                },
            }
        )


def create_server(target: Any = ENDPOINT) -> Any:
    """Create a local stdio proxy without copying the hosted scientific logic."""
    if target == ENDPOINT:
        budget = PublicPostBudget()
        target = StreamableHttpTransport(
            ENDPOINT, httpx_client_factory=budget.http_client
        )
    backend = Client(target, name=CLIENT_NAME, timeout=60)
    return create_proxy(backend, name=SERVER_NAME, instructions=INSTRUCTIONS)
