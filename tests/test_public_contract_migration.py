"""Public 1.7 source contracts, exercised offline through actual MCP dispatch."""

import json
import socket
from copy import deepcopy

import jsonschema
import pytest
from fastapi.testclient import TestClient
from test_app_and_mcp import META, FakeGateway, FakeLiteratureGateway, headers
from test_contracts import resolved_result
from test_gene_disease import FakeReference
from test_public_gene import GENE, SNAPSHOT, FakePublicGeneGateway

from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.contracts import tool_result, validate_upstream_result
from folklore_mcp_service.domain.literature_contracts import (
    PublicVariantLiteratureResponse,
)
from folklore_mcp_service.domain.public_projection import public_result
from folklore_mcp_service.main import create_app


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Contract tests must remain offline")

    for name in ("getaddrinfo", "create_connection"):
        monkeypatch.setattr(socket, name, blocked)
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, blocked)


class Literature(FakeLiteratureGateway):
    async def search(self, payload):
        return PublicVariantLiteratureResponse.model_validate(
            {
                "contract_version": "1.0",
                "status": "resolved",
                "variant_result": resolved_result(),
                "literature": None,
                "usage_boundary": {"review_required": True},
            }
        )


@pytest.fixture
def client():
    app = create_app(
        Settings(
            ENVIRONMENT="test",
            FOLKLORE_MCP_ENABLED=True,
            FOLKLORE_LITERATURE_ENABLED=True,
            FOLKLORE_GENE_DISEASE_ENABLED=True,
            FOLKLORE_PUBLIC_GENE_ENABLED=True,
        ),
        gateway=FakeGateway(resolved_result()),
        literature_gateway=Literature(),
        gene_disease_gateway=FakeReference(),
        public_gene_gateway=FakePublicGeneGateway(),
    )
    with TestClient(app) as value:
        yield value


def rpc(client, method, params=None):
    params = {**(params or {}), "_meta": META}
    response = client.post(
        "/folklore/v1/mcp",
        headers=headers(method, params.get("name")),
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )
    assert response.status_code == 200
    assert "error" not in response.json()
    return response.json()["result"]


CALLS = [
    ("classify_germline_variant", {"query": "chr17:43124028 CTC>C"}),
    ("search_variant_literature", {"query": "chr17:43124028 CTC>C"}),
    ("get_publication_details", {"pmid": "12345678"}),
    ("search_literature_corpus", {"query": "BRCA1"}),
    ("get_gene_disease_associations", {"gene": "BRCA1"}),
    ("search_disease_genes", {"disease": "Disease"}),
    ("resolve_gene", {"query": "BRCA1"}),
    ("get_gene_profile", {"gene_id": GENE, "snapshot_id": SNAPSHOT}),
    (
        "get_gene_section",
        {"gene_id": GENE, "snapshot_id": SNAPSHOT, "section": "overview"},
    ),
    ("search_gene_literature", {"gene_id": GENE, "snapshot_id": SNAPSHOT}),
]


@pytest.mark.parametrize("name,arguments", CALLS)
def test_all_scientific_routes_publish_current_shape_and_keep_source_fields(
    client, name, arguments
):
    catalog = {tool["name"]: tool for tool in rpc(client, "tools/list")["tools"]}
    result = rpc(client, "tools/call", {"name": name, "arguments": arguments})
    structured = result["structuredContent"]
    assert result["isError"] is False
    assert "usage_boundary" not in structured
    assert structured.get("contract_version", structured.get("contractVersion")) == "2"
    jsonschema.validate(structured, catalog[name]["outputSchema"])
    serialized = json.dumps(structured)
    for key in (
        "review_required",
        "patient_context_evaluated",
        "not_for",
        "diagnostic_use",
        "unavailable_context",
    ):
        assert key not in serialized
    if name == "classify_germline_variant":
        assert structured["result"]["identity"] == resolved_result()["identity"]
        assert (
            structured["result"]["interpretation"]["classification"]["automated_class"]
            == "LP"
        )
    if name in {"get_gene_disease_associations", "search_disease_genes"}:
        assert structured["source"]["snapshotSha256"] == "a" * 64
        assert structured["associations"][1]["classification"] == "Limited"


@pytest.mark.parametrize("name,_arguments", CALLS)
def test_all_invalid_arguments_keep_typed_errors_without_retired_boundary(
    client, name, _arguments
):
    result = rpc(
        client, "tools/call", {"name": name, "arguments": {"unexpected": True}}
    )
    assert result["isError"] is True
    structured = result["structuredContent"]
    assert structured["adapter_error"]["code"] == "invalid_arguments"
    assert "usage_boundary" not in structured
    assert "review_required" not in json.dumps(result)
    catalog = {tool["name"]: tool for tool in rpc(client, "tools/list")["tools"]}
    jsonschema.validate(structured, catalog[name]["outputSchema"])


def test_old_tool_and_prompt_names_are_not_aliases(client):
    names = {tool["name"] for tool in rpc(client, "tools/list")["tools"]}
    assert "classify_germline_variant" in names
    assert "search_variant_evidence" not in names
    rejected = rpc(
        client,
        "tools/call",
        {"name": "search_variant_evidence", "arguments": {"query": "rs429358"}},
    )
    assert rejected["isError"] is True
    assert rejected["structuredContent"]["adapter_error"]["code"] == "unknown_tool"
    prompt = rpc(
        client,
        "prompts/get",
        {"name": "classify_germline_variant", "arguments": {"variant": "rs429358"}},
    )
    assert "Call classify_germline_variant" in prompt["messages"][0]["content"]["text"]
    assert "assess_vus" in {p["name"] for p in rpc(client, "prompts/list")["prompts"]}


