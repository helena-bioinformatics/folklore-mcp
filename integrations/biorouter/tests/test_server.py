import asyncio

from fastmcp import Client, FastMCP
from folklore_biorouter.server import SERVER_NAME, create_server


def test_proxy_preserves_tool_schema_and_structured_result() -> None:
    async def exercise() -> None:
        backend = FastMCP("Public contract fixture")

        @backend.tool
        def search_variant_evidence(query: str, assembly: str = "GRCh38") -> dict:
            """Return a deterministic public ambiguity fixture."""
            return {
                "query": query,
                "assembly": assembly,
                "result": {
                    "status": "ambiguous",
                    "candidates": ["candidate-1", "candidate-2"],
                },
                "usage_boundary": {
                    "patient_context_evaluated": False,
                    "review_required": True,
                },
            }

        proxy = create_server(backend)
        assert proxy.name == SERVER_NAME

        async with Client(proxy, name="Biorouter bridge unit test") as client:
            tools = await client.list_tools()
            assert [tool.name for tool in tools] == ["search_variant_evidence"]
            schema = tools[0].inputSchema
            assert schema["required"] == ["query"]
            assert set(schema["properties"]) == {"assembly", "query"}

            result = await client.call_tool(
                "search_variant_evidence",
                {"assembly": "GRCh38", "query": "rs80357914"},
            )
            structured = result.structured_content
            assert structured is not None
            assert structured["result"]["status"] == "ambiguous"
            assert len(structured["result"]["candidates"]) == 2
            assert structured["usage_boundary"] == {
                "patient_context_evaluated": False,
                "review_required": True,
            }

    asyncio.run(exercise())
