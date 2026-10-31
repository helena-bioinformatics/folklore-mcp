"""Public gene transport, identity and MCP parity acceptance tests."""

import asyncio
import json
from copy import deepcopy

import httpx
import mcp.types as types
import pytest
from pydantic import ValidationError

from folklore_mcp_service.application.public_gene_gateway import (
    PublicGeneGateway,
    PublicGeneGatewayError,
)
from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.public_gene_contracts import (
    SECTION_NAMES,
    GetGeneProfileArguments,
    GetGeneSectionArguments,
    ResolveGeneArguments,
    SearchGeneLiteratureArguments,
)
from folklore_mcp_service.presentation.public_gene import (
    call_public_gene_tool,
    public_gene_tools,
)

SNAPSHOT = "a" * 64
GENE = "HGNC:1100"


def identity(gene=GENE, symbol="BRCA1"):
    return {
        "gene_id": gene,
        "symbol": symbol,
        "name": "BRCA1 DNA repair associated",
        "locus_type": "gene with protein product",
        "status": "Approved",
        "aliases": ["RNF53"],
        "previous_symbols": [],
        "ensembl_ids": ["ENSG00000012048"],
        "ncbi_gene_ids": ["672"],
        "source_id": "hgnc",
        "replacement_gene_ids": [],
    }


def source():
    return {
        "source_id": "hgnc",
        "provider": "HGNC",
        "dataset": "Approved genes",
        "release": "fixture",
        "raw_sha256": "b" * 64,
        "projection_sha256": "c" * 64,
        "source_url": "https://www.genenames.org/",
        "retrieved_at": "2026-10-06",
        "provider_updated_at": None,
        "accepted_at": "2026-10-08",
        "transform_version": "1",
        "rights_receipt_sha256": "d" * 64,
        "public_display": True,
        "attribution": "HGNC",
    }


def section(request, name="overview"):
    return {
        "gene_id": GENE,
        "request_id": request["request_id"],
        "snapshot_id": SNAPSHOT,
        "section": name,
        "status": "not_integrated",
        "coverage": "unknown",
        "coverage_scope": "Source-qualified public reference snapshot",
        "freshness": {"last_source_check": None, "stale": False, "stale_reason": None},
        "source_ids": [],
        "data": None,
        "limitations": ["Not integrated in this snapshot."],
        "pagination": None,
    }


def profile(request):
    return {
        "schema_version": "1.0",
        "gene_id": GENE,
        "request_id": request["request_id"],
        "snapshot_id": SNAPSHOT,
        "canonical_symbol": "BRCA1",
        "generated_at": "2026-10-30T10:00:00Z",
        "identity": identity(),
        "sources": {"hgnc": source()},
        "sections": {name: section(request, name) for name in SECTION_NAMES},
    }


def resolution(request, *, ambiguous=False):
    candidates = [
        {
            "identity": identity(),
            "match_types": ["approved_symbol"],
            "matched_terms": [request["query"]],
        }
    ]
    if ambiguous:
        candidates.append(
            {
                "identity": identity("HGNC:29", "ABCA1"),
                "match_types": ["alias"],
                "matched_terms": [request["query"]],
            }
        )
    return {
        "schema_version": "1.0",
        "request_id": request["request_id"],
        "identity_snapshot_id": SNAPSHOT,
        "status": "ambiguous" if ambiguous else "exact",
        "normalized_query": request["query"].upper(),
        "candidates": candidates,
        "candidate_total": len(candidates),
        "complete": True,
    }


def literature(request):
    return {
        "schema_version": "1.0",
        "gene_id": GENE,
        "canonical_symbol": "BRCA1",
        "request_id": request["request_id"],
        "snapshot_id": SNAPSHOT,
        "owner": "canonical_literature_mining",
        "query": "BRCA1",
        "captured_at": "2026-10-30T10:00:00Z",
        "capture_sha256": "e" * 64,
        "owner_contract_version": "1.0",
        "owner_returned_count": 1,
        "returned": 1,
        "filtered_unsafe_link_count": 0,
        "records": [
            {
                "work_id": "work-123",
                "pmid": "123",
                "title": "Public gene discovery",
                "journal": None,
                "publication_date": None,
                "doi": None,
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/123/",
                "match_types": ["gene"],
                "rank_score": 0.125,
                "relation": "discovery_result_not_curated_gene_association",
            }
        ],
        "has_more": True,
        "next_cursor": "next-literature-page",
        "semantic_index_used": False,
        "semantic_degraded_reason": "Not used",
        "graph_used": False,
        "graph_version": None,
        "graph_degraded_reason": None,
        "limits": ["Live discovery capture, not curated gene-disease evidence."],
    }


