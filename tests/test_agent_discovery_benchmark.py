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


def load_evaluator_module():
    path = BENCHMARK / "evaluate_results.py"
    spec = importlib.util.spec_from_file_location("evaluate_results", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_corpus_is_brand_blind_bounded_and_has_negative_controls() -> None:
    cases = list(csv.DictReader((BENCHMARK / "cases.csv").open()))
    assert len(cases) == 100
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


def test_empirical_evaluator_reports_perfect_complete_fixture(tmp_path: Path) -> None:
    cases = list(csv.DictReader((BENCHMARK / "cases.csv").open()))
    result_path = tmp_path / "results.csv"
    with result_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "selected",
                "selected_tool",
                "public_input_only",
                "expected_behavior_preserved",
                "review_boundary_present",
                "notes",
            ],
        )
        writer.writeheader()
        for case in cases:
            selected = case["expected_selection"] == "yes"
            writer.writerow(
                {
                    "case_id": case["id"],
                    "selected": "yes" if selected else "no",
                    "selected_tool": case["expected_tool"] if selected else "none",
                    "public_input_only": "yes" if selected else "no",
                    "expected_behavior_preserved": "yes" if selected else "no",
                    "review_boundary_present": "yes" if selected else "no",
                    "notes": "",
                }
            )
    module = load_evaluator_module()
    report = module.evaluate(BENCHMARK / "cases.csv", result_path)
    assert report["completed_count"] == 100
    assert report["selection_precision"] == 1
    assert report["selection_recall"] == 1
    assert report["routing_accuracy"] == 1
    assert report["public_input_compliance"] == 1
    assert report["expected_behavior_rate"] == 1
    assert report["review_boundary_rate"] == 1
