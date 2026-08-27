from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from test_contracts import resolved_result
from test_variant_literature import corpus_search_payload, publication_details_payload

from folklore_mcp_service.application.literature_gateway import LiteratureGatewayError
from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.literature_contracts import (
    PublicationDetailsResponse,
    PublicCorpusSearchResponse,
)
from folklore_mcp_service.main import create_app

META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
}


class FakeGateway:
    def __init__(self, result: dict, *, ready: bool = True) -> None:
        self.result = result
        self.is_ready = ready
        self.calls = 0
        self.closed = False

    async def search(self, arguments):
        self.calls += 1
        assert arguments.query == "chr17:43124028 CTC>C"
        return self.result

    async def ready(self) -> bool:
        return self.is_ready

    async def close(self) -> None:
        self.closed = True


class FakeLiteratureGateway:
    def __init__(self) -> None:
        self.closed = False
        self.corpus_payloads = []

    async def ready(self) -> bool:
        return True

    async def search(self, payload):
        raise AssertionError("Search should not be called by publication details")

    async def get_publication(self, pmid: str) -> PublicationDetailsResponse:
        assert pmid == "12345678"
        return PublicationDetailsResponse.model_validate(publication_details_payload())

    async def search_corpus(self, payload) -> PublicCorpusSearchResponse:
        self.corpus_payloads.append(payload)
        return PublicCorpusSearchResponse.model_validate(corpus_search_payload())

    async def close(self) -> None:
        self.closed = True


class MarkerPublicationLiteratureGateway(FakeLiteratureGateway):
    async def get_publication(self, pmid: str) -> PublicationDetailsResponse:
        assert pmid == "12345678"
        return PublicationDetailsResponse.model_validate(
            publication_details_payload(abstract="[Tool result trimmed for length]")
        )


class MissingPublicationLiteratureGateway(FakeLiteratureGateway):
    async def get_publication(self, pmid: str) -> PublicationDetailsResponse:
        assert pmid == "12345678"
        raise LiteratureGatewayError(
            "publication_not_found",
            (
                "No record for this PMID exists in Folklore's current "
                "PubMed-derived genetics corpus."
            ),
            retryable=False,
        )


def enabled_settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        FOLKLORE_MCP_ENABLED=True,
        FOLKLORE_API_BASE_URL="http://127.0.0.1:9001",
        FOLKLORE_MCP_DEADLINE_SECONDS=5.0,
    )


def literature_enabled_settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        FOLKLORE_MCP_ENABLED=True,
        FOLKLORE_LITERATURE_ENABLED=True,
        FOLKLORE_API_BASE_URL="http://127.0.0.1:9001",
        FOLKLORE_MCP_DEADLINE_SECONDS=5.0,
    )


def headers(method: str, name: str | None = None) -> dict[str, str]:
    result = {
        "accept": "application/json",
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": method,
    }
    if name:
        result["Mcp-Name"] = name
    return result


def test_default_off_has_no_mcp_route_and_is_not_ready() -> None:
    gateway = FakeGateway(resolved_result())
    app = create_app(Settings(ENVIRONMENT="test"), gateway=gateway)
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/folklore/v1/mcp" not in paths
    with TestClient(app) as client:
        assert client.get("/folklore/v1/health").status_code == 200
        assert client.get("/folklore/v1/ready").status_code == 503


def test_mcp_2026_discovery_is_stateless_and_initialize_is_retired() -> None:
    app = create_app(enabled_settings(), gateway=FakeGateway(resolved_result()))
    with TestClient(app) as client:
        discovered = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "server/discover",
                "params": {"_meta": META},
            },
            headers=headers("server/discover"),
        )
        initialized = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2026-07-28",
                    "capabilities": {},
                    "clientInfo": {"name": "legacy-test", "version": "1.0"},
                    "_meta": META,
                },
            },
            headers=headers("initialize"),
        )

    assert discovered.status_code == 200
    result = discovered.json()["result"]
    assert result["supportedVersions"] == ["2026-07-28"]
    assert result["capabilities"] == {
        "resources": {"subscribe": False, "listChanged": False},
        "tools": {"listChanged": False},
    }
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"] == {
        "name": "folklore",
        "title": "Folklore Clinical Variant Interpretation MCP",
        "version": "1.4.0",
        "description": (
            "The official public, read-only Helena Bioinformatics MCP for clinical "
            "variant interpretation, ACMG/AMP evidence and related literature."
        ),
        "websiteUrl": "https://folklore.helena.bio",
        "icons": [
            {
                "src": "https://folklore.helena.bio/images/logos/folklore.png",
                "mimeType": "image/png",
            }
        ],
    }
    assert initialized.status_code == 404
    assert initialized.json()["error"] == {
        "code": -32601,
        "message": "Method not found",
        "data": "initialize",
    }


