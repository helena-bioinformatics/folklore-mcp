# Synthetic real-transport discovery, privacy and Phase1 compatibility (CR025).

import hashlib
import json
import logging
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from jsonschema import Draft202012Validator

from folklore_mcp_service.case_tools.api_client import ApiClient
from folklore_mcp_service.case_tools.common import CaseError
from folklore_mcp_service.case_tools.contracts import (
    INPUT_SCHEMAS,
    OUTPUT_SCHEMAS,
    TOOLS,
)
from folklore_mcp_service.case_tools.main import CaseService

KEY = "flk_" + "a" * 32 + "." + "b" * 43
A, C, X, INSTALLATION, M, ORGANIZATION, D, K, G, R = [
    str(UUID(int=n)) for n in range(1, 11)
]
T = "2026-11-02T10:00:00Z"
NAMES = ("list_cases", "get_case", "list_case_analyses", "list_source_connections")


def summary():
    return {
        "analysis_id": A,
        "status": "failed",
        "stage": "admission",
        "created_at": T,
        "updated_at": T,
    }


def case():
    return {
        "case_id": C,
        "case_name": "PRIVATE_CASE_LABEL",
        "analysis_type": "germline",
        "case_status": "failed",
        "created_at": T,
        "updated_at": T,
        "latest_analysis": summary(),
    }


def context():
    root = {
        "connection_id": R,
        "bucket": "private-fixture",
        "key_prefix": "PRIVATE_ROOT/",
    }
    return {
        "installation_id": INSTALLATION,
        "client_id": "fixture",
        "actor_kind": "machine",
        "user_id": None,
        "machine_principal_id": M,
        "credential_id": K,
        "contract_id": D,
        "billing_arrangement_id": None,
        "payer_organization_id": None,
        "organization_id": ORGANIZATION,
        "organization_type": "laboratory",
        "role": "machine",
        "context_binding_id": X,
        "binding_version": 1,
        "grant_id": G,
        "grant_version": 1,
        "scopes": ["analyses:read"],
        "connections": [root, deepcopy(root)],
        "profiles": ["singleton-germline-v1"],
        "context_name": None,
        "payer_name": None,
        "input_kinds": ["s3_object"],
        "billing": None,
    }


def page(records, **extra):
    return dict(
        context_binding_id=X,
        records=records,
        returned_count=len(records),
        has_more=False,
        next_cursor=None,
        **extra,
    )


def handler(request):
    assert request.headers["Authorization"] == "Bearer " + KEY
    assert request.url.host == "api.helena.bio"
    if request.url.path == "/folklore/v1/context":
        assert not request.url.query
        return httpx.Response(200, json={"contexts": [context()]})
    assert request.url.params["context_binding_id"] == X
    if request.url.path.endswith("/analyses"):
        return httpx.Response(
            200, json=page([summary()], case_id=C, history_kind="partner_commands")
        )
    if request.url.path.endswith("/" + C):
        return httpx.Response(200, json={"context_binding_id": X, "case": case()})
    assert request.url.path == "/folklore/v1/cases"
    return httpx.Response(200, json=page([case()]))


def schema_digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def test_all_seventeen_schemas_and_old_thirteen_identity():
    assert len(TOOLS) == len(set(TOOLS)) == 18
    baseline = json.loads(
        (Path(__file__).with_name("data") / "phase1-schema-hashes.json").read_text()
    )["tools"]
    assert len(baseline) == 13
    for name, hashes in baseline.items():
        assert schema_digest(INPUT_SCHEMAS[name]) == hashes["input"]
        assert schema_digest(OUTPUT_SCHEMAS[name]) == hashes["output"]
    for name in TOOLS:
        for schema in (INPUT_SCHEMAS[name], OUTPUT_SCHEMAS[name]):
            assert schema["type"] == "object"
            Draft202012Validator.check_schema(schema)


