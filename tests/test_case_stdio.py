"""Independent genuine-SDK stdio tests; synthetic credential, network denied."""

import os
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from folklore_mcp_service.case_tools.contracts import TOOLS

KEY = "flk_" + "a" * 32 + "." + "b" * 43
LAUNCH = """
import runpy, socket, os, importlib.util
if os.environ.get("FOLKLORE_CASE_TEST_INSTALLED") == "1":
    origin = importlib.util.find_spec("folklore_mcp_service.case_tools.main").origin
    assert "/site-packages/" in origin, origin

def deny_network(*args, **kwargs):
    raise AssertionError('Network access prohibited in synthetic stdio acceptance')
socket.socket.connect = deny_network
socket.create_connection = deny_network
socket.getaddrinfo = deny_network
runpy.run_module('folklore_mcp_service.case_tools.main', run_name='__main__')
"""


@pytest.mark.asyncio
async def test_real_sdk_stdio_discovery_all_tools_and_typed_invalid_inputs(tmp_path):
    source = Path(__file__).resolve().parents[1] / "src"
    state, output = tmp_path / "state", tmp_path / "output"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", LAUNCH],
        env={
            "FOLKLORE_API_KEY": KEY,
            "FOLKLORE_CASE_STATE_DIR": str(state),
            "FOLKLORE_CASE_OUTPUT_DIR": str(output),
            "PYTHONPATH": str(source),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    if os.environ.get("FOLKLORE_CASE_TEST_INSTALLED") == "1":
        params.env.pop("PYTHONPATH", None)
        params.env["FOLKLORE_CASE_TEST_INSTALLED"] = "1"
    stderr = tmp_path / "stderr.log"
    with stderr.open("w+") as errors:
        async with stdio_client(params, errlog=errors) as streams:
            async with ClientSession(*streams, read_timeout_seconds=15) as session:
                discovery = await session.discover()
                assert discovery is not None
                listing = await session.list_tools()
                assert tuple(tool.name for tool in listing.tools) == TOOLS
                assert len(listing.tools) == 18
                for tool in listing.tools:
                    assert tool.description
                    hints = tool.annotations.model_dump(by_alias=True)
                    assert hints["destructiveHint"] is (
                        tool.name == "request_sequencing_analysis_cancellation"
                    )
                    assert tool.input_schema["type"] == "object"
                    Draft202012Validator.check_schema(tool.input_schema)
                    Draft202012Validator.check_schema(tool.output_schema)
                    invalid = (
                        {"unexpected": "synthetic"}
                        if tool.name == "list_analysis_contexts"
                        else {}
                    )
                    result = await session.call_tool(tool.name, invalid)
                    assert result.is_error is True
                    assert result.structured_content["ok"] is False
                    assert result.structured_content["error"]["code"] == "invalid_input"
                    Draft202012Validator(tool.output_schema).validate(
                        result.structured_content
                    )
                    text = " ".join(
                        item.text for item in result.content if item.type == "text"
                    )
                    assert text == tool.name + ": invalid_input"
                    assert KEY not in text
        errors.flush()
    assert KEY not in stderr.read_text()
    assert not list((state / "staging").iterdir())
    assert not list((state / "cache").iterdir())
    assert not list(output.iterdir())
    assert os.stat(state).st_mode & 0o777 == 0o700


def _test_source_module(name):
    import importlib.util

    path = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("independent_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PIPELINE_LAUNCH = LAUNCH.replace(
    "runpy.run_module('folklore_mcp_service.case_tools.main', run_name='__main__')",
    """
import asyncio, json, os
from pathlib import Path
import httpx
from folklore_mcp_service.case_tools import main
from folklore_mcp_service.case_tools.api_client import ApiClient

raw = Path(os.environ['FOLKLORE_TEST_EXPORT']).read_bytes()
manifest = json.loads(Path(os.environ['FOLKLORE_TEST_MANIFEST']).read_text())
status = json.loads(Path(os.environ['FOLKLORE_TEST_STATUS']).read_text())
traffic = Path(os.environ['FOLKLORE_TEST_TRAFFIC'])
calls = []

def handler(request):
    assert request.url.host == 'api.helena.bio'
    assert request.headers['Authorization'] == 'Bearer ' + os.environ['FOLKLORE_API_KEY']
    assert request.method == 'GET'
    calls.append(request.url.path)
    traffic.write_text(json.dumps(calls))
    if request.url.path == '/folklore/v1/context':
        return httpx.Response(200, json={'contexts': []})
    if request.url.path.endswith('/results'):
        return httpx.Response(200, json=manifest)
    if '/artifacts/' in request.url.path:
        return httpx.Response(200, content=raw, headers={'Content-Type': 'application/json'})
    if request.url.path == '/folklore/v1/analyses/' + manifest['analysis_id']:
        return httpx.Response(200, json=status)
    raise AssertionError('Unexpected first-party API route')

transport = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
api = ApiClient(os.environ['FOLKLORE_API_KEY'], client=transport)
main.ApiClient = lambda key: api
asyncio.run(main.serve())
""",
)


@pytest.mark.asyncio
async def test_real_stdio_api_client_download_worker_and_all_six_views(tmp_path):
    import json

    from folklore_mcp_service.case_tools.contracts import EXPORT_PACKET

    export_fixture = _test_source_module("test_case_exports")
    api_fixture = _test_source_module("test_case_api")
    _, identity, artifact, _ = export_fixture.frozen.__wrapped__(
        tmp_path, EXPORT_PACKET
    )
    manifest = api_fixture.manifest(artifact.read_bytes())
    aid, cid = identity["analysis_id"], identity["case_id"]
    status = {
        "analysis_id": aid,
        "case_id": cid,
        "status": "succeeded",
        "stage": "complete",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "error": None,
        "cost": {"reserved_units": 9007199254740993},
        "billing": {"state": "consumed"},
        "warnings": [],
        "links": {
            "self": "/folklore/v1/analyses/" + aid,
            "results": "/folklore/v1/analyses/" + aid + "/results",
            "folklore": "https://folklore.helena.bio/app/analysis/" + cid,
        },
    }
    manifest_path, status_path, traffic = (
        tmp_path / name for name in ("manifest.json", "status.json", "traffic.json")
    )
    manifest_path.write_text(json.dumps(manifest))
    status_path.write_text(json.dumps(status))
    source = Path(__file__).resolve().parents[1] / "src"
    state, output = tmp_path / "state", tmp_path / "output"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", PIPELINE_LAUNCH],
        env={
            "FOLKLORE_API_KEY": KEY,
            "FOLKLORE_CASE_STATE_DIR": str(state),
            "FOLKLORE_CASE_OUTPUT_DIR": str(output),
            "PYTHONPATH": str(source),
            "PYTHONDONTWRITEBYTECODE": "1",
            "FOLKLORE_TEST_EXPORT": str(artifact),
            "FOLKLORE_TEST_MANIFEST": str(manifest_path),
            "FOLKLORE_TEST_STATUS": str(status_path),
            "FOLKLORE_TEST_TRAFFIC": str(traffic),
        },
    )
    if os.environ.get("FOLKLORE_CASE_TEST_INSTALLED") == "1":
        params.env.pop("PYTHONPATH", None)
        params.env["FOLKLORE_CASE_TEST_INSTALLED"] = "1"
    with (tmp_path / "pipeline-stderr.log").open("w+") as errors:
        async with stdio_client(params, errlog=errors) as streams:
            async with ClientSession(*streams, read_timeout_seconds=20) as session:
                await session.discover()
                listing = await session.list_tools()
                schemas = {tool.name: tool.output_schema for tool in listing.tools}

                async def call(name, args):
                    result = await session.call_tool(name, args)
                    assert result.is_error is False, result.structured_content
                    Draft202012Validator(schemas[name]).validate(
                        result.structured_content
                    )
                    return result.structured_content["data"]

                contexts = await call("list_analysis_contexts", {})
                assert contexts["result"] == {"contexts": []}
                observed = await call("get_case_analysis_status", {"analysis_id": aid})
                assert (
                    observed["result"]["cost"]["reserved_units"] == "9007199254740993"
                )
                metadata = await call(
                    "get_case_analysis_result_manifest", {"analysis_id": aid}
                )
                assert metadata["result"]["generation_id"] == identity["generation_id"]
                for name in EXPORT_PACKET["input_schemas"]:
                    args = {"analysis_id": aid}
                    if name == "query_analysis_export_records":
                        args.update(collection="variants", limit=1)
                    elif name == "get_analysis_export_variant":
                        args["variant_idx"] = "0"
                    elif name == "get_analysis_export_gene_records":
                        args.update(collection="variants", gene_symbol="GENE1")
                    data = await call(name, args)
                    assert data["generation_id"] == identity["generation_id"]
                    if name == "get_analysis_export_variant":
                        assert data["record"]["global_af"] == "0.1"
                    if name == "query_analysis_export_records":
                        assert data["records"][0]["variant_idx"] == "0"
                        second = await call(
                            name, {**args, "cursor": data["next_cursor"]}
                        )
                        assert second["records"][0]["variant_idx"] == "1"
                saved = await call(
                    "download_analysis_result_file",
                    {"analysis_id": aid, "artifact_id": identity["artifact_id"]},
                )
                delivered = Path(saved["file"]["local_path"])
                assert delivered.read_bytes() == artifact.read_bytes()
                assert delivered.parent == output
                assert delivered.stat().st_mode & 0o777 == 0o600
    calls = json.loads(traffic.read_text())
    assert (
        calls.count(
            "/folklore/v1/analyses/" + aid + "/artifacts/" + identity["artifact_id"]
        )
        == 2
    )
    assert calls.count("/folklore/v1/analyses/" + aid + "/results") >= 18
    assert not list((state / "staging").iterdir())
    assert not list((state / "cache").iterdir())
    assert KEY not in (tmp_path / "pipeline-stderr.log").read_text()