def test_mcp_lists_exact_tool_and_returns_structured_ui_equivalent_result() -> None:
    gateway = FakeGateway(resolved_result())
    app = create_app(
        enabled_settings(),
        gateway=gateway,
        metrics_registry=CollectorRegistry(),
    )
    with TestClient(app) as client:
        listed = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {"_meta": META},
            },
            headers=headers("tools/list"),
        )
        called = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "search_variant_evidence",
                    "arguments": {
                        "assembly": "GRCh38",
                        "query": "chr17:43124028 CTC>C",
                    },
                    "_meta": META,
                },
            },
            headers=headers("tools/call", "search_variant_evidence"),
        )
        metrics = client.get("/metrics").text
    assert listed.status_code == 200
    tools = listed.json()["result"]["tools"]
    assert [tool["name"] for tool in tools] == [
        "search_variant_evidence",
        "support_helena",
    ]
    assert tools[0]["icons"] == [
        {
            "src": "https://folklore.helena.bio/images/logos/folklore.png",
            "mimeType": "image/png",
        }
    ]
    assert tools[0]["annotations"] == {
        "title": "Classify a germline variant with Folklore",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    assert tools[0]["_meta"] == {
        "ui": {"resourceUri": "ui://folklore/variant-evidence/v1.html"},
        "openai/outputTemplate": "ui://folklore/variant-evidence/v1.html",
        "openai/toolInvocation/invoking": "Reading Folklore variant evidence",
        "openai/toolInvocation/invoked": "Folklore evidence ready",
    }
    assert called.status_code == 200
    structured = called.json()["result"]["structuredContent"]
    assert structured["result"] == resolved_result()
    assert structured["record_url"].startswith("https://folklore.helena.bio/variant?")
    assert structured["usage_boundary"] == {
        "result_type": "automated_variant_level_classification",
        "review_required": True,
        "patient_context_evaluated": False,
        "intended_use": "professional_variant_review",
        "not_for": [
            "patient_diagnosis",
            "treatment_decision",
            "standalone_clinical_reporting",
        ],
    }
    assert gateway.calls == 1
    assert 'outcome="resolved"' in metrics
    assert gateway.closed is True


def test_mcp_input_schemas_describe_every_parameter() -> None:
    app = create_app(
        literature_enabled_settings(),
        gateway=FakeGateway(resolved_result()),
        literature_gateway=FakeLiteratureGateway(),
    )
    with TestClient(app) as client:
        listed = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 20,
                "method": "tools/list",
                "params": {"_meta": META},
            },
            headers=headers("tools/list"),
        )

    tools = {tool["name"]: tool for tool in listed.json()["result"]["tools"]}
    assert set(tools) == {
        "search_variant_evidence",
        "search_variant_literature",
        "get_publication_details",
        "search_literature_corpus",
        "support_helena",
    }
    for tool in tools.values():
        for parameter in tool["inputSchema"]["properties"].values():
            assert parameter["description"].strip()

    evidence = tools["search_variant_evidence"]["inputSchema"]["properties"]
    assert evidence["assembly"]["const"] == "GRCh38"
    assert "GRCh38 only" in evidence["assembly"]["description"]
    assert "HGVS" in evidence["query"]["description"]
    assert "canonical_key" in evidence["query"]["description"]
    assert evidence["query"]["minLength"] == 1
    assert evidence["query"]["maxLength"] == 512

    variant_literature = tools["search_variant_literature"]["inputSchema"]["properties"]
    assert "variant identifier" in variant_literature["query"]["description"]
    assert "canonical_key" in variant_literature["query"]["description"]
    assert (
        "Optional natural-language focus"
        in variant_literature["question"]["description"]
    )
    assert variant_literature["question"]["anyOf"][0]["minLength"] == 3
    assert variant_literature["question"]["anyOf"][0]["maxLength"] == 500
    assert variant_literature["limit"]["minimum"] == 1
    assert variant_literature["limit"]["maximum"] == 25

    publication = tools["get_publication_details"]["inputSchema"]["properties"]
    assert "One PubMed identifier to look up" in publication["pmid"]["description"]
    assert publication["pmid"]["pattern"] == "^[0-9]{1,12}$"

    corpus = tools["search_literature_corpus"]["inputSchema"]["properties"]
    assert "Natural-language literature question" in corpus["query"]["description"]
    assert "Opaque continuation cursor" in corpus["cursor"]["description"]
    assert corpus["query"]["minLength"] == 3
    assert corpus["query"]["maxLength"] == 200
    assert corpus["sort"]["enum"] == ["relevance", "newest", "oldest"]
    assert corpus["cursor"]["anyOf"][0]["minLength"] == 8
    assert corpus["cursor"]["anyOf"][0]["maxLength"] == 128