def settings():
    return Settings()


@pytest.mark.parametrize(
    "model,args",
    [
        (ResolveGeneArguments, {"query": "BRCA1", "patient": "private"}),
        (ResolveGeneArguments, {"query": "a\nb"}),
        (GetGeneProfileArguments, {"gene_id": GENE}),
        (GetGeneProfileArguments, {"gene_id": "BRCA1", "snapshot_id": SNAPSHOT}),
        (
            GetGeneSectionArguments,
            {
                "gene_id": GENE,
                "snapshot_id": SNAPSHOT,
                "section": "gwas",
                "limit": True,
            },
        ),
        (
            GetGeneSectionArguments,
            {"gene_id": GENE, "snapshot_id": SNAPSHOT, "section": "gwas", "limit": 51},
        ),
        (
            SearchGeneLiteratureArguments,
            {"gene_id": GENE, "snapshot_id": SNAPSHOT, "limit": 26},
        ),
    ],
)
def test_public_inputs_are_closed_and_snapshot_pinned(model, args):
    with pytest.raises(ValidationError):
        model.model_validate(args)


def test_discovery_has_four_closed_described_read_only_tools():
    tools = public_gene_tools(literature_enabled=True)
    assert [tool.name for tool in tools] == [
        "resolve_gene",
        "get_gene_profile",
        "get_gene_section",
        "search_gene_literature",
    ]
    assert [tool.name for tool in public_gene_tools(literature_enabled=False)] == [
        "resolve_gene",
        "get_gene_profile",
        "get_gene_section",
    ]
    for tool in tools:
        assert tool.input_schema["additionalProperties"] is False
        assert all(
            prop.get("description") for prop in tool.input_schema["properties"].values()
        )
        assert "request_id" not in tool.input_schema["properties"]
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.output_schema["additionalProperties"] is False


@pytest.mark.asyncio
async def test_all_four_http_operations_preserve_original_public_dtos_and_identity():
    seen = []
    returned = []

    def handler(request):
        payload = json.loads(request.content)
        seen.append((request.url.path, payload))
        assert "X-Folklore-MCP-Source-Key" not in request.headers
        operation = request.url.path.rsplit("/", 1)[-1]
        result = {
            "resolve": resolution,
            "profile": profile,
            "section": lambda p: section(p, p["section"]),
            "literature": literature,
        }[operation](payload)
        returned.append(result)
        return httpx.Response(200, json=result)

    async with httpx.AsyncClient(
        base_url="https://api.helena.bio", transport=httpx.MockTransport(handler)
    ) as client:
        gateway = PublicGeneGateway(settings(), client)
        for operation, args in [
            ("resolve", {"query": " BRCA1 "}),
            ("profile", {"gene_id": GENE, "snapshot_id": SNAPSHOT}),
            (
                "section",
                {
                    "gene_id": GENE,
                    "snapshot_id": SNAPSHOT,
                    "section": "gwas",
                    "cursor": "first-page",
                    "limit": 5,
                },
            ),
            (
                "literature",
                {
                    "gene_id": GENE,
                    "snapshot_id": SNAPSHOT,
                    "sort": "newest",
                    "cursor": "first-page",
                    "limit": 5,
                },
            ),
        ]:
            result = await gateway.request(operation, args)
            assert result == returned[-1]
        assert [path for path, _ in seen] == [
            f"/public/v1/genes/{name}"
            for name in ["resolve", "profile", "section", "literature"]
        ]
        assert len({p["request_id"] for _, p in seen}) == 4
        assert seen[0][1]["query"] == "BRCA1"
        assert seen[-1][1]["sort"] == "newest"
        assert seen[-1][1]["cursor"] == "first-page"
        assert "abstract" not in json.dumps(returned[-1])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("request_id", "wrong"),
        ("gene_id", "HGNC:29"),
        ("snapshot_id", "f" * 64),
        ("section", "expression"),
    ],
)
async def test_gateway_rejects_cross_request_gene_snapshot_or_section(field, value):
    def handler(request):
        result = section(json.loads(request.content), "gwas")
        result[field] = value
        return httpx.Response(200, json=result)

    async with httpx.AsyncClient(
        base_url="https://api.helena.bio", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(PublicGeneGatewayError) as error:
            await PublicGeneGateway(settings(), client).request(
                "section", {"gene_id": GENE, "snapshot_id": SNAPSHOT, "section": "gwas"}
            )
        assert error.value.code == "invalid_upstream_response"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body,media,status",
    [
        (b'{"request_id":"one","request_id":"two"}', "application/json", 200),
        (b"{}", "text/html", 200),
        (b"{}", "application/json", 302),
        (b"{}", "application/json", 200),
        (b"x" * 65537, "application/json", 200),
        (b'{"unexpected":NaN}', "application/json", 200),
    ],
)
async def test_gateway_rejects_transport_and_closed_contract_drift(body, media, status):
    async with httpx.AsyncClient(
        base_url="https://api.helena.bio",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                status, content=body, headers={"Content-Type": media}
            )
        ),
    ) as client:
        with pytest.raises(PublicGeneGatewayError) as error:
            await PublicGeneGateway(
                Settings(FOLKLORE_MCP_MAX_RESPONSE_BYTES=65536), client
            ).request("resolve", {"query": "BRCA1"})
        assert error.value.code == "invalid_upstream_response"


