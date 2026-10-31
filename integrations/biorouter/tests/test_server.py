import asyncio

from fastmcp import Client, Context, FastMCP
from folklore_biorouter.server import SERVER_NAME, create_server


def test_proxy_preserves_tool_schema_and_structured_result() -> None:
    async def exercise() -> None:
        backend = FastMCP("Public contract fixture")

        @backend.tool
        def classify_germline_variant(query: str, assembly: str = "GRCh38") -> dict:
            """Return a deterministic public ambiguity fixture."""
            return {
                "query": query,
                "assembly": assembly,
                "result": {
                    "status": "ambiguous",
                    "candidates": ["candidate-1", "candidate-2"],
                },
                "contract_version": "2",
            }

        proxy = create_server(backend)
        assert proxy.name == SERVER_NAME

        async with Client(proxy, name="Biorouter bridge unit test") as client:
            tools = await client.list_tools()
            assert [tool.name for tool in tools] == ["classify_germline_variant"]
            schema = tools[0].inputSchema
            assert schema["required"] == ["query"]
            assert set(schema["properties"]) == {"assembly", "query"}

            result = await client.call_tool(
                "classify_germline_variant",
                {"assembly": "GRCh38", "query": "rs80357914"},
            )
            structured = result.structured_content
            assert structured is not None
            assert structured["result"]["status"] == "ambiguous"
            assert len(structured["result"]["candidates"]) == 2
            assert structured["contract_version"] == "2"

    asyncio.run(exercise())


def test_proxy_forwards_request_context_without_inventing_identity() -> None:
    async def exercise() -> None:
        backend = FastMCP("Journey fixture")
        received = []

        @backend.tool
        def classify_germline_variant(query: str, ctx: Context) -> dict:
            received.append(dict(ctx.request_context.meta or {}))
            return {"query": query, "status": "ambiguous"}

        proxy = create_server(backend)
        context = {
            "opt_in": True,
            "user_id": "77e8885e-02a4-43ca-a63a-20fcdcd65d94",
            "session_id": "7f78d2e5-12e1-4142-86b5-cf872731420e",
            "intent": "variant_evidence",
        }
        async with Client(proxy) as client:
            await client.call_tool(
                "classify_germline_variant",
                {"query": "rs80357914"},
                meta={"io.helena/analytics": context},
            )
            await client.call_tool("classify_germline_variant", {"query": "rs80357914"})
            await client.call_tool(
                "classify_germline_variant",
                {"query": "rs80357914"},
                meta={"io.helena/analytics": {"opt_in": False}},
            )
        assert received[0]["io.helena/analytics"] == context
        assert "io.helena/analytics" not in received[1]
        assert received[2]["io.helena/analytics"] == {"opt_in": False}

    asyncio.run(exercise())
