"""Source browsing relay, immutable selections, privacy and frozen compatibility."""

import asyncio
import hashlib
import json
import logging
import os
import sys
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from folklore_mcp_service.case_tools import source_browse
from folklore_mcp_service.case_tools.api_client import ApiClient
from folklore_mcp_service.case_tools.common import CaseError
from folklore_mcp_service.case_tools.contracts import (
    INPUT_SCHEMAS,
    OUTPUT_SCHEMAS,
    TOOLS,
)
from folklore_mcp_service.case_tools.main import CaseService

KEY = "flk_" + "a" * 32 + "." + "b" * 43
X, R, RID = [str(UUID(int=n)) for n in (3, 10, 99)]
ARGS = {"context_binding_id": X, "connection_id": R}
PRIVATE = "PRIVATE_SOURCE"
T = "2026-11-04T10:00:00Z"


def roots():
    return {
        **ARGS,
        "parent": None,
        "records": [
            {
                "kind": "root",
                "root_index": 0,
                "bucket": "synthetic-bucket",
                "key_prefix": PRIVATE + "/",
                "parent_handle": "opaque-parent",
            }
        ],
        "returned_count": 1,
        "has_more": False,
        "next_cursor": None,
    }


def files(state="versioned", key=None):
    key = key or PRIVATE + "/input.vcf"
    version = "immutable-v1" if state == "versioned" else None
    available = state != "unavailable"
    selectable = state == "versioned" and source_browse.supported_input_key(key)
    reason = (
        None
        if selectable
        else (
            "unsupported_input_key"
            if state == "versioned"
            else "versioning_required"
            if state == "unversioned"
            else "access_denied"
        )
    )
    selection = (
        {
            "connection_id": R,
            "bucket": "synthetic-bucket",
            "key": key,
            "version_id": version,
            "size_bytes": 9007199254740993,
        }
        if selectable
        else None
    )
    return {
        **ARGS,
        "parent": {
            "root_index": 0,
            "bucket": "synthetic-bucket",
            "prefix": PRIVATE + "/",
        },
        "records": [
            {
                "kind": "file",
                "key": key,
                "metadata_state": state,
                "version_id": version,
                "size_bytes": 9007199254740993 if available else None,
                "last_modified": T if available else None,
                "selectable": selectable,
                "selection": selection,
                "reason": reason,
            }
        ],
        "returned_count": 1,
        "has_more": False,
        "next_cursor": None,
    }


async def invoke(tmp_path, value, args=None, status=200, headers=None):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url == "https://api.helena.bio/folklore/v1/source-objects"
        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer " + KEY
        assert "Idempotency-Key" not in request.headers
        return httpx.Response(status, json=value, headers=headers)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = CaseService(
            KEY, tmp_path / "s", tmp_path / "o", api=ApiClient(KEY, client=client)
        )
        try:
            result = await service.call(source_browse.TOOL, args or ARGS)
        finally:
            await service.close()
    return result, calls


