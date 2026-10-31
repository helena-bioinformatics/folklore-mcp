"""Transparent stdio bridge to Folklore Clinical Variant Interpretation MCP."""

from typing import Any

from fastmcp import Client
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


def create_server(target: Any = ENDPOINT) -> Any:
    """Create a local stdio proxy without copying the hosted scientific logic."""
    backend = Client(target, name=CLIENT_NAME, timeout=60)
    return create_proxy(backend, name=SERVER_NAME, instructions=INSTRUCTIONS)
