import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_app_and_mcp import META, FakeGateway, FakeLiteratureGateway
from test_contracts import resolved_result

from folklore_mcp_service.application.gene_disease_gateway import (
    GeneDiseaseGateway,
    GeneDiseaseGatewayError,
)
from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.gene_disease_contracts import (
    GeneDiseaseResponse,
    GetGeneDiseaseArguments,
    SearchDiseaseGenesArguments,
    gene_disease_boundary,
)
from folklore_mcp_service.main import create_app


def payload():
    return {
        "contractVersion": "1.0",
        "status": "ok",
        "query": {"kind": "gene", "value": "BRCA1", "match": "exact"},
        "associations": [
            {
                "geneSymbol": "BRCA1",
                "hgncId": "HGNC:1100",
                "diseaseName": name,
                "diseaseId": disease,
                "modeOfInheritance": moi,
                "modeOfInheritanceId": None,
                "classification": validity,
                "expertPanel": "test panel",
                "reportUrl": "https://search.clinicalgenome.org/",
                "classificationDate": "2026-01-01",
                "sopVersion": "test",
            }
            for name, disease, moi, validity in [
                ("Disease A", "MONDO:0000001", "AD", "Definitive"),
                ("Disease B", "MONDO:0000002", "AR", "Limited"),
            ]
        ],
        "pagination": {"limit": 20, "offset": 0, "total": 2, "nextOffset": None},
        "source": {
            "name": "ClinGen Gene-Disease Validity",
            "version": "fixture",
            "snapshotSha256": "a" * 64,
            "downloadUrl": "https://search.clinicalgenome.org/",
            "license": "CC0-1.0",
            "attribution": "ClinGen",
        },
        "warnings": ["Local reference snapshot; not a patient diagnosis."],
        "usage_boundary": gene_disease_boundary(),
    }


class FakeReference:
    def __init__(self, ready=True):
        self.calls = []
        self.is_ready = ready

    async def search(self, kind, arguments):
        self.calls.append((kind, arguments))
        response = payload()
        if kind == "diseases":
            response["query"] = {
                "kind": "disease",
                "value": arguments["disease"],
                "match": "name_contains",
            }
        return GeneDiseaseResponse.model_validate(response)

    async def ready(self):
        return self.is_ready

    async def close(self):
        pass


@pytest.mark.parametrize(
    "model,args",
    [
        (GetGeneDiseaseArguments, {"gene": "BRCA1", "patient": "private"}),
        (GetGeneDiseaseArguments, {"gene": "BRCA1", "limit": True}),
        (GetGeneDiseaseArguments, {"gene": "BRCA1", "offset": 1001}),
        (GetGeneDiseaseArguments, {"gene": "BRCA1; DROP TABLE"}),
        (SearchDiseaseGenesArguments, {"disease": "MONDO:123"}),
        (SearchDiseaseGenesArguments, {"disease": "a\nb"}),
        (SearchDiseaseGenesArguments, {"disease": "abc", "symptoms": []}),
        (SearchDiseaseGenesArguments, {"disease": "abc", "limit": 51}),
    ],
)
def test_closed_inputs(model, args):
    with pytest.raises(ValidationError):
        model.model_validate(args)


def test_input_normalization():
    assert GetGeneDiseaseArguments(gene=" brca1 ").gene == "BRCA1"
    assert GetGeneDiseaseArguments(gene="hgnc:1100").gene == "HGNC:1100"


@pytest.mark.asyncio
async def test_gateway_forwards_closed_contract_and_preserves_assertions():
    def handler(request):
        assert request.url.path == "/folklore/v1/gene-disease/genes/search"
        assert "authorization" not in request.headers
        assert not any(name.lower().startswith("x-") for name in request.headers)
        assert json.loads(request.content) == {
            "gene": "BRCA1",
            "limit": 20,
            "offset": 0,
        }
        return httpx.Response(200, json=payload())

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://authority"
    ) as client:
        gateway = GeneDiseaseGateway(Settings(), client)
        result = await gateway.search(
            "genes", GetGeneDiseaseArguments(gene="BRCA1").model_dump()
        )
        assert result.model_dump() == payload()


@pytest.mark.parametrize(
    "status,body,media,retryable",
    [
        (503, b"{}", "application/json", True),
        (200, b'{"status":"ok","status":"not_found"}', "application/json", False),
        (200, b"{}", "application/json", False),
        (200, b"{}", "text/html", False),
        (302, b"{}", "application/json", False),
        (200, b"x" * 65537, "application/json", False),
    ],
)
@pytest.mark.asyncio
async def test_gateway_rejects_invalid_or_unavailable_not_empty_results(
    status, body, media, retryable
):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                status, content=body, headers={"content-type": media}
            )
        ),
        base_url="http://authority",
    ) as client:
        gateway = GeneDiseaseGateway(
            Settings(FOLKLORE_MCP_MAX_RESPONSE_BYTES=65536), client
        )
        with pytest.raises(GeneDiseaseGatewayError) as caught:
            await gateway.search("genes", {"gene": "BRCA1"})
        assert caught.value.retryable is retryable


