import ast
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

ROOT = Path(__file__).resolve().parents[1]
USER = "77e8885e-02a4-43ca-a63a-20fcdcd65d94"
SESSION = "7f78d2e5-12e1-4142-86b5-cf872731420e"
OTHER = "f29fe568-bd51-465e-8b13-eb20a8112ac9"
SETTINGS = {
    "analytics_opt_in": True,
    "analytics_user_id": USER,
    "analytics_session_id": SESSION,
    "analytics_intent": "variant_evidence",
}
SOURCES = [
    "integrations/dify/tools/mcp_client.py",
    "integrations/galaxy/folklore_mcp.py",
    "integrations/knime/knime_node.py",
    "integrations/openai-agents-python/main.py",
]


def functions(source):
    tree = ast.parse(source)
    tree.body = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "journey_metadata"
    ]
    scope = {"UUID": UUID}
    exec(compile(tree, "client-fixture", "exec"), scope)
    return scope


@pytest.fixture(params=SOURCES + ["notebook"])
def project(request):
    if request.param == "notebook":
        v = json.loads(
            (
                ROOT / "integrations/notebooks/folklore_variant_to_noodle_graph.ipynb"
            ).read_text()
        )
        source = "".join(v["cells"][1]["source"])
    else:
        source = (ROOT / request.param).read_text()
    return functions(source)["journey_metadata"]


@pytest.mark.parametrize(
    "changes",
    [
        {"analytics_opt_in": False},
        {"analytics_opt_in": "true"},
        {"analytics_opt_in": 1},
        {"analytics_user_id": "patient@example.invalid"},
        {"analytics_user_id": USER.upper()},
        {"analytics_user_id": []},
        {"analytics_user_id": "77e8885e-02a4-13ca-a63a-20fcdcd65d94"},
    ],
)
def test_invalid_or_disabled_context_is_anonymous(project, changes):
    assert project({**SETTINGS, **changes}) == {}
    assert project(None) == {}
    assert project({}) == {}


def test_allowed_projection_and_actual_session_boundaries(project):
    settings = {**SETTINGS, "email": "private", "reason": "private", "query": "private"}
    expected = {
        "opt_in": True,
        "user_id": USER,
        "session_id": SESSION,
        "intent": "variant_evidence",
    }
    assert project(settings) == {"io.helena/analytics": expected}
    assert project(settings) == project(settings)
    assert (
        project({**settings, "analytics_session_id": OTHER})["io.helena/analytics"][
            "session_id"
        ]
        == OTHER
    )
    assert settings["analytics_session_id"] == SESSION
    result = project(
        {
            **settings,
            "analytics_session_id": "private",
            "analytics_intent": "private patient prompt",
        }
    )
    assert result == {"io.helena/analytics": {"opt_in": True, "user_id": USER}}


def load(path):
    spec = importlib.util.spec_from_file_location("test_client", ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Response:
    def __enter__(self):
        import io

        return io.BytesIO(
            json.dumps(
                {"result": {"structuredContent": {"status": "ambiguous"}}}
            ).encode()
        )

    def __exit__(self, *args):
        pass


def test_dify_actual_http_builder_keeps_science_separate():
    client = load("integrations/dify/tools/mcp_client.py")
    requests = []

    def send(req, **kwargs):
        requests.append(json.loads(req.data))
        return Response()

    with patch.object(client.urllib.request, "urlopen", send):
        for analytics in [None, SETTINGS, {**SETTINGS, "analytics_opt_in": False}]:
            assert client.call_tool(
                "classify_germline_variant",
                {"query": "rs80357914"},
                analytics=analytics,
            ) == {"status": "ambiguous"}
    assert all(x["params"]["arguments"] == {"query": "rs80357914"} for x in requests)
    assert "io.helena/analytics" not in requests[0]["params"]["_meta"]
    assert (
        requests[1]["params"]["_meta"]["io.helena/analytics"]["session_id"] == SESSION
    )
    assert "io.helena/analytics" not in requests[2]["params"]["_meta"]


def test_galaxy_real_cli_uses_explicit_context(tmp_path, monkeypatch):
    client = load("integrations/galaxy/folklore_mcp.py")
    result = []

    def send(req, **kwargs):
        result.append(json.loads(req.data))
        return Response()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "galaxy",
            "--query",
            "rs80357914",
            "--output",
            str(tmp_path / "out.json"),
            "--analytics-opt-in",
            "--analytics-user-id",
            USER,
            "--analytics-session-id",
            SESSION,
            "--analytics-intent",
            "variant_evidence",
        ],
    )
    with patch.object(client.urllib.request, "urlopen", send):
        assert client.main() == 0
    assert result[0]["params"]["_meta"]["io.helena/analytics"]["user_id"] == USER
    assert json.loads((tmp_path / "out.json").read_text()) == {"status": "ambiguous"}