@pytest.mark.asyncio
async def test_snapshot_conflict_is_actionable_without_silent_restart():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            409,
            json={
                "detail": {
                    "code": "snapshot_unavailable",
                    "available_snapshot_id": "f" * 64,
                }
            },
        )

    async with httpx.AsyncClient(
        base_url="https://api.helena.bio", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(PublicGeneGatewayError) as error:
            await PublicGeneGateway(settings(), client).request(
                "profile", {"gene_id": GENE, "snapshot_id": SNAPSHOT}
            )
        assert error.value.code == "snapshot_unavailable"
        assert error.value.available_snapshot_id == "f" * 64
        assert error.value.retryable is False
        assert len(calls) == 1


@pytest.mark.asyncio
async def test_timeout_is_typed_and_retryable():
    def handler(request):
        raise httpx.ReadTimeout("private detail that must not escape")

    async with httpx.AsyncClient(
        base_url="https://api.helena.bio", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(PublicGeneGatewayError) as error:
            await PublicGeneGateway(settings(), client).request(
                "resolve", {"query": "BRCA1"}
            )
        assert error.value.code == "upstream_timeout" and error.value.retryable
        assert "private" not in str(error.value)


@pytest.mark.asyncio
async def test_ambiguous_and_empty_gene_outcomes_remain_results_and_text_is_full_json():
    class Gateway:
        async def request(self, operation, arguments):
            result = resolution(
                {**arguments, "request_id": "generated"}, ambiguous=True
            )
            return result

    result = await call_public_gene_tool(
        params=types.CallToolRequestParams(
            name="resolve_gene", arguments={"query": "ABC1"}
        ),
        gateway=Gateway(),
        settings=settings(),
        semaphore=asyncio.Semaphore(1),
    )
    assert result.is_error is False
    assert result.structured_content["result"]["status"] == "ambiguous"
    assert len(result.structured_content["result"]["candidates"]) == 2
    assert result.structured_content["record_url"] is None
    assert json.loads(result.content[0].text) == result.structured_content
    assert "usage_boundary" not in result.structured_content


@pytest.mark.asyncio
async def test_invalid_arguments_never_reach_authority():
    class Gateway:
        async def request(self, *_):
            raise AssertionError("invalid input reached the authority")

    result = await call_public_gene_tool(
        params=types.CallToolRequestParams(
            name="get_gene_profile", arguments={"gene_id": GENE}
        ),
        gateway=Gateway(),
        settings=settings(),
        semaphore=asyncio.Semaphore(1),
    )
    assert result.is_error is True
    assert result.structured_content["adapter_error"]["code"] == "invalid_arguments"
    assert json.loads(result.content[0].text) == result.structured_content


@pytest.mark.asyncio
async def test_literature_rejects_abstracts_unknown_fields_and_repeated_cursor():
    for mutation in ["abstract", "cursor"]:

        def handler(request, mutation=mutation):
            result = literature(json.loads(request.content))
            if mutation == "abstract":
                result["records"][0]["abstract"] = "unqualified abstract"
            else:
                result["next_cursor"] = "previous-page"
            return httpx.Response(200, json=result)

        async with httpx.AsyncClient(
            base_url="https://api.helena.bio", transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(PublicGeneGatewayError):
                await PublicGeneGateway(settings(), client).request(
                    "literature",
                    {
                        "gene_id": GENE,
                        "snapshot_id": SNAPSHOT,
                        "cursor": "previous-page",
                    },
                )


class FakePublicGeneGateway:
    def __init__(self):
        self.calls = []
        self.closed = False

    async def request(self, operation, arguments):
        self.calls.append((operation, arguments))
        request = {**arguments, "request_id": "internal-generated-request"}
        return {
            "resolve": resolution,
            "profile": profile,
            "section": lambda p: section(p, p["section"]),
            "literature": literature,
        }[operation](request)

    async def ready(self):
        self.ready_calls = getattr(self, "ready_calls", 0) + 1
        return True

    async def close(self):
        self.closed = True


@pytest.mark.parametrize(
    "enabled,literature_enabled,expected_new",
    [
        (False, False, []),
        (False, True, []),
        (True, False, ["resolve_gene", "get_gene_profile", "get_gene_section"]),
        (
            True,
            True,
            [
                "resolve_gene",
                "get_gene_profile",
                "get_gene_section",
                "search_gene_literature",
            ],
        ),
    ],
)
def test_real_dispatcher_gates_public_genes_and_preserves_original_tool_order(
    enabled, literature_enabled, expected_new
):
    from fastapi.testclient import TestClient
    from test_app_and_mcp import META, FakeGateway, FakeLiteratureGateway, headers
    from test_contracts import resolved_result
    from test_gene_disease import FakeReference

    from folklore_mcp_service.main import create_app

    genes = FakePublicGeneGateway()
    configuration = Settings(
        FOLKLORE_MCP_ENABLED=True,
        FOLKLORE_PUBLIC_GENE_ENABLED=enabled,
        FOLKLORE_GENE_DISEASE_ENABLED=True,
        FOLKLORE_LITERATURE_ENABLED=literature_enabled,
    )
    original = ["classify_germline_variant"]
    if literature_enabled:
        original += [
            "search_variant_literature",
            "get_publication_details",
            "search_literature_corpus",
        ]
    original += [
        "support_helena",
        "get_gene_disease_associations",
        "search_disease_genes",
    ]
    with TestClient(
        create_app(
            configuration,
            gateway=FakeGateway(resolved_result()),
            literature_gateway=FakeLiteratureGateway(),
            gene_disease_gateway=FakeReference(),
            public_gene_gateway=genes,
        )
    ) as client:
        response = client.post(
            "/folklore/v1/mcp",
            headers=headers("tools/list"),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {"_meta": META},
            },
        )
        assert response.status_code == 200
        assert [
            tool["name"] for tool in response.json()["result"]["tools"]
        ] == original + expected_new
        ready = client.get("/folklore/v1/ready")
        assert ready.status_code == 200
        assert getattr(genes, "ready_calls", 0) == (1 if enabled else 0)
        blocked_name = (
            "resolve_gene"
            if not enabled
            else "search_gene_literature"
            if not literature_enabled
            else None
        )
        if blocked_name:
            blocked = client.post(
                "/folklore/v1/mcp",
                headers=headers("tools/call", blocked_name),
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": blocked_name, "arguments": {}, "_meta": META},
                },
            )
            assert blocked.status_code == 200
            assert blocked.json()["result"]["isError"] is True
            assert genes.calls == []
    assert genes.closed is True


def test_real_dispatcher_routes_all_four_operations_with_full_structured_text_parity():
    from fastapi.testclient import TestClient
    from test_app_and_mcp import META, FakeGateway, FakeLiteratureGateway, headers
    from test_contracts import resolved_result

    from folklore_mcp_service.main import create_app

    genes = FakePublicGeneGateway()
    configuration = Settings(
        FOLKLORE_MCP_ENABLED=True,
        FOLKLORE_PUBLIC_GENE_ENABLED=True,
        FOLKLORE_LITERATURE_ENABLED=True,
    )
    variants = FakeGateway(resolved_result())
    cases = [
        ("resolve_gene", {"query": "BRCA1"}),
        ("get_gene_profile", {"gene_id": GENE, "snapshot_id": SNAPSHOT}),
        (
            "get_gene_section",
            {
                "gene_id": GENE,
                "snapshot_id": SNAPSHOT,
                "section": "structure",
                "cursor": "continuation",
                "limit": 5,
            },
        ),
        (
            "search_gene_literature",
            {"gene_id": GENE, "snapshot_id": SNAPSHOT, "sort": "newest", "limit": 5},
        ),
    ]
    with TestClient(
        create_app(
            configuration,
            gateway=variants,
            literature_gateway=FakeLiteratureGateway(),
            public_gene_gateway=genes,
        )
    ) as client:
        for index, (name, arguments) in enumerate(cases):
            response = client.post(
                "/folklore/v1/mcp",
                headers=headers("tools/call", name),
                json={
                    "jsonrpc": "2.0",
                    "id": index,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments, "_meta": META},
                },
            )
            assert response.status_code == 200
            result = response.json()["result"]
            assert result["isError"] is False
            assert (
                json.loads(result["content"][0]["text"]) == result["structuredContent"]
            )
            assert "usage_boundary" not in result["structuredContent"]
        assert [operation for operation, _ in genes.calls] == [
            "resolve",
            "profile",
            "section",
            "literature",
        ]
        assert genes.calls[2][1]["cursor"] == "continuation"
        assert variants.calls == 0


