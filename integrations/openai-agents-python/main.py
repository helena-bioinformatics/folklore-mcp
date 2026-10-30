"""Connect an OpenAI Agents SDK agent to the public read-only MCP endpoint."""

import argparse
import asyncio
from uuid import UUID

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter

ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"
SCIENTIFIC_TOOLS = [
    "search_variant_evidence",
    "search_variant_literature",
    "get_publication_details",
    "search_literature_corpus",
]


def journey_metadata(analytics=None):
    """Project caller-owned, explicitly enabled analytics; never infer identity."""
    if not isinstance(analytics, dict) or analytics.get("analytics_opt_in") is not True:
        return {}

    def valid_id(value):
        if not isinstance(value, str):
            return False
        try:
            parsed = UUID(value)
        except (ValueError, AttributeError):
            return False
        return parsed.version == 4 and str(parsed) == value

    user_id = analytics.get("analytics_user_id")
    if not valid_id(user_id):
        return {}
    context = {"opt_in": True, "user_id": user_id}
    session_id = analytics.get("analytics_session_id")
    if valid_id(session_id):
        context["session_id"] = session_id
    intent = analytics.get("analytics_intent")
    if intent in (
        "variant_evidence",
        "literature_review",
        "gene_disease_review",
        "infrastructure_support",
    ):
        context["intent"] = intent
    return {"io.helena/analytics": context}


async def run(request: str, *, analytics=None) -> str:
    async with MCPServerStreamableHttp(
        name="Folklore Clinical Variant Interpretation MCP",
        params={"url": ENDPOINT, "timeout": 30},
        tool_meta_resolver=lambda *_args, **_kwargs: journey_metadata(analytics),
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
    parser.add_argument("--analytics-opt-in", action="store_true")
    parser.add_argument("--analytics-user-id")
    parser.add_argument("--analytics-session-id")
    parser.add_argument(
        "--analytics-intent",
        choices=[
            "variant_evidence",
            "literature_review",
            "gene_disease_review",
            "infrastructure_support",
        ],
    )
    args = parser.parse_args()
    print(asyncio.run(run(args.request, analytics=vars(args))))


if __name__ == "__main__":
    main()
