"""Connect an OpenAI Agents SDK agent to the public read-only MCP endpoint."""

import argparse
import asyncio

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter

ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"
SCIENTIFIC_TOOLS = [
    "search_variant_evidence",
    "search_variant_literature",
    "get_publication_details",
    "search_literature_corpus",
]


async def run(request: str) -> str:
    async with MCPServerStreamableHttp(
        name="Folklore Clinical Variant Interpretation MCP",
        params={"url": ENDPOINT, "timeout": 30},
        cache_tools_list=True,
        use_structured_content=True,
        tool_filter=create_static_tool_filter(allowed_tool_names=SCIENTIFIC_TOOLS),
    ) as server:
        agent = Agent(
            name="Public germline variant evidence reviewer",
            instructions=(
                "Use only a public variant expression. Never send patient, phenotype, "
                "family, segregation or private case data. Preserve resolved, ambiguous, "
                "not-found, invalid, unsupported and unavailable outcomes. Keep literature "
                "association separate from classification. State that automated results "
                "require qualified professional review and are not diagnosis or treatment."
            ),
            mcp_servers=[server],
        )
        result = await Runner.run(agent, request)
        return result.final_output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("request")
    args = parser.parse_args()
    print(asyncio.run(run(args.request)))


if __name__ == "__main__":
    main()
