"""Offline declarative-recipe checks; no executor or agent behavior measurement."""

from __future__ import annotations

import json
import socket
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.main import create_app

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"


def load(name):
    return json.loads((REGISTRY / name).read_text())


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Task-contract tests must not use external networking")

    for name in ("getaddrinfo", "create_connection"):
        monkeypatch.setattr(socket, name, blocked)
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, blocked)


class NoScientificGateway:
    async def close(self):
        pass

    async def search(self, *args, **kwargs):
        raise AssertionError("Catalog validation must not execute science")

    async def request(self, *args, **kwargs):
        raise AssertionError("Catalog validation must not execute science")


def source_catalog(**overrides):
    configured = {
        "ENVIRONMENT": "test",
        "FOLKLORE_MCP_ENABLED": True,
        "FOLKLORE_LITERATURE_ENABLED": True,
        "FOLKLORE_GENE_DISEASE_ENABLED": True,
        "FOLKLORE_PUBLIC_GENE_ENABLED": True,
    }
    configured.update(overrides)
    settings = Settings(**configured)
    gateway = NoScientificGateway()
    app = create_app(
        settings,
        gateway=gateway,
        literature_gateway=gateway,
        gene_disease_gateway=gateway,
        public_gene_gateway=gateway,
    )
    with TestClient(app) as client:
        response = client.post(
            "/folklore/v1/mcp",
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "tools/list",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {
                    "_meta": {
                        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                        "io.modelcontextprotocol/clientCapabilities": {},
                        "io.modelcontextprotocol/clientInfo": {
                            "name": "offline-recipe-validation",
                            "version": "1",
                        },
                    }
                },
            },
        )
        assert response.status_code == 200
        return {tool["name"]: tool for tool in response.json()["result"]["tools"]}


def pointer(value, path):
    """Evaluate a real JSON Pointer on a synthetic test fixture only."""
    assert path.startswith("/") and "{" not in path and "}" not in path
    for token in path[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


@pytest.fixture
def synthetic_responses():
    # These are binding-shape fixtures, not scientific evidence or observations.
    return {
        "resolve_gene": {
            "structuredContent": {
                "result": {
                    "candidates": [{"identity": {"gene_id": "HGNC:1100"}}],
                    "identity_snapshot_id": "a" * 64,
                }
            }
        },
        "search_variant_evidence": {
            "structuredContent": {
                "result": {"identity": {"canonical_key": "GRCh38:chr17:43124027:ACT:A"}}
            }
        },
        "search_variant_literature": {
            "structuredContent": {
                "literature": {"publications": [{"pmid": "12345678"}]}
            }
        },
    }


def fixture_arguments(recipe, responses):
    """Materialize test data only, with an explicitly selected synthetic member."""
    if recipe["kind"] == "literal":
        return deepcopy(recipe["arguments"])
    arguments = deepcopy(recipe["fixedArguments"])
    for binding in recipe["bindings"]:
        value = pointer(responses[binding["fromTool"]], binding["responseField"])
        if "selectedMemberPointer" in binding:
            # Fixture index0 is an explicit test choice, never a production rule.
            value = pointer(value[0], binding["selectedMemberPointer"])
        assert binding["argument"] not in arguments
        arguments[binding["argument"]] = value
    return arguments


def test_companion_is_closed_and_covers_actual_source_catalog(catalog):
    contract, schema = load("task-contracts.json"), load("task-contracts.schema.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(contract, schema)
    names = [route["tool"] for route in contract["routes"]]
    assert len(names) == len(set(names)) == 10
    assert set(names) == set(catalog) - {"support_helena"}
    assert set(names) == {r["tool"] for r in load("agent-selection.json")["routing"]}
    assert (
        contract["pointerRoot"]
        == "MCP CallToolResult; excludes the outer JSON-RPC envelope"
    )
    mutated = deepcopy(contract)
    mutated["routes"][0]["invented_field"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(mutated, schema)


def test_recipes_validate_actual_emitted_input_schemas(catalog, synthetic_responses):
    for route in load("task-contracts.json")["routes"]:
        schema = catalog[route["tool"]]["inputSchema"]
        assert schema["additionalProperties"] is False
        arguments = fixture_arguments(route["inputRecipe"], synthetic_responses)
        jsonschema.validate(arguments, schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {**arguments, "private_case_context": "forbidden"}, schema
            )


def test_wrong_assembly_and_malformed_snapshot_fail_input_schema(catalog):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {"query": "rs429358", "assembly": "GRCh37"},
            catalog["search_variant_evidence"]["inputSchema"],
        )
    for value in ("<returned snapshot>", "A" * 64, "a" * 63):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {"gene_id": "HGNC:1100", "snapshot_id": value},
                catalog["get_gene_profile"]["inputSchema"],
            )


def test_response_bound_shapes_are_not_literal_executable_arguments(catalog):
    contract, schema = load("task-contracts.json"), load("task-contracts.schema.json")
    for route in contract["routes"]:
        recipe = route["inputRecipe"]
        if recipe["kind"] != "response_bound":
            continue
        assert "arguments" not in recipe
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                recipe["fixedArguments"], catalog[route["tool"]]["inputSchema"]
            )
        mutated = deepcopy(contract)
        current = next(r for r in mutated["routes"] if r["tool"] == route["tool"])
        current["inputRecipe"]["kind"] = "literal"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(mutated, schema)