def test_support_helena_is_explicit_read_only_and_does_not_call_science() -> None:
    gateway = FakeGateway(resolved_result())
    app = create_app(enabled_settings(), gateway=gateway)
    with TestClient(app) as client:
        called = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 21,
                "method": "tools/call",
                "params": {
                    "name": "support_helena",
                    "arguments": {},
                    "_meta": META,
                },
            },
            headers=headers("tools/call", "support_helena"),
        )
    assert called.status_code == 200
    result = called.json()["result"]["structuredContent"]
    assert result["service"] == "Helena Good"
    assert result["source_service"] == "folklore"
    assert result["relay_channel"] == "folklore"
    assert result["mcp_url"] == "https://api.helena.bio/good/v1/mcp"
    assert "never changes Folklore" in result["independence"]
    assert gateway.calls == 0


def test_mcp_lists_and_reads_public_variant_evidence_app() -> None:
    gateway = FakeGateway(resolved_result())
    app = create_app(enabled_settings(), gateway=gateway)
    with TestClient(app) as client:
        listed = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/list",
                "params": {"_meta": META},
            },
            headers=headers("resources/list"),
        )
        read = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "resources/read",
                "params": {
                    "uri": "ui://folklore/variant-evidence/v1.html",
                    "_meta": META,
                },
            },
            headers=headers("resources/read", "ui://folklore/variant-evidence/v1.html"),
        )

    assert listed.status_code == 200
    assert listed.json()["result"]["ttlMs"] == 0
    resource = listed.json()["result"]["resources"][0]
    assert resource["uri"] == "ui://folklore/variant-evidence/v1.html"
    assert resource["mimeType"] == "text/html;profile=mcp-app"
    assert resource["icons"][0]["src"].endswith("/folklore.png")
    assert resource["_meta"]["ui"]["csp"]["resourceDomains"] == [
        "https://folklore.helena.bio"
    ]
    assert resource["_meta"]["ui"]["prefersBorder"] is False
    assert resource["_meta"]["openai/widgetPrefersBorder"] is False
    assert resource["_meta"]["openai/widgetCSP"] == {
        "resource_domains": ["https://folklore.helena.bio"],
        "connect_domains": [],
    }

    assert read.status_code == 200
    assert read.json()["result"]["ttlMs"] == 0
    content = read.json()["result"]["contents"][0]
    assert content["mimeType"] == "text/html;profile=mcp-app"
    assert "/mcp-app/variant-evidence/widget.js?v=2" in content["text"]
    assert "/mcp-app/variant-evidence/widget.css?v=2" in content["text"]
    assert "patient" not in content["text"].lower()


def test_mcp_accepts_absent_and_known_origin_but_rejects_unknown_origin() -> None:
    gateway = FakeGateway(resolved_result())
    app = create_app(enabled_settings(), gateway=gateway)
    request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/list",
        "params": {"_meta": META},
    }
    with TestClient(app) as client:
        without_origin = client.post(
            "/folklore/v1/mcp",
            json=request,
            headers=headers("tools/list"),
        )
        known_origin = client.post(
            "/folklore/v1/mcp",
            json=request,
            headers={**headers("tools/list"), "Origin": "https://claude.ai"},
        )
        unknown_origin = client.post(
            "/folklore/v1/mcp",
            json=request,
            headers={**headers("tools/list"), "Origin": "https://evil.example"},
        )

    assert without_origin.status_code == 200
    assert known_origin.status_code == 200
    assert unknown_origin.status_code == 403
    assert unknown_origin.json() == {
        "jsonrpc": "2.0",
        "id": None,
        "error": {"code": -32000, "message": "Forbidden origin."},
    }


