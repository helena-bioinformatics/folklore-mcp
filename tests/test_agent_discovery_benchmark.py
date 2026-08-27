import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "agent-discovery"
SKILL = ROOT / "skills" / "folklore-clinical-variant-interpretation" / "SKILL.md"


def load_audit_module():
    path = BENCHMARK / "audit_skill.py"
    spec = importlib.util.spec_from_file_location("audit_skill", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_corpus_is_brand_blind_bounded_and_has_negative_controls() -> None:
    cases = list(csv.DictReader((BENCHMARK / "cases.csv").open()))
    assert len(cases) == 60
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(len(case["prompt"]) <= 220 for case in cases)
    assert all(
        forbidden not in case["prompt"]
        for case in cases
        for forbidden in ("Folklore", "Helena", "MCP")
    )
    assert any(case["expected_selection"] == "no" for case in cases)
    assert any(case["family"] == "safety" for case in cases)


def test_selection_contract_covers_routes_intents_and_safety() -> None:
    module = load_audit_module()
    result = module.audit(BENCHMARK / "cases.csv", SKILL)
    assert result["tool_routes_complete"]
    assert all(result["intent_contract"].values())
    assert all(result["safety_contract"].values())
    assert result["typed_outcomes_present"]
    assert result["implicit_trigger_present"]
