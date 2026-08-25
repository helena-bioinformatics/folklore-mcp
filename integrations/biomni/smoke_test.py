"""Verify the public Folklore MCP connection through Biomni's stdio pattern."""

import asyncio
import json
from pathlib import Path

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

INTEGRATION_DIR = Path(__file__).resolve().parent
CONFIG_PATH = INTEGRATION_DIR / "mcp_config.yaml"
EXPECTED_TOOLS = {
    "search_variant_evidence",
    "search_variant_literature",
    "get_publication_details",
    "search_literature_corpus",
}


def load_server_parameters() -> StdioServerParameters:
    """Load the same command array that Biomni consumes from YAML."""
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    command = config["mcp_servers"]["folklore_clinical_variant_interpretation_mcp"][
        "command"
    ]
    executable, *arguments = command
    return StdioServerParameters(command=executable, args=arguments)


async def run_smoke_test() -> dict[str, object]:
    """Discover all tools and confirm ambiguity is preserved for a public rsID."""
    parameters = load_server_parameters()
    async with asyncio.timeout(90):
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                initialization = await session.initialize()
                listed = await session.list_tools()
                tools = {tool.name: tool for tool in listed.tools}
                assert set(tools) == EXPECTED_TOOLS

                evidence_schema = tools["search_variant_evidence"].input_schema
                assert evidence_schema["additionalProperties"] is False
                assert evidence_schema["required"] == ["query"]
                assert set(evidence_schema["properties"]) == {"assembly", "query"}

                response = await session.call_tool(
                    "search_variant_evidence",
                    {"assembly": "GRCh38", "query": "rs80357914"},
                )
                assert response.is_error is False

                structured = response.structured_content
                assert structured is not None
                assert structured["adapter_error"] is None
                assert structured["result"]["status"] == "ambiguous"
                assert len(structured["result"]["candidates"]) >= 2
                assert (
                    structured["usage_boundary"]["patient_context_evaluated"] is False
                )
                assert structured["usage_boundary"]["review_required"] is True

                return {
                    "protocol_version": initialization.protocol_version,
                    "tools": sorted(tools),
                    "probe": {
                        "query": "rs80357914",
                        "status": structured["result"]["status"],
                        "candidate_count": len(structured["result"]["candidates"]),
                    },
                    "patient_context_evaluated": False,
                    "professional_review_required": True,
                }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_smoke_test()), indent=2, sort_keys=True))