@pytest.mark.asyncio
async def test_four_views_real_client_service_private_structured_payload(tmp_path):
    calls = []

    def capture(request):
        calls.append(request)
        return handler(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(capture)) as transport:
        service = CaseService(
            KEY,
            tmp_path / "state",
            tmp_path / "out",
            api=ApiClient(KEY, client=transport),
        )
        try:
            for name in NAMES:
                args = {"context_binding_id": X}
                if name in ("get_case", "list_case_analyses"):
                    args["case_id"] = C
                if name == "list_cases":
                    args.update(query=" %_\\ private é ", limit=7)
                result = await service.call(name, args)
                assert not result.is_error, result.structured_content
                data = result.structured_content["data"]
                assert data["contract_version"] == "1.0.0"
                assert data["source_operation"] == name
                payload = data["result"]
                assert payload["context_binding_id"] == X
                if "returned_count" in payload:
                    assert isinstance(payload["returned_count"], str)
                text = " ".join(item.text for item in result.content)
                assert text == name + ": completed"
                assert "PRIVATE" not in text and C not in text
                if name == "list_source_connections":
                    assert payload["records"] == context()["connections"]
                    assert payload["returned_count"] == "2"
                if name == "list_case_analyses":
                    assert payload["history_kind"] == "partner_commands"
                    assert set(payload["records"][0]) == set(summary())
                    assert "cost" not in payload["records"][0]
                Draft202012Validator(OUTPUT_SCHEMAS[name]).validate(
                    result.structured_content
                )
        finally:
            await service.close()
    assert len(calls) == 4
    assert calls[0].url.params["query"] == " %_\\ private é "
    assert calls[0].url.params["limit"] == "7"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["wrong_context", "wrong_case", "count", "paging", "unknown", "bad_type"]
)
async def test_invalid_source_never_disclosed(tmp_path, failure):
    def source(request):
        value = {"context_binding_id": X, "case": case()}
        if failure == "wrong_context":
            value["context_binding_id"] = A
        if failure == "wrong_case":
            value["case"]["case_id"] = A
        if failure in ("count", "paging"):
            value = page([case()])
            value["returned_count"] = 2
            if failure == "paging":
                value.update(returned_count=1, has_more=True)
        if failure == "unknown":
            value["case"]["patient"] = "PRIVATE_VALUE"
        if failure == "bad_type":
            value["case"]["case_name"] = 42
        return httpx.Response(200, json=value)

    async with httpx.AsyncClient(transport=httpx.MockTransport(source)) as transport:
        service = CaseService(
            KEY, tmp_path / "s", tmp_path / "o", api=ApiClient(KEY, client=transport)
        )
        try:
            name = "list_cases" if failure in ("count", "paging") else "get_case"
            args = {"context_binding_id": X}
            if name == "get_case":
                args["case_id"] = C
            result = await service.call(name, args)
            assert result.is_error
            assert (
                result.structured_content["error"]["code"] == "source_contract_mismatch"
            )
            assert "PRIVATE" not in str(result.content)
        finally:
            await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["human", "missing", "too_many", "bad_prefix", "bad_bucket"]
)
async def test_source_grants_current_admission_and_bounds(tmp_path, failure):
    def source(request):
        assert request.url.path == "/folklore/v1/context"
        item = context()
        if failure == "human":
            item.update(actor_kind="human", user_id=A)
        if failure == "missing":
            item["context_binding_id"] = A
        if failure == "too_many":
            item["connections"] *= 33
        if failure == "bad_prefix":
            item["connections"][0]["key_prefix"] = "../PRIVATE/"
        if failure == "bad_bucket":
            item["connections"][0]["bucket"] = "ab"
        return httpx.Response(200, json={"contexts": [item]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(source)) as transport:
        service = CaseService(
            KEY, tmp_path / "s", tmp_path / "o", api=ApiClient(KEY, client=transport)
        )
        try:
            result = await service.call(
                "list_source_connections", {"context_binding_id": X}
            )
            assert result.is_error
        finally:
            await service.close()


@pytest.mark.asyncio
async def test_nonretryable_api_budget_preserved_and_no_repeat(tmp_path):
    calls = []

    def source(request):
        calls.append(request)
        return httpx.Response(
            503,
            json={
                "request_id": A,
                "error": {
                    "code": "discovery_response_too_large",
                    "message": "PRIVATE",
                    "retryable": False,
                },
            },
            headers={"X-Request-ID": A},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(source)) as transport:
        service = CaseService(
            KEY, tmp_path / "s", tmp_path / "o", api=ApiClient(KEY, client=transport)
        )
        try:
            result = await service.call("list_cases", {"context_binding_id": X})
            assert (
                result.structured_content["error"]["code"]
                == "discovery_response_too_large"
            )
            assert result.structured_content["error"]["retryable"] is False
            assert len(calls) == 1
            assert "PRIVATE" not in str(result.content)
        finally:
            await service.close()


@pytest.mark.asyncio
async def test_valid_api_page_can_exceed_mcp_budget_without_partial_disclosure(
    tmp_path,
):
    records = []
    for n in range(100):
        row = case()
        row["case_id"] = str(UUID(int=n + 100))
        row["case_name"] = "🧬" * 200
        row["latest_analysis"]["analysis_id"] = str(UUID(int=n + 1000))
        records.append(row)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=page(records))
        )
    ) as transport:
        service = CaseService(
            KEY, tmp_path / "s", tmp_path / "o", api=ApiClient(KEY, client=transport)
        )
        try:
            result = await service.call(
                "list_cases", {"context_binding_id": X, "limit": 100}
            )
            assert (
                result.structured_content["error"]["code"] == "response_budget_exceeded"
            )
            assert "data" not in result.structured_content
        finally:
            await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, "invalid_api_key", False),
        (403, "partner_access_denied", False),
        (404, "case_not_found", False),
        (422, "invalid_cursor", False),
    ],
)
async def test_source_error_codes_and_privacy_preserved(
    tmp_path, status, code, retryable
):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status,
                json={
                    "request_id": A,
                    "error": {
                        "code": code,
                        "message": "PRIVATE_SOURCE",
                        "retryable": retryable,
                    },
                },
                headers={"X-Request-ID": A},
            )
        )
    ) as transport:
        service = CaseService(
            KEY, tmp_path / "s", tmp_path / "o", api=ApiClient(KEY, client=transport)
        )
        try:
            result = await service.call(
                "get_case", {"context_binding_id": X, "case_id": C}
            )
            assert result.structured_content["error"]["code"] == code
            assert result.structured_content["error"]["retryable"] == retryable
            assert "PRIVATE_SOURCE" not in str(result)
        finally:
            await service.close()