def test_all_seventeen_existing_schemas_are_identical():
    baseline = json.loads(
        (Path(__file__).parent / "data/phase2-schema-hashes.json").read_text()
    )["tools"]
    assert tuple(baseline) == TOOLS[:17]
    assert len(TOOLS) == 18
    for name, hashes in baseline.items():
        for kind, schemas in (("input", INPUT_SCHEMAS), ("output", OUTPUT_SCHEMAS)):
            raw = json.dumps(
                schemas[name], sort_keys=True, separators=(",", ":")
            ).encode()
            assert hashlib.sha256(raw).hexdigest() == hashes[kind], (name, kind)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"limit": True},
        {"limit": 0},
        {"limit": 26},
        {"limit": 1.0},
        {"context_binding_id": "bad"},
        {"connection_id": "bad"},
        {"bucket": "override"},
        {"api_key": "private"},
        {"origin": "https://private"},
        {"cursor": ""},
        {"parent_handle": ""},
        {"cursor": "x" * 16385},
    ],
)
async def test_invalid_arguments_never_send_http(tmp_path, changes):
    result, calls = await invoke(tmp_path, roots(), {**ARGS, **changes})
    assert not calls
    assert result.structured_content["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_root_page_and_defaults_are_relayed(tmp_path):
    result, calls = await invoke(tmp_path, roots())
    assert not result.is_error, result.structured_content
    assert result.structured_content["data"]["result"]["returned_count"] == "1"
    body = json.loads(calls[0].content)
    assert body == {**ARGS, "limit": 10, "parent_handle": None, "cursor": None}
    assert result.content[0].text == "browse_source_objects: completed"
    assert PRIVATE not in result.content[0].text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state,key",
    [
        ("versioned", None),
        ("unversioned", None),
        ("unavailable", None),
        ("versioned", PRIVATE + "/"),
        ("versioned", PRIVATE + "/.."),
        ("versioned", PRIVATE + "/a\\b"),
    ],
)
async def test_metadata_and_exact_selection(tmp_path, state, key):
    page = files(state, key)
    result, calls = await invoke(
        tmp_path, page, {**ARGS, "parent_handle": "opaque-parent"}
    )
    assert not result.is_error, result.structured_content
    record = result.structured_content["data"]["result"]["records"][0]
    assert record["selectable"] == page["records"][0]["selectable"]
    if state != "unavailable":
        assert record["size_bytes"] == "9007199254740993"
    if record["selectable"]:
        assert record["selection"]["version_id"] == "immutable-v1"
        assert record["selection"]["size_bytes"] == "9007199254740993"


@pytest.mark.asyncio
async def test_one_level_folder_and_literal_repeated_slash(tmp_path):
    page = files()
    page["records"] = [
        {"kind": "folder", "prefix": PRIVATE + "//", "parent_handle": "next"}
    ]
    result, _ = await invoke(tmp_path, page, {**ARGS, "parent_handle": "opaque-parent"})
    assert not result.is_error, result.structured_content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "context",
        "connection",
        "count",
        "cursor",
        "parent",
        "kind",
        "outside",
        "descendant",
        "duplicate",
        "latest",
        "null",
        "size",
        "time",
        "selection",
        "reason",
        "selectable",
        "extra",
        "missing",
    ],
)
async def test_corrupt_page_is_rejected_without_partial_data(tmp_path, change):
    page = files()
    row = page["records"][0]
    if change == "context":
        page["context_binding_id"] = RID
    elif change == "connection":
        page["connection_id"] = RID
    elif change == "count":
        page["returned_count"] = 0
    elif change == "cursor":
        page["has_more"] = True
    elif change == "parent":
        page["parent"] = None
    elif change == "kind":
        row["kind"] = "root"
    elif change == "outside":
        row["key"] = "other/input.vcf"
    elif change == "descendant":
        row["key"] = PRIVATE + "/sub/input.vcf"
    elif change == "duplicate":
        page["records"].append(deepcopy(row))
        page["returned_count"] = 2
    elif change in ("latest", "null"):
        row["version_id"] = change
    elif change == "size":
        row["size_bytes"] = -1
    elif change == "time":
        row["last_modified"] = "2026-11-04T10:00:00+02:00"
    elif change == "selection":
        row["selection"]["bucket"] = "other"
    elif change == "reason":
        row["reason"] = "access_denied"
    elif change == "selectable":
        row["selectable"] = False
    elif change == "extra":
        row["raw_provider_token"] = PRIVATE
    elif change == "missing":
        del row["kind"]
    result, _ = await invoke(tmp_path, page, {**ARGS, "parent_handle": "opaque-parent"})
    assert result.is_error
    assert result.structured_content["error"]["code"] == "source_contract_mismatch"
    assert "data" not in result.structured_content
    assert PRIVATE not in str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 503])
async def test_post_is_not_retried_and_retry_after_is_preserved(tmp_path, status):
    page = {
        "request_id": RID,
        "error": {
            "code": "source_browse_unavailable",
            "message": PRIVATE,
            "retryable": True,
        },
    }
    result, calls = await invoke(
        tmp_path,
        page,
        status=status,
        headers={"X-Request-ID": RID, "Retry-After": "17"},
    )
    assert len(calls) == 1
    assert result.structured_content["error"]["code"] == "source_browse_unavailable"
    assert result.structured_content["error"]["retryable"] is True
    assert "17 seconds" in result.structured_content["error"]["message"]
    assert PRIVATE not in str(result)