@pytest.mark.asyncio
async def test_dense_section_page_preserves_partial_coverage_counts_and_nullable_evidence():
    def handler(request):
        result = section(json.loads(request.content), "disease_validity")
        result.update(
            status="available",
            coverage="partial",
            source_ids=["clingen"],
            limitations=["Subset only."],
        )
        result["data"] = {
            "kind": "disease_validity",
            "count_unit": "source_assertion",
            "records": [
                {
                    "assertion_id": "assertion-1",
                    "source_id": "clingen",
                    "disease_id": "MONDO:0000001",
                    "disease_name": "Source disease label",
                    "inheritance": None,
                    "classification": "Limited",
                    "curation_date": None,
                    "panel": None,
                    "criteria_version": None,
                    "report_url": "https://search.clinicalgenome.org/",
                }
            ],
        }
        result["pagination"] = {
            "observed_total": 23,
            "total": None,
            "returned": 1,
            "count_unit": "source_assertion",
            "next_cursor": "next-section-page",
        }
        return httpx.Response(200, json=result)

    async with httpx.AsyncClient(
        base_url="https://api.helena.bio", transport=httpx.MockTransport(handler)
    ) as client:
        result = await PublicGeneGateway(settings(), client).request(
            "section",
            {
                "gene_id": GENE,
                "snapshot_id": SNAPSHOT,
                "section": "disease_validity",
                "limit": 1,
            },
        )
        assert result["pagination"] == {
            "observed_total": 23,
            "total": None,
            "returned": 1,
            "count_unit": "source_assertion",
            "next_cursor": "next-section-page",
        }
        assert result["data"]["records"][0]["inheritance"] is None
        assert result["data"]["records"][0]["classification"] == "Limited"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", ["exact", "alias", "ambiguous", "not_found", "withdrawn"]
)
async def test_all_resolver_domain_outcomes_are_preserved_without_candidate_selection(
    status,
):
    def handler(request):
        args = json.loads(request.content)
        result = resolution(args, ambiguous=status == "ambiguous")
        result["status"] = status
        if status == "not_found":
            result["candidates"] = []
            result["candidate_total"] = 0
        elif status == "withdrawn":
            result["candidates"][0]["identity"]["status"] = "Entry Withdrawn"
            result["candidates"][0]["identity"]["replacement_gene_ids"] = ["HGNC:29"]
            result["candidates"][0]["match_types"] = ["withdrawn_symbol"]
        elif status == "alias":
            result["candidates"][0]["match_types"] = ["alias"]
        return httpx.Response(200, json=result)

    async with httpx.AsyncClient(
        base_url="https://api.helena.bio", transport=httpx.MockTransport(handler)
    ) as client:
        gateway = PublicGeneGateway(settings(), client)
        result = await call_public_gene_tool(
            params=types.CallToolRequestParams(
                name="resolve_gene", arguments={"query": "BRCA1"}
            ),
            gateway=gateway,
            settings=settings(),
            semaphore=asyncio.Semaphore(1),
        )
        assert result.is_error is False
        assert result.structured_content["result"]["status"] == status
        assert json.loads(result.content[0].text) == result.structured_content
        if status in {"ambiguous", "not_found", "withdrawn"}:
            assert result.structured_content["record_url"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["gene", "snapshot", "source", "unknown", "query"])
