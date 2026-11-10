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
    "Use public reference inputs only. Do not provide patient, phenotype, family, "
    "segregation or private case data. Public phenotype reference terms in literature "
    "queries must not describe an individual patient or private case. "
    "Use classify_germline_variant for germline variant classification. "
    "Retrieve gene identities, profiles, disease associations and publications with the matching tools. "
    "Preserve returned typed outcomes, source provenance and snapshot identity. "
    "Present ambiguous candidates for selection. "
    "Results require qualified professional review and are not a diagnosis, "
    "treatment recommendation or standalone clinical report."
)


class PublicPostBudget:
    """Share the six-request burst and refill across metadata and tool POSTs."""

    def __init__(self, clock=time.monotonic, sleep=asyncio.sleep):
        self.clock = clock
        self.sleep = sleep
        self.lock = asyncio.Lock()
        self.tokens = 6.0
        self.updated_at = self.clock()
        self.blocked = False

    async def before_request(self, request: httpx.Request) -> None:
        if request.method != "POST":
            return
        async with self.lock:
            if self.blocked:
                raise RuntimeError("Upstream rate limit: stop and reconnect later.")
            now = self.clock()
            self.tokens = min(6.0, self.tokens + (now - self.updated_at) / 10.1)
            self.updated_at = now
            if self.tokens < 1:
                await self.sleep((1 - self.tokens) * 10.1)
                now = self.clock()
                self.tokens = min(6.0, self.tokens + (now - self.updated_at) / 10.1)
                self.updated_at = now
            if self.blocked:
                raise RuntimeError("Upstream rate limit: stop and reconnect later.")
            self.tokens = max(0.0, self.tokens - 1)

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