@pytest.mark.asyncio
async def test_total_deadline_cancels_and_closes_transport(tmp_path, monkeypatch):
    closed = asyncio.Event()

    async def handler(request):
        try:
            await asyncio.sleep(10)
        finally:
            closed.set()

    monkeypatch.setattr(source_browse, "TOTAL_TIMEOUT", 0.02)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        api = ApiClient(KEY, client=client)
        with pytest.raises(CaseError) as caught:
            await api.browse_source_objects(ARGS)
    assert caught.value.code == "upstream_unavailable"
    assert closed.is_set()


@pytest.mark.asyncio
async def test_api_body_and_complete_mcp_envelope_budgets(tmp_path):
    result, _ = await invoke(tmp_path, {"private": "x" * 262144})
    assert result.structured_content["error"]["code"] == "source_contract_mismatch"
    page = roots()
    page["records"] = [
        {**page["records"][0], "root_index": n, "parent_handle": "x" * 8192}
        for n in range(10)
    ]
    page["returned_count"] = 10
    result, _ = await invoke(tmp_path, page)
    assert result.structured_content["error"]["code"] == "response_budget_exceeded"
    assert "data" not in result.structured_content


@pytest.mark.asyncio
async def test_source_transport_logging_is_private(tmp_path, caplog):
    with caplog.at_level(logging.DEBUG):
        result, _ = await invoke(tmp_path, files(), {**ARGS, "parent_handle": PRIVATE})
    assert not result.is_error
    assert PRIVATE not in caplog.text and KEY not in caplog.text


@pytest.mark.asyncio
async def test_genuine_sdk_browse_success_is_structured_and_private(tmp_path):
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    source = Path(__file__).resolve().parents[1] / "src"
    launch = (
        "import sys,socket,logging;sys.path.insert(0,"
        + repr(str(Path(__file__).parent))
        + ");"
        "logging.basicConfig(level=logging.DEBUG);"
        "from test_case_source_browse import roots;from test_case_discovery import context;import httpx;"
        "ctx=context();ctx['scopes']=['analyses:read','analyses:create','results:read','credits:read','sources:browse'];"
        "from folklore_mcp_service.case_tools import main;"
        "from folklore_mcp_service.case_tools.api_client import ApiClient;"
        "main.ApiClient=lambda key:ApiClient(key,client=httpx.AsyncClient("
        "transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'contexts':[ctx]} if r.url.path.endswith('/context') else roots()))));"
        "socket.socket.connect=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network prohibited'));main.main()"
    )
    env = {
        "FOLKLORE_API_KEY": KEY,
        "FOLKLORE_CASE_STATE_DIR": str(tmp_path / "s"),
        "FOLKLORE_CASE_OUTPUT_DIR": str(tmp_path / "o"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(source),
    }
    if os.environ.get("FOLKLORE_CASE_TEST_INSTALLED") == "1":
        env.pop("PYTHONPATH")
    stderr = tmp_path / "private-stderr.txt"
    with stderr.open("w+") as log:
        async with stdio_client(
            StdioServerParameters(command=sys.executable, args=["-c", launch], env=env),
            errlog=log,
        ) as streams:
            async with ClientSession(*streams, read_timeout_seconds=15) as session:
                initialized = await session.initialize()
                assert initialized.server_info.version == "1.2.0"
                listing = await session.list_tools()
                assert len(listing.tools) == 18
                ctx = await session.call_tool("list_analysis_contexts", {})
                assert not ctx.is_error, ctx.structured_content
                assert (
                    len(
                        ctx.structured_content["data"]["result"]["contexts"][0][
                            "scopes"
                        ]
                    )
                    == 5
                )
                result = await session.call_tool(source_browse.TOOL, ARGS)
                assert not result.is_error, result.structured_content
                assert result.content[0].text == "browse_source_objects: completed"
                assert (
                    result.structured_content["data"]["result"]["records"][0][
                        "key_prefix"
                    ]
                    == PRIVATE + "/"
                )
    raw = stderr.read_text()
    for value in (KEY, PRIVATE, X, R):
        assert value not in raw
