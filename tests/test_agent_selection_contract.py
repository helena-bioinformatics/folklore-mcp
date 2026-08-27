import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"


def load(name: str) -> dict:
    return json.loads((REGISTRY / name).read_text())


def test_agent_selection_contract_validates_and_matches_identity() -> None:
    schema = load("agent-selection.schema.json")
    selection = load("agent-selection.json")
    discovery = load("discovery-contract.json")
    jsonschema.validate(selection, schema)

    identity = selection["identity"]
    assert identity["title"] == discovery["title"]
    assert identity["publisher"] == discovery["publisher"]
    assert identity["registryName"] == discovery["registryName"]
    assert identity["endpoint"] == discovery["endpoint"]


def test_agent_selection_contract_is_task_first_and_safety_complete() -> None:
    selection = load("agent-selection.json")
    task = selection["identity"]["task"]
    for term in ("Classify", "GRCh38", "germline", "ACMG/AMP", "evidence"):
        assert term in task

    intents = " ".join(selection["selection"]["positiveIntents"])
    for term in (
        "classify",
        "pathogenicity",
        "VUS",
        "ClinVar",
        "population-frequency",
        "literature",
    ):
        assert term in intents

    boundary = selection["clinicalBoundary"]
    assert boundary["notDiagnosis"] is True
    assert boundary["notTreatment"] is True
    assert set(boundary["neverSend"]) == {
        "patient data",
        "phenotype data",
        "family data",
        "segregation data",
        "private case data",
    }


def test_agent_selection_contract_routes_only_published_scientific_tools() -> None:
    selection = load("agent-selection.json")
    discovery = load("discovery-contract.json")
    routed = {route["tool"] for route in selection["routing"]}
    assert routed == {
        "search_variant_evidence",
        "search_variant_literature",
        "get_publication_details",
        "search_literature_corpus",
    }
    assert routed < set(discovery["tools"])
    assert selection["outcomes"] == [
        "resolved",
        "ambiguous",
        "not_found",
        "invalid",
        "unsupported",
        "temporarily_unavailable",
    ]