def test_private_transport_redacts_existing_and_future_logger_names(caplog):
    from folklore_mcp_service.case_tools.private_logging import protect_transport_logs

    release = protect_transport_logs()
    try:
        with caplog.at_level(logging.DEBUG):
            for name in (
                "httpx",
                "httpcore.connection",
                "httpcore.dynamic_private_fixture",
                "mcp.server.lowlevel",
            ):
                logger = logging.getLogger(name)
                logger.disabled = False
                logger.debug("PRIVATE_QUERY=%s", "PRIVATE_CURSOR/PRIVATE_ROOT/" + C)
                logger.info("PRIVATE_QUERY=%s", "PRIVATE_CURSOR/PRIVATE_ROOT/" + C)
        assert "PRIVATE_QUERY" not in caplog.text
        assert "PRIVATE_CURSOR" not in caplog.text
        assert "PRIVATE_ROOT" not in caplog.text
        assert C not in caplog.text
        assert "Private" in caplog.text
    finally:
        release()


def test_hosted_and_legacy_stdio_release_metadata():
    from folklore_mcp_service import __version__
    from folklore_mcp_service.case_tools.common import SOFTWARE_VERSION, VERSION
    from folklore_mcp_service.presentation.mcp import MCP_ADAPTER_VERSION

    assert VERSION == "1.0.0"
    assert SOFTWARE_VERSION == "1.2.0"
    assert __version__ == "2.0.0"
    assert MCP_ADAPTER_VERSION == "2.0.0"
    import os

    if os.environ.get("FOLKLORE_CASE_TEST_INSTALLED") == "1":
        from importlib.metadata import version

        assert version("folklore-mcp-service") == "2.0.0"


