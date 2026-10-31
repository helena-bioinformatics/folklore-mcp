"""Offline contract tests. Synthetic upstream data never qualifies a live client."""

import importlib.util
import io
import json
from copy import deepcopy
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient
from test_app_and_mcp import FakeGateway
from test_contracts import resolved_result
from test_public_gene import FakePublicGeneGateway, resolution

from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.public_gene_contracts import public_gene_boundary
from folklore_mcp_service.main import create_app

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "direct_identity_smoke",
    ROOT / "integrations/direct-streamable-http/smoke_test.py",
)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def fixture_message():
    return {
        "jsonrpc": "2.0",
        "id": smoke.REQUEST_ID,
        "result": {
            "isError": False,
            "structuredContent": {
                "contract_version": "1",
                "adapter_error": None,
                "record_url": "https://folklore.helena.bio/gene/BRCA1",
                "usage_boundary": public_gene_boundary(),
                "result": resolution({"query": "BRCA1", "request_id": "synthetic"}),
            },
        },
    }


class Response(io.BytesIO):
    def __init__(self, body, status=200, media="application/json"):
        super().__init__(body)
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = media


class Sender:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        return self.response


def test_actual_request_through_local_sdk_dispatch():
    genes = FakePublicGeneGateway()
    app = create_app(
        Settings(FOLKLORE_MCP_ENABLED=True, FOLKLORE_PUBLIC_GENE_ENABLED=True),
        gateway=FakeGateway(resolved_result()),
        public_gene_gateway=genes,
    )
    request = smoke.make_request()
    payload = json.loads(request.data)
    headers = dict(request.header_items())
    assert request.full_url == smoke.ENDPOINT
    assert request.method == "POST"
    assert payload["params"]["arguments"] == {"query": "BRCA1"}
    assert "Origin" not in headers
    assert "application/json" in request.get_header("Accept")
    assert "text/event-stream" in request.get_header("Accept")
    with TestClient(app) as client:
        response = client.post(
            "/folklore/v1/mcp", content=request.data, headers=headers
        )
        assert response.status_code == 200
        assert smoke.check_identity(response.json())["result"]["status"] == "exact"
        assert len(genes.calls) == 1
        assert genes.calls[0] == ("resolve", {"query": "BRCA1"})
        headers["Mcp-name"] = "get_gene_profile"
        denied = client.post("/folklore/v1/mcp", content=request.data, headers=headers)
        assert denied.status_code == 400
        assert len(genes.calls) == 1


def test_single_send_has_no_hidden_preflight_or_retry():
    sender = Sender(Response(json.dumps(fixture_message()).encode()))
    result = smoke.run_probe(sender)
    assert result["result"]["candidates"][0]["identity"]["gene_id"] == "HGNC:1100"
    assert len(sender.calls) == 1
    assert sender.calls[0][1] == 150


@pytest.mark.parametrize(
    "path,value",
    [
        (("id",), "wrong-response"),
        (("error",), {"code": -32602}),
        (("result", "isError"), True),
        (
            ("result", "structuredContent", "adapter_error"),
            {"code": "upstream_timeout"},
        ),
        (("result", "structuredContent", "result"), None),
        (("result", "structuredContent", "result", "status"), "ambiguous"),
        (("result", "structuredContent", "result", "complete"), False),
        (("result", "structuredContent", "result", "candidate_total"), True),
        (("result", "structuredContent", "result", "identity_snapshot_id"), "invented"),
        (
            (
                "result",
                "structuredContent",
                "result",
                "candidates",
                0,
                "identity",
                "gene_id",
            ),
            "HGNC:11998",
        ),
        (
            (
                "result",
                "structuredContent",
                "result",
                "candidates",
                0,
                "identity",
                "source_id",
            ),
            "",
        ),
        (
            (
                "result",
                "structuredContent",
                "usage_boundary",
                "patient_context_evaluated",
            ),
            True,
        ),
        (("result", "structuredContent", "usage_boundary", "review_required"), False),
        (("result", "structuredContent", "usage_boundary", "not_for"), []),
        (
            ("result", "structuredContent", "usage_boundary", "not_for"),
            ["patient_diagnosis", "treatment_decision"],
        ),
    ],
)
def test_http200_cannot_turn_missing_or_conflicting_evidence_into_success(path, value):
    message = deepcopy(fixture_message())
    target = message
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(smoke.SmokeFailure):
        smoke.check_identity(message)


@pytest.mark.parametrize(
    "response",
    [
        Response(b"{}", status=429),
        Response(b"event: message\n", media="text/event-stream"),
        Response(b'{"id":1,"id":2}'),
        Response(b'{"nested":{"value":1,"value":2}}'),
        Response(b'{"value":NaN}'),
        Response(b"{}" + b" " * smoke.MAX_RESPONSE_BYTES),
        Response(b"not json"),
    ],
)
def test_transport_media_and_json_rejections_are_not_scientific_results(response):
    sender = Sender(response)
    with pytest.raises(ValueError):
        smoke.run_probe(sender)
    assert len(sender.calls) == 1


def test_redirect_policy_never_replays_the_post():
    handler = smoke.NoRedirect()
    assert (
        handler.redirect_request(
            smoke.make_request(), None, 307, "redirect", {}, "https://other.invalid/"
        )
        is None
    )


def test_missing_exclusions_fail_and_order_is_not_scientific_meaning():
    message = fixture_message()
    boundary = message["result"]["structuredContent"]["usage_boundary"]
    boundary["not_for"].reverse()
    assert smoke.check_identity(message)
    del boundary["not_for"]
    with pytest.raises(smoke.SmokeFailure):
        smoke.check_identity(message)


def test_http429_main_exits_without_retry(monkeypatch, capsys):
    calls = []

    def rejected():
        calls.append("one")
        raise HTTPError(smoke.ENDPOINT, 429, "limited", {}, None)

    monkeypatch.setattr(smoke, "run_probe", rejected)
    assert smoke.main() == 1
    assert calls == ["one"]
    assert "No automatic retry" in capsys.readouterr().err
