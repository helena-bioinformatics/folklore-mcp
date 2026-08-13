import json

import httpx
import pytest
from test_contracts import resolved_result

from folklore_mcp_service.application.gateway import VariantGateway, VariantGatewayError
from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.contracts import SearchVariantArguments


def settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        FOLKLORE_MCP_ENABLED=True,
        FOLKLORE_API_BASE_URL="http://127.0.0.1:9001",
        FOLKLORE_MCP_DEADLINE_SECONDS=5.0,
    )


@pytest.mark.asyncio
async def test_gateway_posts_exact_closed_request_and_validates_result() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/public/v1/variants/search"
        assert json.loads(request.content) == {
            "assembly": "GRCh38",
            "query": "rs80357914",
        }
        return httpx.Response(
            200,
            json=resolved_result(),
            headers={"Content-Type": "application/json"},
        )

    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:9001",
        transport=httpx.MockTransport(handler),
    )
    gateway = VariantGateway(settings(), client)
    result = await gateway.search(SearchVariantArguments(query="rs80357914"))
    assert result["status"] == "resolved"
    await client.aclose()


@pytest.mark.asyncio
async def test_gateway_rejects_duplicate_json_and_wrong_media_type() -> None:
    responses = iter(
        [
            httpx.Response(
                200,
                content=b'{"search_contract_version":"1.0","status":"resolved","status":"resolved"}',
                headers={"Content-Type": "application/json"},
            ),
            httpx.Response(
                200, text="not json", headers={"Content-Type": "text/plain"}
            ),
        ]
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        return next(responses)

    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:9001",
        transport=httpx.MockTransport(handler),
    )
    gateway = VariantGateway(settings(), client)
    for _ in range(2):
        with pytest.raises(VariantGatewayError) as error:
            await gateway.search(SearchVariantArguments(query="rs1"))
        assert error.value.code == "invalid_upstream_response"
    await client.aclose()


@pytest.mark.asyncio
async def test_readiness_requires_healthy_public_resolver() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "ready",
                "dependencies": {"public_variant_search": True},
            },
        )

    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:9001",
        transport=httpx.MockTransport(handler),
    )
    assert await VariantGateway(settings(), client).ready() is True
    await client.aclose()