def test_actual_catalog_prompts_and_schemas_have_no_owned_disclaimer_copy(client):
    values = [
        rpc(client, "tools/list"),
        rpc(client, "prompts/list"),
        rpc(client, "resources/list"),
    ]
    for prompt in values[1]["prompts"]:
        values.append(
            rpc(
                client,
                "prompts/get",
                {"name": prompt["name"], "arguments": {"variant": "rs429358"}},
            )
        )
    serialized = json.dumps(values).lower()
    for phrase in (
        "usage_boundary",
        "review_required",
        "patient_context_evaluated",
        "not_for",
        "professional review",
        "patient diagnosis",
        "treatment recommendation",
        "no patient data",
        "no symptoms or patient narrative",
        "no patient or case narrative",
    ):
        assert phrase not in serialized


def test_projection_is_precise_nonmutating_and_keeps_scientific_source_text():
    original = resolved_result()
    original["interpretation"]["limitations"]["scope"] = (
        "GRCh38 nuclear SNVs and simple indels"
    )
    original["interpretation"]["source_note"] = (
        "This publication discusses diagnosis and treatment."
    )
    frozen = deepcopy(original)
    validate_upstream_result(original)
    result = tool_result(original)
    assert original == frozen
    assert (
        result["result"]["interpretation"]["source_note"]
        == original["interpretation"]["source_note"]
    )
    assert result["result"]["interpretation"]["limitations"] == {
        "scope": "GRCh38 nuclear SNVs and simple indels"
    }
    assert (
        public_result(
            {"publication": {"abstract": "Professional review of diagnosis."}}
        )["publication"]["abstract"]
        == "Professional review of diagnosis."
    )


def test_capture_request_is_single_send_and_reports_429_without_replay(monkeypatch):
    import importlib.util
    from email.message import Message
    from pathlib import Path
    from urllib.error import HTTPError

    path = (
        Path(__file__).resolve().parents[1]
        / "benchmarks/variant-interpretation/capture_folklore.py"
    )
    spec = importlib.util.spec_from_file_location("capture_current", path)
    capture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capture)
    calls = []
    response_headers = Message()
    response_headers["Retry-After"] = "10"

    class Sender:
        def open(self, request, timeout):
            calls.append((request, timeout))
            assert (
                json.loads(request.data)["params"]["name"]
                == "classify_germline_variant"
            )
            assert request.get_header("Mcp-name") == "classify_germline_variant"
            raise HTTPError(capture.ENDPOINT, 429, "limited", response_headers, None)

    monkeypatch.setattr(capture, "build_opener", lambda *args: Sender())
    result = capture._request("rs429358", "GRCh38", 1)
    assert len(calls) == 1
    assert result["error"]["http_status"] == 429
    assert result["error"]["retry_after"] == "10"


def test_projection_preserves_unavailable_and_ambiguous_domain_states():
    unavailable = resolved_result()
    unavailable["interpretation"] = {
        "contract_version": "1.0",
        "status": "unavailable",
        "identity": unavailable["identity"],
        "error": {
            "code": "reference_unavailable",
            "message": "Reference unavailable",
            "retryable": True,
        },
    }
    validated = validate_upstream_result(unavailable)
    assert (
        tool_result(validated)["result"]["interpretation"]
        == unavailable["interpretation"]
    )
    ambiguous = {
        "status": "ambiguous",
        "candidates": [
            {"identity": {"canonical_key": "one"}},
            {"identity": {"canonical_key": "two"}},
        ],
    }
    assert public_result(ambiguous) == ambiguous


@pytest.mark.parametrize(
    "value",
    [
        {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"structuredContent": {"result": {"status": "resolved"}}},
        },
        {"jsonrpc": "2.0", "id": True, "result": {}},
        {"id": 1, "result": {}},
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {},
            "error": {"code": -32603, "message": "failure"},
        },
        {"jsonrpc": "2.0", "id": 1, "result": []},
        [],
        None,
    ],
)
def test_capture_rejects_uncorrelated_or_invalid_rpc_and_retains_original(
    value, monkeypatch
):
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "benchmarks/variant-interpretation/capture_folklore.py"
    )
    spec = importlib.util.spec_from_file_location("capture_rpc", path)
    capture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capture)
    import io
    from email.message import Message

    class Response(io.BytesIO):
        headers = Message()
        headers["Content-Type"] = "application/json"

    class Sender:
        def open(self, request, timeout):
            return Response(json.dumps(value).encode())

    monkeypatch.setattr(capture, "build_opener", lambda *args: Sender())
    result = capture._request("rs429358", "GRCh38", 1)
    assert result["error"]["code"] == "invalid_rpc_response"
    assert result["unvalidated_response"] == value
    record = capture._record({"case_id": "one"}, result, 1)
    assert record["status"] is None
    assert record["automated_class"] is None
    assert record["raw_response"]["unvalidated_response"] == value