def test_gene_bindings_declare_same_response_identity_and_snapshot():
    for route in load("task-contracts.json")["routes"]:
        if route["tool"] not in {
            "get_gene_profile",
            "get_gene_section",
            "search_gene_literature",
        }:
            continue
        bindings = {b["argument"]: b for b in route["inputRecipe"]["bindings"]}
        assert set(bindings) == {"gene_id", "snapshot_id"}
        assert {b["fromTool"] for b in bindings.values()} == {"resolve_gene"}
        assert {b["responseGroup"] for b in bindings.values()} == {
            "resolved_gene_identity"
        }
        assert (
            bindings["gene_id"]["responseField"]
            == "/structuredContent/result/candidates"
        )
        assert bindings["gene_id"]["selectedMemberPointer"] == "/identity/gene_id"
        assert "ambiguous" in bindings["gene_id"]["selectionRule"]
        assert (
            bindings["snapshot_id"]["responseField"]
            == "/structuredContent/result/identity_snapshot_id"
        )
        assert (
            "same successful resolution response"
            in bindings["snapshot_id"]["selectionRule"]
        )
        assert "snapshot_id" not in route["inputRecipe"]["fixedArguments"]
        assert "cursor" not in route["inputRecipe"]["fixedArguments"]


def test_missing_binding_pointer_is_not_replaced_with_a_fixture_value(
    synthetic_responses,
):
    recipe = next(
        r
        for r in load("task-contracts.json")["routes"]
        if r["tool"] == "get_gene_profile"
    )["inputRecipe"]
    del synthetic_responses["resolve_gene"]["structuredContent"]["result"][
        "identity_snapshot_id"
    ]
    with pytest.raises(KeyError):
        fixture_arguments(recipe, synthetic_responses)


def test_scope_guides_and_entrypoints_are_consistent():
    contract = load("task-contracts.json")
    for route in contract["routes"]:
        assert (REGISTRY / route["guide"]).is_file()
        assert route["capabilityGates"][0] == "FOLKLORE_MCP_ENABLED"
    text = json.dumps(contract)
    assert "HPO" in text and "OMIM" in text and "patient phenotype narratives" in text
    assert "Native GRCh37" in text and "abstract-free" in text.lower()
    for path in (
        ROOT / "README.md",
        REGISTRY / "README.md",
        ROOT / "docs/INTEGRATION_BRIEF.md",
    ):
        assert "task-contracts.json" in path.read_text()


@pytest.fixture
def catalog():
    return source_catalog()


@pytest.mark.parametrize(
    "disabled",
    [
        {"FOLKLORE_LITERATURE_ENABLED"},
        {"FOLKLORE_GENE_DISEASE_ENABLED"},
        {"FOLKLORE_PUBLIC_GENE_ENABLED"},
        {
            "FOLKLORE_LITERATURE_ENABLED",
            "FOLKLORE_GENE_DISEASE_ENABLED",
            "FOLKLORE_PUBLIC_GENE_ENABLED",
        },
    ],
)
def test_declared_capability_gates_match_source_catalog(disabled):
    available = source_catalog(**dict.fromkeys(disabled, False))
    expected = {
        route["tool"]
        for route in load("task-contracts.json")["routes"]
        if not set(route["capabilityGates"]) & disabled
    }
    assert set(available) - {"support_helena"} == expected


def test_malformed_json_pointer_is_rejected_by_companion_schema():
    contract = load("task-contracts.json")
    route = next(r for r in contract["routes"] if r["tool"] == "get_gene_profile")
    route["inputRecipe"]["bindings"][0]["responseField"] = (
        "/structuredContent/~2invalid"
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(contract, load("task-contracts.schema.json"))


def test_published_schema_rejects_duplicate_tool_and_missing_route():
    contract = load("task-contracts.json")
    contract["routes"][-1] = deepcopy(contract["routes"][0])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(contract, load("task-contracts.schema.json"))


def test_adapter_error_guidance_is_route_qualified():
    contract = load("task-contracts.json")
    for instruction in contract["beforeBinding"]:
        if "adapter_error" in instruction:
            assert "where supplied by that route contract" in instruction
    for route in contract["routes"]:
        for instruction in route["stopOrUseAlternative"]:
            if "adapter_error" in instruction:
                assert "where supplied by the route contract" in instruction