async def test_profile_rejects_mixed_gene_snapshot_or_source_and_resolver_query_drift(
    mutation,
):
    def handler(request):
        args = json.loads(request.content)
        result = profile(args)
        if mutation == "gene":
            result["sections"]["overview"]["gene_id"] = "HGNC:29"
        elif mutation == "snapshot":
            result["sections"]["overview"]["snapshot_id"] = "f" * 64
        elif mutation == "source":
            result["identity"]["source_id"] = "unknown-source"
        elif mutation == "unknown":
            result["private_debug"] = "not public"
        else:
            result = resolution(args)
            result["normalized_query"] = "OTHER_GENE"
        return httpx.Response(200, json=result)

    async with httpx.AsyncClient(
        base_url="https://api.helena.bio", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(PublicGeneGatewayError) as error:
            if mutation == "query":
                await PublicGeneGateway(settings(), client).request(
                    "resolve", {"query": "BRCA1"}
                )
            else:
                await PublicGeneGateway(settings(), client).request(
                    "profile", {"gene_id": GENE, "snapshot_id": SNAPSHOT}
                )
        assert error.value.code == "invalid_upstream_response"


def expression_page(request):
    result = section(request, "expression")
    result.update(
        status="available", coverage="complete", source_ids=["gtex"], limitations=[]
    )
    result["data"] = {
        "kind": "expression",
        "count_unit": "provider_expression_category",
        "records": [
            {
                "source_id": "gtex",
                "ensembl_gene_id": "ENSG00000012048",
                "tissue_id": "provider-1",
                "tissue_label": "Provider tissue label",
                "median_tpm": 0.000001,
                "unit": "TPM",
                "statistic": "median",
                "sample_count": None,
                "category_type": "provider_expression_category",
            }
        ],
    }
    result["pagination"] = {
        "observed_total": 68,
        "total": 68,
        "returned": 1,
        "count_unit": "provider_expression_category",
        "next_cursor": "next-section-page",
    }
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation", ["returned", "observed", "total", "unit", "cursor", "limit", "partial"]
)
async def test_dense_section_page_fails_closed_for_count_unit_limit_and_cursor_drift(
    mutation,
):
    def handler(request):
        result = expression_page(json.loads(request.content))
        if mutation == "returned":
            result["pagination"]["returned"] = 2
        elif mutation == "observed":
            result["pagination"]["observed_total"] = 0
        elif mutation == "total":
            result["pagination"]["total"] = 69
        elif mutation == "unit":
            result["pagination"]["count_unit"] = "different_unit"
        elif mutation == "cursor":
            result["pagination"]["next_cursor"] = "previous-page"
        elif mutation == "partial":
            result["coverage"] = "partial"
        else:
            another = deepcopy(result["data"]["records"][0])
            another["tissue_id"] = "provider-2"
            result["data"]["records"].append(another)
            result["pagination"]["returned"] = 2
        return httpx.Response(200, json=result)

    async with httpx.AsyncClient(
        base_url="https://api.helena.bio", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(PublicGeneGatewayError) as error:
            await PublicGeneGateway(settings(), client).request(
                "section",
                {
                    "gene_id": GENE,
                    "snapshot_id": SNAPSHOT,
                    "section": "expression",
                    "limit": 1,
                    "cursor": "previous-page",
                },
            )
        assert error.value.code == "invalid_upstream_response"


@pytest.mark.asyncio
async def test_successful_dense_continuation_keeps_tiny_positive_source_values():
    seen = []

    def handler(request):
        args = json.loads(request.content)
        seen.append(args)
        return httpx.Response(200, json=expression_page(args))

    async with httpx.AsyncClient(
        base_url="https://api.helena.bio", transport=httpx.MockTransport(handler)
    ) as client:
        result = await PublicGeneGateway(settings(), client).request(
            "section",
            {
                "gene_id": GENE,
                "snapshot_id": SNAPSHOT,
                "section": "expression",
                "limit": 1,
                "cursor": "previous-page",
            },
        )
        assert result["data"]["records"][0]["median_tpm"] == 0.000001
        assert result["data"]["records"][0]["sample_count"] is None
        assert result["pagination"]["observed_total"] == 68
        assert seen[0]["cursor"] == "previous-page"


@pytest.mark.asyncio
@pytest.mark.parametrize("available", [True, False])
async def test_ready_requires_valid_public_snapshot_response(available):
    def handler(request):
        if available:
            result = resolution(json.loads(request.content))
            result.update(status="not_found", candidates=[], candidate_total=0)
            return httpx.Response(200, json=result)
        return httpx.Response(
            503, json={"detail": {"code": "gene_snapshot_unavailable"}}
        )

    async with httpx.AsyncClient(
        base_url="https://api.helena.bio", transport=httpx.MockTransport(handler)
    ) as client:
        assert await PublicGeneGateway(settings(), client).ready() is available


@pytest.mark.asyncio
async def test_output_schema_accepts_full_results_and_typed_errors():
    import jsonschema

    from folklore_mcp_service.presentation.public_gene import public_gene_output_schema

    class Gateway:
        def __init__(self, failure):
            self.failure = failure

        async def request(self, operation, arguments):
            if self.failure:
                raise PublicGeneGatewayError(
                    "snapshot_unavailable",
                    "Restart resolution.",
                    retryable=False,
                    available_snapshot_id="f" * 64,
                )
            request = {**arguments, "request_id": "internal-generated-request"}
            return {
                "resolve": resolution,
                "profile": profile,
                "section": lambda p: section(p, p["section"]),
                "literature": literature,
            }[operation](request)

    for failure in [False, True]:
        for name, operation, arguments in [
            ("resolve_gene", "resolve", {"query": "BRCA1"}),
            ("get_gene_profile", "profile", {"gene_id": GENE, "snapshot_id": SNAPSHOT}),
            (
                "get_gene_section",
                "section",
                {"gene_id": GENE, "snapshot_id": SNAPSHOT, "section": "structure"},
            ),
            (
                "search_gene_literature",
                "literature",
                {"gene_id": GENE, "snapshot_id": SNAPSHOT},
            ),
        ]:
            result = await call_public_gene_tool(
                params=types.CallToolRequestParams(name=name, arguments=arguments),
                gateway=Gateway(failure),
                settings=settings(),
                semaphore=asyncio.Semaphore(1),
            )
            schema = public_gene_output_schema(operation)
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.validate(result.structured_content, schema)
            assert result.is_error is failure


@pytest.mark.parametrize(
    "outcome,metric",
    [
        ("withdrawn", "withdrawn"),
        ("snapshot_unavailable", "snapshot_unavailable"),
        ("gene_not_found", "not_found"),
        ("invalid_gene_cursor", "invalid_request"),
        ("gene_capacity_unavailable", "upstream_unavailable"),
        ("gene_read_timeout", "upstream_timeout"),
        ("gene_literature_unavailable", "upstream_unavailable"),
    ],
)
def test_real_dispatcher_preserves_gene_outcomes_without_false_internal_failure(
    outcome, metric
):
    from fastapi.testclient import TestClient
    from test_app_and_mcp import META, FakeGateway, FakeLiteratureGateway, headers
    from test_contracts import resolved_result

    from folklore_mcp_service.main import create_app

    class OutcomeGateway(FakePublicGeneGateway):
        async def request(self, operation, arguments):
            self.calls.append((operation, arguments))
            if outcome == "withdrawn":
                result = resolution({**arguments, "request_id": "generated-read"})
                result["status"] = "withdrawn"
                result["candidates"][0]["identity"]["status"] = "Entry Withdrawn"
                result["candidates"][0]["identity"]["replacement_gene_ids"] = [
                    "HGNC:29"
                ]
                return result
            raise PublicGeneGatewayError(
                outcome,
                "Bounded public gene failure.",
                retryable=outcome
                in {
                    "gene_capacity_unavailable",
                    "gene_read_timeout",
                    "gene_literature_unavailable",
                },
                available_snapshot_id="f" * 64
                if outcome == "snapshot_unavailable"
                else None,
            )

    genes = OutcomeGateway()
    variants = FakeGateway(resolved_result())
    configuration = Settings(
        FOLKLORE_MCP_ENABLED=True,
        FOLKLORE_PUBLIC_GENE_ENABLED=True,
        FOLKLORE_LITERATURE_ENABLED=True,
    )
    name, arguments = "get_gene_profile", {"gene_id": GENE, "snapshot_id": SNAPSHOT}
    if outcome == "withdrawn":
        name, arguments = "resolve_gene", {"query": "OLD_GENE_SYMBOL"}
    elif outcome == "invalid_gene_cursor":
        name, arguments = (
            "get_gene_section",
            {**arguments, "section": "structure", "cursor": "opaque-stale-cursor"},
        )
    elif outcome == "gene_literature_unavailable":
        name = "search_gene_literature"
    app = create_app(
        configuration,
        gateway=variants,
        literature_gateway=FakeLiteratureGateway(),
        public_gene_gateway=genes,
    )
    with TestClient(app) as client:
        response = client.post(
            "/folklore/v1/mcp",
            headers=headers("tools/call", name),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments, "_meta": META},
            },
        )
        assert response.status_code == 200
        result = response.json()["result"]
        structured = result["structuredContent"]
        assert json.loads(result["content"][0]["text"]) == structured
        assert "usage_boundary" not in structured
        if outcome == "withdrawn":
            assert result["isError"] is False
            assert structured["result"]["status"] == "withdrawn"
            assert structured["result"]["candidates"][0]["identity"][
                "replacement_gene_ids"
            ] == ["HGNC:29"]
            assert structured["record_url"] is None
        else:
            assert result["isError"] is True
            assert structured["adapter_error"]["code"] == outcome
            assert structured["result"] is None
        assert (
            app.state.metrics_registry.get_sample_value(
                "folklore_mcp_tool_calls_total", {"outcome": metric}
            )
            == 1
        )
        assert (
            app.state.metrics_registry.get_sample_value(
                "folklore_mcp_tool_calls_total", {"outcome": "internal_failure"}
            )
            is None
        )
        assert len(genes.calls) == 1
        assert variants.calls == 0
    assert genes.closed is True


