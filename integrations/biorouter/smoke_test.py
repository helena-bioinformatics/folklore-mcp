"""Verify the Biorouter bridge against the live public endpoint."""

import asyncio
import json

from fastmcp import Client
from folklore_biorouter.server import create_server

EXPECTED_TOOLS = {
    "classify_germline_variant",
    "search_variant_literature",
    "get_publication_details",
    "search_literature_corpus",
    "support_helena",
    "get_gene_disease_associations",
    "search_disease_genes",
    "resolve_gene",
    "get_gene_profile",
    "get_gene_section",
    "search_gene_literature",
}


async def run_smoke_test() -> dict[str, object]:
    """Discover the tools and confirm that ambiguity remains fail-closed."""
    async with asyncio.timeout(90):
        async with Client(
            create_server(), name="Biorouter integration smoke test"
        ) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed}
            assert set(tools) == EXPECTED_TOOLS

            evidence_schema = tools["classify_germline_variant"].inputSchema
            assert evidence_schema["additionalProperties"] is False
            assert evidence_schema["required"] == ["query"]
            assert set(evidence_schema["properties"]) == {"assembly", "query"}

            response = await client.call_tool(
                "classify_germline_variant",
                {"assembly": "GRCh38", "query": "rs80357914"},
            )
            structured = response.structured_content
            assert structured is not None
            assert structured["adapter_error"] is None
            assert structured["result"]["status"] == "ambiguous"
            assert len(structured["result"]["candidates"]) >= 2
            assert structured["contract_version"] == "2"
            assert structured["contract_version"] == "2"

            return {
                "tools": sorted(tools),
                "probe": {
                    "query": "rs80357914",
                    "status": structured["result"]["status"],
                    "candidate_count": len(structured["result"]["candidates"]),
                },
            }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_smoke_test()), indent=2, sort_keys=True))
