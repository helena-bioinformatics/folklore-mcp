"""Hosted request boundary acceptance through actual ASGI/SDK HTTP dispatch."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from test_app_and_mcp import META, FakeGateway, headers
from test_contracts import resolved_result

from folklore_mcp_service.case_tools.common import CaseError
from folklore_mcp_service.case_tools.contracts import TOOLS
from folklore_mcp_service.case_tools.main import CaseService
from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.main import create_app
from folklore_mcp_service.presentation.case_auth import current_api_key
from folklore_mcp_service.presentation.mcp import FolkloreMcpApplication

A = "flk_" + "a" * 32 + "." + "b" * 43
B = "flk_" + "c" * 32 + "." + "d" * 43


class Manager:
    def __init__(self):
        self.admitted = []
        self.calls = []
        self.revoked = set()
        self.closed = False
        self.slow = False

    async def authorize(self, key):
        self.admitted.append(key)
        if key in self.revoked:
            raise CaseError("admission_denied")

    async def call(self, key, name, arguments):
        before = current_api_key.get()
        await asyncio.sleep(0.01)
        assert current_api_key.get() == before == key
        if self.slow:
            await asyncio.Event().wait()
        self.calls.append((key, name, arguments))
        return CaseService._result(
            name,
            {
                "ok": True,
                "data": {
                    "contract_version": "1.0.0",
                    "source_operation": name,
                    "result": {"contexts": []},
                },
            },
        )

    async def close(self):
        self.closed = True


def app_for(manager):
    settings = Settings(
        ENVIRONMENT="test",
        FOLKLORE_MCP_ENABLED=True,
        FOLKLORE_MCP_CASES_ENABLED=True,
        FOLKLORE_MCP_CASE_NAMESPACE_SECRET="a" * 64,
        FOLKLORE_LITERATURE_ENABLED=True,
        FOLKLORE_GENE_DISEASE_ENABLED=True,
        FOLKLORE_PUBLIC_GENE_ENABLED=True,
    )
    return create_app(
        settings,
        gateway=FakeGateway(resolved_result()),
        metrics_registry=CollectorRegistry(),
        case_manager=manager,
    )


def packet(method, name=None, arguments=None):
    params = {"_meta": META}
    if name:
        params.update(name=name, arguments=arguments or {})
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}


def request_headers(method, name=None, key=None):
    result = headers(method, name)
    if key:
        result["Authorization"] = "Bearer " + key
    return result


def test_auth_catalog_and_private_disclosure_headers():
    manager = Manager()
    with TestClient(app_for(manager)) as client:
        anonymous = client.post(
            "/folklore/v1/mcp",
            json=packet("tools/list"),
            headers=request_headers("tools/list"),
        )
        authenticated = client.post(
            "/folklore/v1/mcp",
            json=packet("tools/list"),
            headers=request_headers("tools/list", key=A),
        )
        assert anonymous.status_code == authenticated.status_code == 200
        public = anonymous.json()["result"]
        private = authenticated.json()["result"]
        assert len(public["tools"]) == 11
        assert len(private["tools"]) == 29
        assert {t["name"] for t in private["tools"]} - {
            t["name"] for t in public["tools"]
        } == set(TOOLS)
        assert private["cacheScope"] == "private"
        assert private["ttlMs"] == 0
        assert "private" in authenticated.headers["cache-control"]
        assert "no-store" in authenticated.headers["cache-control"]
        assert "authorization" in authenticated.headers["vary"].lower()
        assert "authorization" in anonymous.headers["vary"].lower()
        assert A not in authenticated.text
    assert manager.closed


@pytest.mark.parametrize(
    "authorization",
    [
        "Basic abc",
        "Bearer browser-session",
        "Bearer " + A + ", Bearer " + B,
        "bearer " + A,
        "Bearer  " + A,
    ],
)
def test_non_machine_credentials_rejected_before_case_dispatch(authorization):
    manager = Manager()
    with TestClient(app_for(manager)) as client:
        hs = request_headers("tools/list")
        hs["Authorization"] = authorization
        response = client.post(
            "/folklore/v1/mcp", json=packet("tools/list"), headers=hs
        )
        assert response.status_code == 401
        assert response.headers["cache-control"] == "private, no-store"
        assert "www-authenticate" in response.headers
    assert not manager.admitted
    assert not manager.calls


def test_duplicate_auth_and_revoked_key_never_fall_back_to_anonymous():
    manager = Manager()
    with TestClient(app_for(manager)) as client:
        hs = list(request_headers("tools/list").items())
        hs += [("Authorization", "Bearer " + A), ("Authorization", "Bearer " + B)]
        duplicate = client.post(
            "/folklore/v1/mcp", json=packet("tools/list"), headers=hs
        )
        assert duplicate.status_code == 401
        manager.revoked.add(A)
        revoked = client.post(
            "/folklore/v1/mcp",
            json=packet("tools/list"),
            headers=request_headers("tools/list", key=A),
        )
        assert revoked.status_code == 401
        no_key = client.post(
            "/folklore/v1/mcp",
            json=packet("tools/call", TOOLS[0]),
            headers=request_headers("tools/call", TOOLS[0]),
        )
        assert no_key.status_code == 200
        assert (
            no_key.json()["result"]["structuredContent"]["error"]["code"]
            == "authentication_required"
        )
    assert not manager.calls


def test_case_calls_do_not_increment_public_tool_metrics():
    manager = Manager()
    app = app_for(manager)
    with TestClient(app) as client:
        before = client.get("/metrics").text
        private = client.post(
            "/folklore/v1/mcp",
            json=packet("tools/call", TOOLS[0]),
            headers=request_headers("tools/call", TOOLS[0], A),
        )
        after = client.get("/metrics").text
        assert private.status_code == 200
        assert not private.json()["result"]["isError"]

        def tool_counts(text):
            return [
                line
                for line in text.splitlines()
                if line.startswith("folklore_mcp_tool_calls_total{")
            ]

        assert tool_counts(before) == tool_counts(after)


@pytest.mark.asyncio
async def test_actual_http_concurrent_credentials_and_anonymous_isolation():
    manager = Manager()
    app = app_for(manager)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            follow_redirects=True,
        ) as client:

            async def call(key):
                return await client.post(
                    "/folklore/v1/mcp",
                    json=packet("tools/call", TOOLS[0]),
                    headers=request_headers("tools/call", TOOLS[0], key),
                )

            a, b, anonymous = await asyncio.gather(call(A), call(B), call(None))
            assert all(r.status_code == 200 for r in (a, b, anonymous))
            assert sorted(key for key, _, _ in manager.calls) == sorted([A, B])
            assert anonymous.json()["result"]["isError"]
            assert current_api_key.get() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_request_context_reset_after_transport_exception_or_cancel(cancel):
    class Broken:
        async def __call__(self, scope, receive, send):
            assert current_api_key.get() == A
            if cancel:
                raise asyncio.CancelledError
            raise RuntimeError("synthetic transport failure")

    manager = Manager()
    wrapper = FolkloreMcpApplication(
        Broken(), allowed_origins=frozenset(), case_manager=manager
    )

    async def noop(*args):
        return None

    exc = asyncio.CancelledError if cancel else RuntimeError
    with pytest.raises(exc):
        await wrapper(
            {"type": "http", "headers": [(b"authorization", ("Bearer " + A).encode())]},
            noop,
            noop,
        )
    assert current_api_key.get() is None


def test_hosted_settings_require_private_state_and_secret():
    from pydantic import ValidationError

    for extra in (
        {},
        {
            "FOLKLORE_MCP_CASE_NAMESPACE_SECRET": "a" * 64,
            "FOLKLORE_MCP_CASE_STATE_DIR": "relative",
        },
    ):
        with pytest.raises(ValidationError):
            Settings(
                FOLKLORE_MCP_ENABLED=True, FOLKLORE_MCP_CASES_ENABLED=True, **extra
            )


def test_hosted_namespace_capacity_cannot_be_below_instance_capacity():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(
            FOLKLORE_MCP_ENABLED=True,
            FOLKLORE_MCP_CASES_ENABLED=True,
            FOLKLORE_MCP_CASE_NAMESPACE_SECRET="a" * 64,
            FOLKLORE_MCP_CASE_MAX_NAMESPACES=7,
        )