@pytest.mark.parametrize(
    "enabled,expected_status,expected_calls", [(True, 503, 1), (False, 200, 0)]
)
def test_public_gene_readiness_failure_is_independent_and_default_off(
    enabled, expected_status, expected_calls
):
    from fastapi.testclient import TestClient
    from test_app_and_mcp import FakeGateway
    from test_contracts import resolved_result

    from folklore_mcp_service.main import create_app

    class UnavailableGeneGateway(FakePublicGeneGateway):
        def __init__(self):
            super().__init__()
            self.ready_calls = 0

        async def ready(self):
            self.ready_calls += 1
            assert enabled, (
                "Disabled public gene capability performed an authority probe"
            )
            return False

    genes = UnavailableGeneGateway()
    configuration = Settings(
        FOLKLORE_MCP_ENABLED=True, FOLKLORE_PUBLIC_GENE_ENABLED=enabled
    )
    with TestClient(
        create_app(
            configuration,
            gateway=FakeGateway(resolved_result()),
            public_gene_gateway=genes,
        )
    ) as client:
        response = client.get("/folklore/v1/ready")
        assert response.status_code == expected_status
        assert response.json()["dependencies"]["public_gene_profiles"] is (
            False if enabled else None
        )
        assert genes.ready_calls == expected_calls
        assert genes.calls == []
