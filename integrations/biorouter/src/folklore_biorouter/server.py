"""Transparent stdio bridge to Folklore Clinical Variant Interpretation MCP."""

from typing import Any

from fastmcp import Client
from fastmcp.server import create_proxy

ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"
SERVER_NAME = "Folklore Clinical Variant Interpretation MCP"
CLIENT_NAME = "Biorouter Folklore Clinical Variant Interpretation MCP extension"
INSTRUCTIONS = (
    "Helena Bioinformatics publishes Folklore Clinical Variant Interpretation MCP. "
    "Use public variant-level input only. Do not provide patient, phenotype, family, "
    "segregation or private case data. Preserve explicit outcome states, never select "
    "an ambiguous candidate automatically, and require qualified professional review."
)


def create_server(target: Any = ENDPOINT) -> Any:
    """Create a local stdio proxy without copying the hosted scientific logic."""
    backend = Client(target, name=CLIENT_NAME, timeout=60)
    return create_proxy(backend, name=SERVER_NAME, instructions=INSTRUCTIONS)