def test_notebook_only_attaches_context_to_folklore():
    v = json.loads(
        (
            ROOT / "integrations/notebooks/folklore_variant_to_noodle_graph.ipynb"
        ).read_text()
    )
    scope = {}
    exec("".join(v["cells"][1]["source"]), scope)
    result = []

    def send(req, **kwargs):
        result.append(json.loads(req.data))
        return Response()

    with patch("urllib.request.urlopen", send):
        for endpoint in [scope["FOLKLORE"], scope["NOODLE"]]:
            scope["call_tool"](
                endpoint,
                "classify_germline_variant",
                {"query": "rs80357914"},
                analytics=SETTINGS,
            )
    assert "io.helena/analytics" in result[0]["params"]["_meta"]
    assert "io.helena/analytics" not in result[1]["params"]["_meta"]


def test_sdk_runtime_resolver_uses_application_context(monkeypatch):
    import asyncio

    captured = []

    class Server:
        def __init__(self, **kwargs):
            captured.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    async def run(*args):
        return types.SimpleNamespace(final_output="unchanged")

    agents = types.ModuleType("agents")
    agents.Agent = lambda **kw: kw
    agents.Runner = types.SimpleNamespace(run=run)
    mcp = types.ModuleType("agents.mcp")
    mcp.MCPServerStreamableHttp = Server
    mcp.create_static_tool_filter = lambda **kw: kw
    monkeypatch.setitem(sys.modules, "agents", agents)
    monkeypatch.setitem(sys.modules, "agents.mcp", mcp)
    client = load("integrations/openai-agents-python/main.py")
    assert asyncio.run(client.run("public query", analytics=SETTINGS)) == "unchanged"
    assert (
        captured[0]["tool_meta_resolver"](None)["io.helena/analytics"]["session_id"]
        == SESSION
    )
    assert asyncio.run(client.run("public query")) == "unchanged"
    assert captured[1]["tool_meta_resolver"](None) == {}


@pytest.mark.parametrize(
    "file,cls",
    [
        ("classify_germline_variant", "ClassifyGermlineVariantTool"),
        ("search_variant_literature", "SearchVariantLiteratureTool"),
        ("search_literature_corpus", "SearchLiteratureCorpusTool"),
        ("get_publication_details", "GetPublicationDetailsTool"),
    ],
)
def test_each_dify_tool_passes_operator_context(monkeypatch, file, cls):
    captured = []

    class Tool:
        def create_text_message(self, text):
            return text

    dify = types.ModuleType("dify_plugin")
    dify.Tool = Tool
    entities = types.ModuleType("dify_plugin.entities.tool")
    entities.ToolInvokeMessage = str
    client = types.ModuleType("tools.mcp_client")

    def call(name, arguments, *, analytics=None):
        captured.append((arguments, analytics))
        return {"status": "ambiguous"}

    client.call_tool = call
    monkeypatch.setitem(sys.modules, "dify_plugin", dify)
    monkeypatch.setitem(sys.modules, "dify_plugin.entities.tool", entities)
    monkeypatch.setitem(sys.modules, "tools.mcp_client", client)
    module = load(f"integrations/dify/tools/{file}.py")
    settings = {**SETTINGS, "query": "rs80357914", "pmid": "12345", "limit": 1}
    assert list(getattr(module, cls)()._invoke(settings))
    assert captured[0][1] is settings
    assert not any(key.startswith("analytics_") for key in captured[0][0])


@pytest.mark.parametrize("enabled", [True, False])
def test_knime_actual_script_reuses_run_context(monkeypatch, enabled):
    import runpy

    knio = types.ModuleType("knime.scripting.io")
    knio.flow_variables = {**SETTINGS, "analytics_opt_in": enabled}
    column = types.SimpleNamespace(
        to_pylist=lambda: ["rs80357914", "chr4:67754019 T>C"]
    )
    knio.input_tables = [
        types.SimpleNamespace(
            to_pyarrow=lambda: types.SimpleNamespace(column=lambda index: column)
        )
    ]
    knio.output_tables = {}
    knio.Table = types.SimpleNamespace(from_pyarrow=lambda rows: rows)
    pa = types.ModuleType("pyarrow")
    pa.Table = types.SimpleNamespace(from_pylist=lambda rows: rows)
    monkeypatch.setitem(sys.modules, "knime", types.ModuleType("knime"))
    monkeypatch.setitem(
        sys.modules, "knime.scripting", types.ModuleType("knime.scripting")
    )
    monkeypatch.setitem(sys.modules, "knime.scripting.io", knio)
    monkeypatch.setitem(sys.modules, "pyarrow", pa)
    requests = []

    def send(req, **kwargs):
        requests.append(json.loads(req.data))
        return Response()

    with patch("urllib.request.urlopen", send):
        runpy.run_path(str(ROOT / "integrations/knime/knime_node.py"))
    assert len(requests) == len(knio.output_tables[0]) == 2
    metadata = [r["params"]["_meta"] for r in requests]
    assert all(("io.helena/analytics" in m) == enabled for m in metadata)
    assert metadata[0] == metadata[1]