@pytest.mark.asyncio
async def test_gateway_timeout_is_retryable():
    def handler(request):
        raise httpx.ReadTimeout("timeout")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://authority"
    ) as client:
        with pytest.raises(GeneDiseaseGatewayError, match="timed out"):
            await GeneDiseaseGateway(Settings(), client).search(
                "genes", {"gene": "BRCA1"}
            )


def rpc(client, method, params=None):
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {"_meta": META, **(params or {})},
    }
    return client.post("/folklore/v1/mcp", json=data).json()["result"]


def test_seven_tools_and_mcp_text_parity_and_no_variant_calls():
    reference = FakeReference()
    variant = FakeGateway(resolved_result())
    settings = Settings(
        FOLKLORE_MCP_ENABLED=True,
        FOLKLORE_LITERATURE_ENABLED=True,
        FOLKLORE_GENE_DISEASE_ENABLED=True,
    )
    with TestClient(
        create_app(
            settings,
            gateway=variant,
            literature_gateway=FakeLiteratureGateway(),
            gene_disease_gateway=reference,
        )
    ) as client:
        tools = rpc(client, "tools/list")["tools"]
        assert [tool["name"] for tool in tools] == [
            "search_variant_evidence",
            "search_variant_literature",
            "get_publication_details",
            "search_literature_corpus",
            "support_helena",
            "get_gene_disease_associations",
            "search_disease_genes",
        ]
        for tool in tools[-2:]:
            assert tool["annotations"]["readOnlyHint"] is True
            assert tool["inputSchema"]["additionalProperties"] is False
            assert all(
                p.get("description") for p in tool["inputSchema"]["properties"].values()
            )
        for name, _path, args in [
            ("get_gene_disease_associations", "genes", {"gene": "BRCA1"}),
            ("search_disease_genes", "diseases", {"disease": "Disease"}),
        ]:
            mcp = rpc(client, "tools/call", {"name": name, "arguments": args})
            expected = payload()
            if name == "search_disease_genes":
                expected["query"] = {
                    "kind": "disease",
                    "value": "Disease",
                    "match": "name_contains",
                }
            assert (
                expected
                == mcp["structuredContent"]
                == json.loads(mcp["content"][0]["text"])
            )
            assert mcp["isError"] is False
        assert variant.calls == 0
        bad = rpc(
            client,
            "tools/call",
            {
                "name": "search_disease_genes",
                "arguments": {"disease": "Disease", "patient": "private"},
            },
        )
        assert bad["isError"] is True
        assert bad["structuredContent"]["usage_boundary"] == gene_disease_boundary()


def test_disabled_capability_and_readiness_failure():
    for enabled in [False, True]:
        with TestClient(
            create_app(
                Settings(
                    FOLKLORE_MCP_ENABLED=True, FOLKLORE_GENE_DISEASE_ENABLED=enabled
                ),
                gateway=FakeGateway(resolved_result()),
                gene_disease_gateway=FakeReference(False),
            )
        ) as client:
            assert client.get("/folklore/v1/ready").status_code == (
                503 if enabled else 200
            )
            if not enabled:
                rejected = rpc(
                    client,
                    "tools/call",
                    {
                        "name": "search_disease_genes",
                        "arguments": {"disease": "Disease"},
                    },
                )
                assert rejected["isError"] is True
                assert "search_disease_genes" not in [
                    t["name"] for t in rpc(client, "tools/list")["tools"]
                ]
                assert (
                    client.post(
                        "/folklore/v1/gene-disease/genes/search", json={"gene": "BRCA1"}
                    ).status_code
                    == 404
                )


@pytest.mark.parametrize(
    "field,value", [("value", "BRCA2"), ("kind", "disease"), ("match", "name_contains")]
)
@pytest.mark.asyncio
async def test_gateway_rejects_response_for_other_query(field, value):
    result = payload()
    result["query"][field] = value
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=result)),
        base_url="http://authority",
    ) as client:
        with pytest.raises(GeneDiseaseGatewayError):
            await GeneDiseaseGateway(Settings(), client).search(
                "genes", {"gene": "BRCA1", "limit": 20, "offset": 0}
            )


@pytest.mark.asyncio
async def test_gateway_rejects_response_for_other_page():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload())),
        base_url="http://authority",
    ) as client:
        with pytest.raises(GeneDiseaseGatewayError):
            await GeneDiseaseGateway(Settings(), client).search(
                "genes", {"gene": "BRCA1", "limit": 10, "offset": 0}
            )


@pytest.mark.asyncio
async def test_ready_requires_enabled_ready_public_dependency():
    for result, expected in [
        ({"status": "ready"}, False),
        ({"status": "ready", "dependencies": {"public_gene_disease": True}}, True),
        ({"status": "ready", "dependencies": {"public_gene_disease": False}}, False),
        ({"status": "ready", "dependencies": {"public_gene_disease": "true"}}, False),
        ({"status": "not_ready", "dependencies": {"public_gene_disease": True}}, False),
    ]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _, response_payload=result: httpx.Response(
                    200, json=response_payload
                )
            ),
            base_url="http://authority",
        ) as client:
            assert await GeneDiseaseGateway(Settings(), client).ready() is expected