@pytest.mark.asyncio
async def test_genuine_sdk_four_successes_initialize_and_debug_stderr(tmp_path):
    import os
    import sys

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    source = Path(__file__).resolve().parents[1] / "src"
    launch = (
        "import sys,socket,logging; sys.path.insert(0,"
        + repr(str(Path(__file__).parent))
        + "); "
        + "logging.basicConfig(level=logging.DEBUG); "
        + "from test_case_discovery import handler; import httpx; "
        + "from folklore_mcp_service.case_tools import main; "
        + "from folklore_mcp_service.case_tools.api_client import ApiClient; "
        + "main.ApiClient=lambda key: ApiClient(key,client=httpx.AsyncClient(transport=httpx.MockTransport(handler))); "
        + "socket.socket.connect=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('Network prohibited')); main.main()"
    )
    env = {
        "FOLKLORE_API_KEY": KEY,
        "FOLKLORE_CASE_STATE_DIR": str(tmp_path / "state"),
        "FOLKLORE_CASE_OUTPUT_DIR": str(tmp_path / "output"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(source),
    }
    if os.environ.get("FOLKLORE_CASE_TEST_INSTALLED") == "1":
        env.pop("PYTHONPATH")
    errors = tmp_path / "private-stderr.txt"
    with errors.open("w+") as log:
        async with stdio_client(
            StdioServerParameters(command=sys.executable, args=["-c", launch], env=env),
            errlog=log,
        ) as streams:
            async with ClientSession(*streams, read_timeout_seconds=15) as session:
                initialized = await session.initialize()
                assert initialized.server_info.version == "1.2.0"
                listing = await session.list_tools()
                assert tuple(tool.name for tool in listing.tools) == TOOLS
                assert len(listing.tools) == 18
                for name in NAMES:
                    args = {"context_binding_id": X}
                    if name in ("get_case", "list_case_analyses"):
                        args["case_id"] = C
                    if name == "list_cases":
                        args["query"] = "PRIVATE_QUERY"
                    result = await session.call_tool(name, args)
                    assert not result.is_error, result.structured_content
                    assert result.structured_content["data"]["source_operation"] == name
                    if "returned_count" in result.structured_content["data"]["result"]:
                        assert isinstance(
                            result.structured_content["data"]["result"][
                                "returned_count"
                            ],
                            str,
                        )
        log.flush()
    raw = errors.read_text()
    for secret in (KEY, "PRIVATE_QUERY", "PRIVATE_ROOT", C, X):
        assert secret not in raw


@pytest.mark.asyncio
async def test_transport_logging_on_actual_retry_error_and_private_request(
    caplog, tmp_path, monkeypatch
):
    calls = []

    def source(request):
        calls.append(request)
        logging.getLogger("httpcore.private_after_service_creation").debug(
            "request=%s roots=%s", str(request.url), context()["connections"]
        )
        return httpx.Response(
            503,
            json={
                "request_id": A,
                "error": {
                    "code": "partner_discovery_unavailable",
                    "message": "PRIVATE_QUERY",
                    "retryable": True,
                },
            },
            headers={"X-Request-ID": A},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(source)) as transport:
        api = ApiClient(KEY, client=transport)

        async def immediate_wait(delay, waited):
            return waited + delay

        monkeypatch.setattr(api, "_wait", immediate_wait)
        service = CaseService(KEY, tmp_path / "s", tmp_path / "o", api=api)
        try:
            with caplog.at_level(logging.DEBUG):
                result = await service.call(
                    "list_case_analyses",
                    {"context_binding_id": X, "case_id": C, "cursor": "PRIVATE_CURSOR"},
                )
            assert result.structured_content["error"]["retryable"] is True
            assert len(calls) == 3
            assert calls[0].url.params["cursor"] == "PRIVATE_CURSOR"
            for value in (KEY, C, X, "PRIVATE_CURSOR", "PRIVATE_QUERY", "PRIVATE_ROOT"):
                assert value not in caplog.text
        finally:
            await service.close()


@pytest.mark.asyncio
async def test_complete_maximum_source_roots_use_typed_budget_error(tmp_path):
    item = context()
    item["connections"] = [
        {"connection_id": R, "bucket": "b" * 255, "key_prefix": "p" * 1023 + "/"}
        for _ in range(64)
    ]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"contexts": [item]})
        )
    ) as transport:
        service = CaseService(
            KEY, tmp_path / "s", tmp_path / "o", api=ApiClient(KEY, client=transport)
        )
        try:
            result = await service.call(
                "list_source_connections", {"context_binding_id": X}
            )
            assert (
                result.structured_content["error"]["code"] == "response_budget_exceeded"
            )
            assert "data" not in result.structured_content
        finally:
            await service.close()


def test_postgresql_unrepresentable_query_is_rejected_locally():
    from folklore_mcp_service.case_tools.contracts import validate_input

    with pytest.raises(CaseError) as error:
        validate_input(
            "list_cases",
            {"context_binding_id": X, "query": "private" + chr(0) + "query"},
        )
    assert error.value.code == "invalid_input"