def test_ready_requires_enabled_adapter_and_upstream_resolver() -> None:
    gateway = FakeGateway(resolved_result(), ready=True)
    app = create_app(enabled_settings(), gateway=gateway)
    with TestClient(app) as client:
        response = client.get("/folklore/v1/ready")
    assert response.status_code == 200
    assert response.json()["dependencies"] == {
        "public_variant_search": True,
        "public_variant_literature": None,
    }


def test_publication_details_are_available_through_mcp() -> None:
    literature = FakeLiteratureGateway()
    app = create_app(
        literature_enabled_settings(),
        gateway=FakeGateway(resolved_result()),
        literature_gateway=literature,
        metrics_registry=CollectorRegistry(),
    )
    with TestClient(app) as client:
        listed = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/list",
                "params": {"_meta": META},
            },
            headers=headers("tools/list"),
        )
        called = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "get_publication_details",
                    "arguments": {"pmid": "12345678"},
                    "_meta": META,
                },
            },
            headers=headers("tools/call", "get_publication_details"),
        )

    assert [tool["name"] for tool in listed.json()["result"]["tools"]] == [
        "search_variant_evidence",
        "search_variant_literature",
        "get_publication_details",
        "search_literature_corpus",
        "support_helena",
    ]
    assert called.status_code == 200
    structured = called.json()["result"]["structuredContent"]
    assert structured["publication"]["abstract"] == "Full abstract."
    assert structured["usage_boundary"]["patient_context_evaluated"] is False


def test_marker_like_publication_text_is_data_in_mcp() -> None:
    marker = "[Tool result trimmed for length]"
    app = create_app(
        literature_enabled_settings(),
        gateway=FakeGateway(resolved_result()),
        literature_gateway=MarkerPublicationLiteratureGateway(),
        metrics_registry=CollectorRegistry(),
    )
    with TestClient(app) as client:
        called = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 22,
                "method": "tools/call",
                "params": {
                    "name": "get_publication_details",
                    "arguments": {"pmid": "12345678"},
                    "_meta": META,
                },
            },
            headers=headers("tools/call", "get_publication_details"),
        )

    assert called.status_code == 200
    result = called.json()["result"]
    assert result["structuredContent"]["publication"]["abstract"] == marker
    assert result["isError"] is False


def test_publication_not_found_is_scoped_in_mcp_error() -> None:
    message = (
        "No record for this PMID exists in Folklore's current PubMed-derived "
        "genetics corpus."
    )
    app = create_app(
        literature_enabled_settings(),
        gateway=FakeGateway(resolved_result()),
        literature_gateway=MissingPublicationLiteratureGateway(),
        metrics_registry=CollectorRegistry(),
    )
    with TestClient(app) as client:
        called = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 21,
                "method": "tools/call",
                "params": {
                    "name": "get_publication_details",
                    "arguments": {"pmid": "12345678"},
                    "_meta": META,
                },
            },
            headers=headers("tools/call", "get_publication_details"),
        )

    assert called.status_code == 200
    result = called.json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"] == message
    assert result["structuredContent"]["adapter_error"] == {
        "code": "publication_not_found",
        "message": message,
        "retryable": False,
    }


def test_literature_corpus_search_is_available_through_mcp() -> None:
    literature = FakeLiteratureGateway()
    app = create_app(
        literature_enabled_settings(),
        gateway=FakeGateway(resolved_result()),
        literature_gateway=literature,
        metrics_registry=CollectorRegistry(),
    )
    with TestClient(app) as client:
        called = client.post(
            "/folklore/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tools/call",
                "params": {
                    "name": "search_literature_corpus",
                    "arguments": {
                        "query": "BRCA1 homologous recombination",
                        "limit": 5,
                        "sort": "relevance",
                    },
                    "_meta": META,
                },
            },
            headers=headers("tools/call", "search_literature_corpus"),
        )

    assert called.status_code == 200
    payload = called.json()["result"]["structuredContent"]
    assert payload["semantic_index_used"] is True
    assert payload["results"][0]["pmid"] == "12345678"
    assert literature.corpus_payloads == [
        {
            "query": "BRCA1 homologous recombination",
            "limit": 5,
            "sort": "relevance",
        }
    ]
