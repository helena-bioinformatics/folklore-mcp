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
            initialized = client.initialize_result
            assert initialized is not None
            instructions = initialized.instructions or ""
            assert "Use public reference inputs only." in instructions
            assert (
                "Do not provide patient, phenotype, family, segregation or private case data."
                in instructions
            )
            assert "qualified professional review" in instructions
            assert (
                "not a diagnosis, treatment recommendation or standalone clinical report"
                in instructions
            )
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


def test_upstream_posts_share_burst_and_refill_without_changing_content() -> None:
    import httpx
    from folklore_biorouter.server import PublicPostBudget

    async def exercise() -> None:
        now = [0.0]
        sent = []

        async def sleep(seconds):
            now[0] += seconds

        async def respond(request):
            sent.append((now[0], request.content))
            return httpx.Response(200, json={"result": {"status": "ambiguous"}})

        budget = PublicPostBudget(clock=lambda: now[0], sleep=sleep)
        async with budget.http_client(transport=httpx.MockTransport(respond)) as client:
            for body in [b'{"method":"tools/list"}'] * 6 + [b'{"method":"tools/call"}']:
                response = await client.post("https://example.test/mcp", content=body)
                assert response.json()["result"]["status"] == "ambiguous"
        assert sent == [(0.0, b'{"method":"tools/list"}')] * 6 + [
            (10.1, b'{"method":"tools/call"}'),
        ]

    asyncio.run(exercise())


def test_upstream_429_stops_later_posts_without_retry() -> None:
    import httpx
    import pytest
    from folklore_biorouter.server import PublicPostBudget

    async def exercise() -> None:
        sent = []

        async def respond(request):
            sent.append(request)
            return httpx.Response(
                429, headers={"Retry-After": "10"}, json={"error": {"code": -32029}}
            )

        budget = PublicPostBudget()
        async with budget.http_client(transport=httpx.MockTransport(respond)) as client:
            response = await client.post(
                "https://example.test/mcp", json={"method": "tools/list"}
            )
            assert response.status_code == 429
            assert response.headers["Retry-After"] == "10"
            assert response.json()["error"]["code"] == -32029
            with pytest.raises(RuntimeError, match="rate limit"):
                await client.post(
                    "https://example.test/mcp", json={"method": "tools/call"}
                )
        assert len(sent) == 1

    asyncio.run(exercise())
